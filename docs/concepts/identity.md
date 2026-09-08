---
title: Identity and trust
description: How a workload proves who it is, and how that becomes access.
sidebar_position: 4
---

Rossoctl's security model rests on one idea: every workload has an identity it can prove
cryptographically, and every access decision starts from that identity. There are no shared secrets
passed between agents, and no implicit trust because two things run in the same cluster.

Three principles follow:

- **No implicit trust.** Every request is authenticated and authorized explicitly.
- **Least privilege.** Workloads and users get the minimum they need.
- **Continuous verification.** Identity and permissions are checked at every hop, not once at the
  edge.

## Two identity systems, two jobs

Rossoctl uses SPIFFE for workload identity and Keycloak for user identity and access, then joins them
with token exchange.

| | SPIFFE / SPIRE | Keycloak |
| --- | --- | --- |
| Answers | Which workload is this? | Which user is this, and what may they do? |
| Issues | Short-lived SVIDs, automatically | OAuth2 / OIDC access tokens |
| Trust comes from | Attestation of the pod by the node | A login, or a proven workload identity |

### Workload identity: SPIFFE and SPIRE

[SPIFFE](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/) is a standard for workload
identity. SPIRE is the implementation that issues and rotates it.

Every workload gets an identity of the form:

```
spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}
```

For example, `spiffe://localtest.me/ns/team/sa/weather-tool`.

SPIRE issues it in two formats — an X.509 certificate for mTLS, and a JWT for HTTP APIs. Both are
short-lived and rotated automatically by a helper running alongside the workload. Nothing is
provisioned by hand and nothing is stored in a Secret that could leak.

The identity is derived from what the workload *is* — its namespace and service account, attested by
the node — not from a credential it was handed. A workload cannot claim to be something else.

### User identity and access: Keycloak

Keycloak is the identity provider. It authenticates users, issues tokens, holds the roles that
define what each user may do, and performs the token exchange described below.

Every agent and tool is also a Keycloak client. Registration is automatic: the operator sees a new
workload, reads admin credentials from a Secret in its own namespace, and registers the workload
using its SPIFFE ID as the client identifier. You do not create clients by hand, and agent namespaces
never hold Keycloak admin credentials.

## Delegation: how a user's authority reaches a tool

This is the part that matters, and the part that generic platforms get wrong.

When you ask an agent to do something, the agent needs to call tools *as you* — with your
permissions, not more. Rossoctl does that with [RFC 8693 token
exchange](https://tools.ietf.org/html/rfc8693).

1. You log in. Keycloak issues you an access token carrying your roles.
2. You send a message to the agent with that token attached.
3. The agent's inbound Cortex sidecar validates it — signature, issuer, expiry, and optionally
   audience — against Keycloak's JWKS. An invalid token gets a 401 and never reaches the agent.
4. The agent decides to call a tool.
5. The agent's outbound sidecar asks Keycloak to exchange your token for one whose audience is that
   specific tool. It authenticates that request with the agent's own SPIFFE JWT.
6. Keycloak returns a new token that still names you as the subject, records the agent as the actor,
   and is scoped to the target tool.
7. The tool's inbound sidecar validates that token and confirms the audience is itself.

The resulting token looks like this:

```json
{
  "sub": "user-123",
  "act": { "sub": "spiffe://localtest.me/ns/team/sa/slack-researcher" },
  "aud": "slack-tool",
  "scope": "slack-full-access",
  "exp": 1735686900
}
```

Three properties fall out of that shape:

- **The tool knows who is really asking.** `sub` is you, not the agent.
- **The agent cannot exceed you.** The exchanged token carries a scope derived from your roles.
- **The token is useless elsewhere.** `aud` names one tool. Another tool rejects it.

And `act` gives you an audit trail: every request records both the person and the workload that
acted for them.

## What this stops

| Attack | Why it fails |
| --- | --- |
| A stolen agent token is replayed against a different tool | Audience mismatch. The second tool rejects it. |
| A compromised agent tries to reach a tool the user cannot use | Keycloak will not issue a scope the user does not hold. |
| A workload impersonates another to get credentials | SPIFFE identity is attested, not asserted. |
| A rogue workload calls an agent directly | Inbound validation rejects it without a valid token. |

What it does not stop is a *correctly authenticated request the user never asked for* — an agent that
read a poisoned document and now acts on its instructions passes every check above. That is what
[intent-based access control](../guardrails/ibac.md) is for.

## Related

- [Workload identity](../security/workload-identity.md) — SPIFFE setup and verification.
- [AuthBridge](../security/authbridge.md) — the plugins that do this work.
- [Authentication modes](../security/authentication-modes.md) — client secrets versus SPIFFE.
- [Authentication flows](../security/flows.md) — the diagrams.
