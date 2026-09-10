---
title: Identity and trust
description: How a workload proves its identity, and how that identity becomes access.
sidebar_position: 4
---

The security model of Rossoctl has one basis: each workload has an identity that it can prove with
cryptography. Each access decision starts from that identity. Agents do not share secrets, and
Rossoctl does not trust a workload because the workload is in the same cluster.

Three rules follow from this basis:

- **No implicit trust.** Rossoctl authenticates and authorizes each request.
- **Least privilege.** A workload and a user receive the minimum permissions that they need.
- **Continuous verification.** Rossoctl checks the identity and the permissions at each step, not only
  at the edge of the cluster.

## Two identity systems

Rossoctl uses SPIFFE for the identity of a workload, and Keycloak for the identity of a user. Token
exchange joins the two.

| | SPIFFE and SPIRE | Keycloak |
| --- | --- | --- |
| Answers | Which workload is this? | Which user is this, and what can the user do? |
| Issues | Short-lived identity documents, automatically | OAuth2 and OIDC access tokens |
| Basis of trust | The node attests the pod | A sign-in, or a proven workload identity |

### Workload identity

[SPIFFE](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/) is a standard for the identity
of a workload. SPIRE is the program that issues and renews the identity.

Each workload receives an identity in this form:

```
spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}
```

For example: `spiffe://localtest.me/ns/team/sa/weather-tool`.

SPIRE issues the identity in two formats. An X.509 certificate is for mTLS. A JWT is for HTTP
interfaces. Both are short-lived. A helper program next to the workload renews both automatically. You
do not create a credential, and no credential waits in a Secret.

The identity comes from what the workload **is**: its namespace and its service account, which the
node attests. The identity does not come from a credential that someone gave to the workload. A
workload therefore cannot present the identity of a different workload.

### User identity

Keycloak is the identity provider. It authenticates users, issues tokens, holds the roles that define
the permissions of each user, and performs the token exchange.

Each agent and each tool is also a Keycloak client. Registration is automatic. The operator finds a
new workload, reads the administrator credentials from a Secret in its own namespace, and registers
the workload. The identifier of the client is the SPIFFE identity of the workload. You do not create
clients, and the namespace of an agent never holds administrator credentials.

## Delegation

This part is the most important part of the model.

When you ask an agent to do work, the agent must call tools as you, with your permissions and no more.
Rossoctl does this with [token exchange, RFC 8693](https://tools.ietf.org/html/rfc8693).

1. You sign in. Keycloak issues an access token that contains your roles.
2. You send a message to the agent. The message contains the token.
3. The sidecar of the agent validates the token against the public keys of Keycloak. It checks the
   signature, the issuer, the expiry time and, if you configured it, the audience. An invalid token
   receives the status 401 and does not reach the agent.
4. The agent decides to call a tool.
5. The sidecar of the agent asks Keycloak to exchange your token for a new token. The audience of the
   new token is that one tool. The sidecar authenticates this request with the SPIFFE identity of the
   agent.
6. Keycloak returns the new token. The subject of the token is you. The actor is the agent. The
   audience is the target tool.
7. The sidecar of the tool validates the new token and confirms that the audience names the tool.

The new token has this form:

```json
{
  "sub": "user-123",
  "act": { "sub": "spiffe://localtest.me/ns/team/sa/slack-researcher" },
  "aud": "slack-tool",
  "scope": "slack-full-access",
  "exp": 1735686900
}
```

Three properties come from this form:

- **The tool identifies the user.** The `sub` field names you, not the agent.
- **The agent cannot exceed you.** The `scope` field comes from your roles.
- **The token has no value elsewhere.** The `aud` field names one tool. A different tool rejects the
  token.

The `act` field gives you an audit record. Each request records the person and the workload that acted
for the person.

## What the model prevents

| Attack | Why it fails |
| --- | --- |
| An attacker replays a token from an agent at a different tool | The audience does not match. The second tool rejects the token. |
| A compromised agent tries to reach a tool that the user cannot use | Keycloak does not issue a scope that the user does not have. |
| A workload presents the identity of a different workload to get credentials | The node attests the SPIFFE identity. A workload cannot assert it. |
| An attacker uses a long-lived credential that leaked | In SPIFFE mode there is no long-lived credential. |

The model does not prevent a correctly authenticated request that the user did not ask for. An agent
that reads a document with a hidden instruction passes every check above. To reduce that risk, see
[Intent-based access](../experiments/intent-based-access.md).

## Related pages

- [Workload identity](../../security/workload-identity.md) explains how to install and check SPIRE.
- [AuthBridge](../../security/authbridge.md) describes the plugins that do this work.
- [Authentication modes](../../security/authentication-modes.md) compares client secrets and SPIFFE.
