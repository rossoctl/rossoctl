---
title: GitHub OAuth App
description: Register the OAuth App that lets a user sign in to the eventing demo.
sidebar_position: 2
---

:::warning Alpha

Sign-in is off by default, and EventBridge then accepts every request anonymously. The variables on
this page turn it on for the two routes that start work, `POST /v0/agents` and `POST /v0/groups`.
Every other route stays open, including `/continue`, which also runs the agent; see
[What these controls do not prove](identity.md#what-these-controls-do-not-prove).

:::

The eventing path can identify the person who submits a request by signing them in with GitHub.
This page registers the OAuth App that makes that possible. You do it once per environment.

## Why an app is needed

Sign-in uses the OAuth **device flow**, which requires a `client_id`. The user never types a
password into the CLI. The CLI prints a short code, the user enters it on a GitHub page, and
GitHub returns a token to the CLI.

The `client_id` is **public**, so you can commit it. Device flow needs **no client secret** —
do not generate one.

## Register the app

1. Open your [GitHub developer settings](https://github.com/settings/developers), select **OAuth Apps**, then
   **New OAuth App** (**Register a new application** if you have none yet). For a shared
   environment, use the organization page instead:
   `https://github.com/organizations/<org>/settings/applications`.
2. Complete the form:

   | Field | Value |
   | --- | --- |
   | Application name | `Rossoctl Eventing Demo` |
   | Homepage URL | `https://github.com/rossoctl/rossoctl` |
   | Authorization callback URL | `https://github.com/rossoctl/rossoctl` |

   Device flow never redirects, but the form requires a callback URL.

   Tick **Enable Device Flow** on this same form. Without it, GitHub refuses the first step with
   `device_flow_disabled`. At the revision [the overview](index.md) names, the CLI does not show
   that reason: it stops with a Python traceback ending in `HTTP Error 400: Bad Request`.
   <!-- VERIFY v0.9.0: drop the traceback sentence once rossoctl/examples#887 lands and _post_form
        reads the error body. -->


   Untick **Expire user access tokens**, which GitHub ticks by default. With it ticked, access
   tokens expire after 8 hours and nothing in this path refreshes them, so every user has to run
   `login` again. Leave it ticked only if you would rather have the expiry and accept the
   re-login.
3. Select **Register application**.
4. Copy the **Client ID**. It looks like `Ov23li...`.

## Configure EventBridge

```bash
export EB_GITHUB_CLIENT_ID=Ov23li...
export EB_ALLOWED_USERS="alice,bob,carol"
```

`EB_ALLOWED_USERS` is the approved list. A valid GitHub user who is absent from it receives
`403` rather than `401`: authenticated, but not authorized.

Setting either variable turns sign-in on. The two are not symmetric:

- **A client id with no list** refuses every GitHub sign-in with `403`. A request with no
  credential still gets `401`, and a static-token holder still gets `202`.
- **The list on its own** behaves like both together only while it holds a name. EventBridge treats
  an empty `EB_ALLOWED_USERS` as unset, so keep `EB_GITHUB_CLIENT_ID` set on EventBridge too: with
  it, an empty list refuses every GitHub sign-in. Without it, an empty list turns sign-in off: if
  `EB_AUTH_TOKENS` has an entry that parses, only its holders get in, and otherwise every request is
  accepted anonymously again.

A static `EB_AUTH_TOKENS` entry bypasses the list entirely — see the break-glass path in
[Identity in the event path](identity.md#which-person-asked-for-this).

On Kubernetes, EventBridge reads the whole `eventing-config` ConfigMap through `envFrom`; the
shipped one just does not set these keys. Add them to it and restart the pod, or run
`kubectl -n kev1 set env deploy/eventbridge EB_GITHUB_CLIENT_ID=… EB_ALLOWED_USERS=…` — `kev1` is
the namespace the shipped overlays use. Both replace the pod; see the warning under
[Revoke access](#revoke-access).

**Keep each variable in one place.** `kubectl set env` writes an `env:` entry, and an `env:` entry
overrides the value that arrives through `envFrom`. If you set `EB_GITHUB_CLIENT_ID` or
`EB_ALLOWED_USERS` that way and later change it in the ConfigMap, the ConfigMap's value is ignored
and the old one still applies — nothing reports the shadowed value. Other keys set this way behave
the same; note that the optional `eventbridge-ntfy` Secret is listed after the ConfigMap in
`envFrom`, so its `NTFY_ENABLED` already overrides the ConfigMap's.

Keep `EB_AUTH_TOKENS`, a comma-separated list of `name:token` pairs on one line, in a Secret. The name is what
lands in `ce_submitter`. The Deployment's only shipped Secret source is `eventbridge-ntfy`, so add
one, and name the key `EB_AUTH_TOKENS`, because the key becomes the variable name:

```bash
kubectl -n kev1 create secret generic eventbridge-auth --from-file=EB_AUTH_TOKENS=./auth-tokens
kubectl -n kev1 set env deploy/eventbridge --from=secret/eventbridge-auth
```

Use `--from-file` rather than `--from-literal`, which would put the credential in `argv`. A trailing
newline in the file is harmless, and so is a newline after a comma. A newline *in place of* a comma
joins the two pairs on either side into one, and both of those holders get `401`. Delete the file
once the Secret exists. The second command replaces the pod too.

**EventBridge does not bind tokens to this app.** `EB_GITHUB_CLIENT_ID` is only an on-switch
there. EventBridge calls `GET /user` with whatever token arrives, so any GitHub token belonging
to an approved login is accepted — a PAT, `gh auth token`, or a broadly scoped token held by
another app. Binding the token to one app would require the client secret that device flow
exists to avoid, so this is a limit to know rather than a setting to change.

## Scopes

The CLI requests **no scopes** — it hard-codes an empty scope, so there is nothing for you to
set. `GET /user` returns the login with an unscoped token, so the path asks for the least access
that works and still gets a verified identity.

This is CLI behaviour, not something EventBridge enforces: per the limit above, it accepts a
broadly scoped token just as readily.

## Sign in

There is no installed `login` command. The CLI imports `eventbridge.ghauth` from the checkout, so
run it from your clone of [`rossoctl/examples`](https://github.com/rossoctl/examples). The package
declares `requires-python = ">=3.14"`, so use a Python at that version or later; macOS's stock
`/usr/bin/python3` is older. The `login` path itself needs no virtual environment, because `ghauth`
imports only the standard library.

```bash
cd eventing && python3 skills/eventbridge/eventbridge-cli.py login --client-id Ov23li...
```

```text
$ python3 skills/eventbridge/eventbridge-cli.py login --client-id Ov23li...
· endpoint http://127.0.0.1:8080 (from default)

  Open https://github.com/login/device
  Enter code: WDJB-MJHT

  Waiting for you to authorise in the browser (Ctrl-C to abort)...
✔ signed in as alice
  token stored at /home/alice/.config/rossoctl-eventing/token (mode 600)
```

The token is written to `$XDG_CONFIG_HOME/rossoctl-eventing/token`, falling back to `~/.config`
when `XDG_CONFIG_HOME` is unset, with mode `0600`. Every later request sends it as
`Authorization: Bearer <token>`.

A few things worth knowing:

- **Pass the client id.** The CLI reads `--client-id` or `$EB_GITHUB_CLIENT_ID` from your own
  shell. With neither it silently uses a built-in demo app, and EventBridge accepts that token
  too, so nothing reveals the mistake — but your app's settings do not apply, the user must revoke
  a different app, and all such users share its 50-per-hour code limit.
- **Where requests go.** `login` and `whoami` talk only to GitHub, and `logout` to nothing. Every
  other command sends to `--base-url`, else `$EVENTBRIDGE_URL`, else `http://127.0.0.1:8080`.
- `$EVENTBRIDGE_TOKEN` overrides the stored token, and the CLI sends it to EventBridge on every
  request — so pointing it at a broad PAT hands that token to EventBridge.
- `logout` forgets the local token. It does **not** revoke it on GitHub.

## Limits

| Limit | Value |
| --- | --- |
| Device code lifetime | 15 minutes |
| Poll interval | As returned by GitHub, plus 5 seconds after a `slow_down` response |
| `GET /user` rate limit | 5000 per hour per user |
| Code submissions | 50 per hour per app |

The 50-per-hour limit counts browser code submissions across **all** users of one app, which is
worth knowing for a shared demo app at a workshop or conference.

EventBridge caches the mapping from token to login, keyed by a hash of the token, so repeated
requests with one token cost one API call per cache entry, per EventBridge process. Requests that
arrive together before the first lookup returns each call GitHub, because nothing merges concurrent
lookups. Failed lookups are not cached, so an unknown token costs a call every time.

## Revoke access

A user revokes at [their GitHub applications page](https://github.com/settings/applications).
A revoked token keeps working until its cached entry expires: up to `EB_GITHUB_CACHE_TTL_S`,
300 seconds by default. After that, *starting* work returns `401`.

To remove someone, take their name out of `EB_ALLOWED_USERS` **where you set it** — the ConfigMap or
the `env:` entry, not whichever you reach for first — and restart EventBridge. If that empties the
list, sign-in stays on only when `EB_GITHUB_CLIENT_ID` is also set on EventBridge. Without it, an
empty list turns sign-in off: if `EB_AUTH_TOKENS` has an entry that parses, only its holders get in,
and otherwise every request is accepted anonymously again. To remove a static-token holder, take the
entry out of `EB_AUTH_TOKENS` and restart; the approved-user list does not affect them. If that
removes the last entry while sign-in is off, every request is accepted anonymously again. Either way
the pod is replaced — see the warning below.

Neither revocation nor removal closes everything. As
[Identity in the event path](identity.md#what-these-controls-do-not-prove) explains, only starting
work is authenticated, so either user can still continue any conversation they can name — and the
member ids of the 100 most recent groups are listable without signing in.

:::warning

On the base, kind and test manifests EventBridge's store is an `emptyDir` and the Deployment uses
the `Recreate` strategy. **Anything that replaces the pod discards the agents' answers:**
`kubectl rollout restart`, `kubectl set env`, or any other change to the pod template. EventBridge
reads these variables only when its process starts, and each of those commands replaces the pod.
The responses consumer has already committed its offsets, so the answers are not replayed. Prompts
and groups *are* rebuilt from what Kafka still holds — 24 hours on the Strimzi topics — so an
earlier conversation comes back with its questions and no answers, and `/continue` on it returns
`404`. Only the demo overlay adds a PVC.

Turn sign-in on, and change the approved-user list, before a session whose transcripts you want to
keep.

:::
