---
title: Identity in the event path
description: Who submitted a request, which agent answered it, and what each check proves.
sidebar_position: 3
---

:::warning Alpha

Every control on this page is **off by default**. With none of them configured — which is how
the shipped manifests start — `POST /v0/agents` accepts anonymous requests, nothing is signed,
and nothing is verified. See [Turning the controls on](#turning-the-controls-on) for the
variables that enable each one.

:::

On the platform, a direct call to an agent passes through [AuthBridge](../security/authbridge.md),
which authenticates it and limits what it can reach. EventBridge's own HTTP API does not, and
neither does an event on the broker: once a message is on the broker, anything that can write to
the topic can add to it. This page covers the two controls that narrow that gap, and states
plainly what each one does not cover.

## Two questions, two mechanisms

The two questions look similar and need different answers:

| | Which person asked for this? | Which agent produced this? |
| --- | --- | --- |
| Verified by | GitHub, at the front door; the answer is cached per token | A signature on the event itself |
| Mechanism | OAuth device flow, then a lookup of the login | Ed25519 detached JWS with a key id |
| Trust root | GitHub | A list of approved public keys |
| Checked at | EventBridge | EventRunner for requests, EventBridge for responses |

A user signs in once and gets a token. An agent holds a private key and signs the final event of
each run. Those are different problems: one is about a human authorizing work, the other is about
a workload proving it is the one that did the work.

## Which person asked for this

The caller signs in with GitHub (see [GitHub OAuth App](github-oauth-app.md)) and sends the
resulting token on every request. EventBridge then:

1. Looks up the token in a cache keyed by a hash of the token, never the token itself.
2. On a miss, calls `GET https://api.github.com/user` to get the login.
3. Checks the login against `EB_ALLOWED_USERS`.
4. Records the login on the request event as `ce_submitter`, with `ce_submitteriss: github`. The
   issuer is **absent** when the name came from a static `EB_AUTH_TOKENS` entry, which is how a
   reader tells a GitHub identity from a name an operator typed into an env var.

The attribute is spelled `submitteriss`, without a separator: CloudEvents v1.0 restricts
attribute names to lower-case `[a-z0-9]`, so `submitter_iss` is rejected or silently dropped by
a spec-compliant consumer.

With sign-in on, the outcomes a caller sees — every `401` carries a `WWW-Authenticate` challenge:

| Case | Response |
| --- | --- |
| No credential | `401` |
| Unknown token, or a revoked one once its cache entry expires | `401` |
| GitHub unreachable, rate-limited, or returning 5xx | `401` — the check fails closed |
| Valid GitHub user, not on the approved list | `403` |
| Approved user | `202`, and the identity travels on the event |
| Static `EB_AUTH_TOKENS` holder | `202`, with no `ce_submitteriss` |

With neither sign-in nor static tokens configured, which is the default, every caller gets `202`
anonymously and no `ce_submitter` is recorded. `EB_AUTH_TOKENS` on its own already ends anonymous
starts, as long as one entry parses: a request with no credential then gets `401`. An entry without
a colon is skipped silently, so a value in which no entry parses leaves starts anonymous.

The `403` is the interesting one. The person is real and authenticated, and is still refused.

Failures are not cached, so every retry during a GitHub outage calls GitHub again — while logins
already in the cache keep working until their entry expires.

**Static tokens are checked first.** An `EB_AUTH_TOKENS` entry never consults
`EB_ALLOWED_USERS` and records no issuer. It is the break-glass path for a GitHub outage, and it
is also why removing a name from the approved list does not remove a static-token holder.

**GitHub returns an opaque token, not a signed one.** There is nothing in it to verify offline,
so EventBridge has to ask GitHub who the token belongs to. That makes sign-in depend on GitHub
being reachable, and it is why the cache exists: without it, every request would cost an API
call.

## Which agent produced this

Each agent runner holds a private key and signs the final event of each run. EventBridge holds
its own signing key, plus a file of approved public keys listed by key id:

```text
EventBridge    private: its own signing key    public: approved agent keys, by kid
                                                       (including its own, under EB_SIGNING_KID)
EventRunner    private: its own signing key    public: the EventBridge key

requests    EventBridge signs  ─▶  EventRunner verifies before running anything
responses   EventRunner signs  ─▶  EventBridge verifies terminal events before storing
```

That file **is** the approved-agent list. With enforcement on, an event signed under a kid that
is not in the file is refused, and so is a terminal event with no signature.

<!-- VERIFY: drop "the flag does not stop it" once rossoctl/examples#885 lands — a rejected event
     will no longer reach on_group_event, on_member_event or insert_response. -->

Group events are signed by EventBridge, under `EB_SIGNING_KID`, so a group event under any other
kid is flagged with enforcement on. **At this revision the flag does not stop it**, and a refused
member response can end a batch by a second path — see
[What these controls do not prove](#what-these-controls-do-not-prove).

**Both keysets are flat.** A kid makes a signature attributable, not restricted: any approved
runner can sign a terminal response for any correlation id. On the request side,
`ER_VERIFY_KEYSET_PATH` must hold EventBridge's key alone — a runner key in that file would let
that runner sign requests with any `ce_submitter`.

Two refusals are worth seeing. Both need their control turned on first:

- **An unsigned request** injected straight onto the topic is refused before the agent starts,
  when `ER_REQUIRE_SIGNATURE=true`. No agent process is created. The offset is committed with no
  retry and no dead-letter queue, and no response event is emitted, so the caller sees no reply, and
  EventRunner's only trace is a log line. EventBridge still shows the prompt (see below). Under
  KEDA, consumer lag still wakes a runner pod from zero only to refuse the message.
- **A forged terminal response** published by anything holding broker write access is stored as
  `phase=error`, shown as a failure in the transcript, and raises a priority-5 notification —
  with `EB_VERIFY_KEYSET_PATH` set **and** `EB_REQUIRE_RESPONSE_SIGNATURE=true`. Every
  notification on this page needs ntfy enabled with a topic, which is off as shipped; for a group
  member the priority-5 one also needs `NTFY_GROUP_NOTIFY_ERRORS=true`. A keyset alone is audit
  mode: the event is stored unchanged. **At this revision nothing records the failure**, so there is
  no reject rate to watch before you enforce.
  <!-- VERIFY: drop "nothing records the failure" once rossoctl/examples#886 lands. -->


EventRunner does not run a refused request, but the transcript can still show it: EventBridge's
requests mirror does not verify signatures, so a forged prompt can still be back-filled into the
prompt store and appear as a user turn.

Signing uses Ed25519 rather than a shared secret on purpose. With a shared secret, every party
that can verify can also forge, so EventBridge could produce any agent's answers and one agent
could produce another's. Asymmetric keys mean a private key never leaves the runner that owns
it.

Signing costs roughly 150–200 ms per event **in this implementation**, because Ed25519 is written
in pure Python here, because the examples allow no C extensions. A native implementation takes
microseconds;
the cost is the demo's, not the algorithm's. Verification costs about the same.

That cost is why responses are signed on terminal events only, rather than on every streamed
fragment — and it is the limit behind the next section.

## What these controls do not prove

Be precise about the claims, because a control that is oversold is worse than one that is
absent.

<!-- VERIFY: several limits below are open bugs in the examples repo, and each claim stops being
     true when its issue lands. Group completion and the overwrite: rossoctl/examples#885. Audit
     mode: #886. The open PUT /transcript and the listable ids: #887. Refusal with no keyset
     refusing nothing, under "Turning the controls on": #888. -->


- **Only starting work is authenticated.** `POST /v0/agents` and `POST /v0/groups` check sign-in.
  `POST /v0/agents/{id}/continue` and `/continue-html`, `PUT` and `GET /v0/agents/{id}/transcript`,
  the group `close` and `cancel` endpoints, and every transcript read are open to anyone who can
  reach EventBridge and name the conversation — and a continued turn carries no `ce_submitter`.
  `PUT …/transcript` replaces the session history EventRunner resumes from on a cold pod, and no
  signature covers it, so anyone who can name a conversation can rewrite the history the agent
  continues with. **The ids are not secret:** `GET /v0/groups` lists the 100 most recent groups and
  `GET /v0/groups/{id}/status` every member's correlation id, both without sign-in. Other ids come
  from about 25 million values, and nothing limits the rate of guessing. Removing a user from
  `EB_ALLOWED_USERS` therefore stops new work only.
- **Signing covers the final event of a run, not the stream.** An event that carries no signature
  and is not terminal is passed through even with enforcement on. A forged non-terminal
  `phase=result` frame renders in the transcript and sends a push notification — though for a group
  member no `phase=result` frame is ever pushed, so that notification does not happen. Once stored,
  the verified answer is not protected either: a later unsigned frame with the same sequence number
  replaces it in the transcript, and sequence numbers are readable without sign-in. So a terminal
  signature does not reliably prove who finished a run.
- **Anything that can write to the responses topic can end a batch.** At this revision EventBridge
  still applies a flagged `group.completed`, and replays group events unverified on restart. A
  refused member response also still counts that member as failed — the rewritten event keeps its
  `final` and `groupid` attributes. Once every member is counted, the batch completes. The member's
  real signed answer still reaches its transcript, but the batch count ignores it as a duplicate.
- **Audit mode records nothing.** A keyset without `EB_REQUIRE_RESPONSE_SIGNATURE=true` is meant to
  verify and log while storing events unchanged. It does store them unchanged, but nothing is logged
  or counted, so there is no reject rate to watch before you enforce.
- **A forged prompt is still back-filled.** EventRunner does not run a refused request, but
  EventBridge's requests mirror does not verify signatures, so an injected prompt appears as a user
  turn in the transcript whether or not it was signed.
- **Tokens are not bound to the app.** EventBridge accepts any GitHub token for an approved
  login — a PAT, `gh auth token`, or a token held by another app. See
  [GitHub OAuth App](github-oauth-app.md#configure-eventbridge).
- **There is no replay protection.** A captured signed request runs again if someone publishes it
  again; nothing deduplicates by event id. The only limit is `ER_MAX_REQUEST_AGE_S`, an hour by
  default.
- **The user identity is EventBridge's assertion.** `ce_submitter` is covered by the signature,
  along with `ce_submitteriss` and `ce_groupid` — but a signature only helps where something
  checks it: with request signing on **and** `ER_REQUIRE_SIGNATURE=true`, EventRunner refuses a
  request whose `ce_submitter` was altered. Even then the signature proves only that EventBridge
  asserted the name, not that the name is real. With signing off, which is the default, anything
  that can write to the topic can set it.
- **Trust in EventBridge is load-bearing.** EventRunner never contacts GitHub, and it does not act
  on the identity at all: it checks only that EventBridge signed the request. Compromising
  EventBridge therefore means being able to claim any user. This is the usual shape for a
  policy enforcement point, and the alternative — handing every runner the user's GitHub token
  — is worse, because it spreads a live credential across every workload.
- **Approval is an operator action.** The approved-user list is an env var or a `config.toml`
  entry; only the keyset is a file. Either way they say who an operator approved, not what a
  platform attested.
- **The broker connection is unprotected.** Kafka traffic in this path is plaintext, and the
  broker does not check event identity. Transport authentication would say which connection
  sent a message, not who produced its contents.
- **There is no rate limiting.** Refusing an invalid event is cheap but not free, so a flood
  still costs work. An unknown bearer token costs a GitHub call every time, because failures are
  not cached.

## Turning the controls on

Each control is off until its variable is set.

| Control | Set | Default |
| --- | --- | --- |
| User sign-in | `EB_GITHUB_CLIENT_ID` or `EB_ALLOWED_USERS`, or `client_id` / `allowed_users` under `[github]` in `eventbridge/config.toml` | Off — requests are accepted anonymously |
| Static tokens | `EB_AUTH_TOKENS`, a comma-separated list of `name:token` pairs | Off |
| Request signing | `EB_SIGNING_KEY_PATH` | Off — requests are unsigned |
| Request refusal | `ER_REQUIRE_SIGNATURE=true`, and either `ER_VERIFY_KEY_PATH` naming EventBridge's public key, or `ER_VERIFY_KEYSET_PATH` holding only that key, filed under the kid `EB_SIGNING_KID` names | Off — EventRunner runs unsigned requests |
| Response signing | `ER_SIGNING_KEY_PATH` and `ER_SIGNING_KID` on each runner | Off — responses are unsigned |
| Response verification | `EB_VERIFY_KEYSET_PATH` holding each runner's key under its `ER_SIGNING_KID` and EventBridge's own under `EB_SIGNING_KID`, plus `EB_SIGNING_KID` and `EB_SIGNING_KEY_PATH` | Off — responses are stored unchecked |
| Response refusal | `EB_REQUIRE_RESPONSE_SIGNATURE=true`, on top of response verification. Without `EB_VERIFY_KEYSET_PATH` it has no effect | Off — a keyset alone stores events unchanged and records nothing |

The `[github]` table itself is not the switch: the shipped `eventbridge/config.toml` already has
one, with `client_id = ""` and `allowed_users = []`, and sign-in is off. A non-empty value under it
is what turns sign-in on.

**The controls depend on each other. On each side, turn signing on before refusal.** If refusal is
on before the matching signer, key and kid are in place, genuine traffic is refused: on the request
side every request, and on the response side every genuine answer, which is stored as `phase=error`.
Two cases are easy to miss once refusal is on and a keyset is loaded:

- **The kid has to match.** EventRunner looks up exactly the kid EventBridge signs with; the
  single-key fallback applies only when a token names no kid. So when `EB_SIGNING_KID` is set, a
  keyset holding EventBridge's key under any other name refuses every genuine request.
- **Response verification needs EventBridge's own signing key.** EventBridge signs its group events
  only when `EB_SIGNING_KEY_PATH` gives it a seed, so without one it flags every genuine group
  event. The rewrite replaces the event's data, so the completion notification loses the real
  counts and reports the batch as `0 finished`, `ended by: no ce_signature attribute`. Nothing at
  startup checks that `EB_SIGNING_KID` is in the keyset.

Neither failure is easy to see. A refused request is never answered, and only EventRunner's log says
why. Response refusal with no keyset fails the other way: EventBridge verifies no event and stores
every one unchanged, and the startup line says
`[eventbridge] response verification OFF (set EB_VERIFY_KEYSET_PATH to enable)`. Genuine answers
keep arriving, so the deployment looks healthy while forgeries are stored as answers.

On the response side, an unsigned streamed frame still passes. Enforcement rewrites terminal events,
group events and any frame whose signature does not verify, but at this revision a rewritten group
event still takes effect.

One case to know on the sign-in side: a client id with no approved-user list refuses every GitHub
sign-in with `403`, while a request with no credential still gets `401` and a static-token holder
still gets `202`. The list on its own behaves the same as both together only while it holds a name:
EventBridge treats an empty `EB_ALLOWED_USERS` as unset, so emptying a list-only setup turns
sign-in off rather than shutting everyone out. Keeping `EB_GITHUB_CLIENT_ID` set makes an empty list
fail closed.

[The Phase 2 design record](https://github.com/rossoctl/examples/blob/main/eventing/agentdocs/DESIGN_PHASE2.md),
a draft, has the reasoning behind the design. It predates several findings on this page and does not
discuss some of these limits: where the two disagree, this page describes the code at the revision
named in the overview.

## Where this is going

The signing mechanism looks up a key by kid, as the platform's does, so that part survives a change
of trust root. The file format and the algorithm do not.

<!-- VERIFY v0.9.0: each row is design-only. SPIRE is the Phase 2 §4.3 upgrade path; the user
     registry is DESIGN_PHASE3 §2.5; the OIDC slot is Phase 3 §2.4, verified in EventBridge and
     marked not implemented there. Confirm against the epic #1460, and #2596 for the signed-events
     MVP, before claiming any of it as released. -->

| Today | Next |
| --- | --- |
| Approved keys in a file | Keys issued and rotated by SPIRE, rooted in [workload identity](../security/workload-identity.md) |
| Sign-in checked in EventBridge | An OIDC token verified at the front door |
| An approved-user list | A user registry |

For the keys row, the kid lookup does not change. The key file and the algorithm do: the keyset is a
flat JSON map of kid to key rather than a JWKS, which it rejects, and the verifier accepts EdDSA
only, while SPIRE issues EC or RSA keys rather than Ed25519.
[#2596](https://github.com/rossoctl/rossoctl/issues/2596) covers that as ES256 JWS.

The sign-in row is a larger change than it looks, and it is not an AuthBridge change today: the
Phase 3 design puts the next verifier in EventBridge rather than behind a sidecar. Moving it
behind [AuthBridge](../security/authbridge.md) would need a JWT issuer in front — AuthBridge
validates **JWTs** against a JWKS, and a GitHub token is opaque — so the sign-in verification code
changes more deeply than the keys row's does.
