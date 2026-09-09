---
title: Security
sidebar_label: Overview
description: What Rossoctl enforces, where it enforces it, and what it does not cover.
sidebar_position: 1
---

Each feature in this section is **Ready**. Rossoctl enables it by default, tests cover it, and you can
depend on it. The optional controls at an earlier maturity level are in
[Experiments](../concepts/index.md#experimental-features).

If you must approve Rossoctl for use, read these four pages in order:

1. This page, for the model.
2. [Workload identity](workload-identity.md), for the source of each identity.
3. [AuthBridge](authbridge.md), for the component that enforces the model.
4. [Authentication flows](flows.md), for the diagrams.

## The model

Rossoctl assumes that an attacker can be inside the cluster. It does not trust a component because that
component is local. It does not trust another agent, a tool, or the network between them. It
authenticates and authorizes each request separately.

Three commitments follow:

- **Each workload has an identity that it can prove.** SPIRE issues the identity. The identity comes
  from what the workload is, and Rossoctl renews it automatically. It is not a credential that someone
  gave to the workload.
- **An agent acts by delegation.** An agent that calls a tool for you presents your identity, and a
  token that is valid only for that tool. It never holds a credential that belongs to the tool, and it
  never has more permissions than you have.
- **The enforcement is outside the agent.** It is in the sidecar. It therefore does not depend on the
  behaviour or the quality of the code of the agent.

## Where Rossoctl enforces the model

Each workload in the platform has a RossoCortex sidecar that controls four points.

| Point | What Rossoctl checks |
| --- | --- |
| Inbound request | The identity of the caller. The signature, the issuer, the expiry time and the audience of the token. |
| Outbound request | Whether this agent can reach this target for this user. It also exchanges the token for the target. |
| Outbound response | Whether the reply contains an attempt to control the agent. |
| Inbound response | Whether the reply contains data that the user must not receive. |

Rossoctl enforces points 1 and 2 by default. The optional plugins act on points 3 and 4. See
[Experiments](../concepts/index.md#experimental-features).

For the mechanism, see [RossoCortex](../concepts/core/cortex.md).

## The components

| Component | Function |
| --- | --- |
| **SPIFFE and SPIRE** | Issues and renews the identity of each workload. |
| **Keycloak** | Authenticates users, holds the roles, issues tokens and exchanges tokens. |
| **The RossoCortex sidecar** | Validates each token that arrives, exchanges each token that leaves, and runs the plugins. |
| **The operator** | Registers the OAuth clients, injects the sidecars and validates the agent cards. |
| **The Istio ambient mesh** | Adds mTLS between the workloads. It is optional: `--with-istio`. |
| **Kubernetes RBAC and network policies** | Controls access at the level of the cluster. |

## What the model prevents

| Attack | Why it fails |
| --- | --- |
| An unauthenticated caller sends a request to an agent | The sidecar rejects the request with the status 401. |
| An attacker replays a token from an agent at a different tool | The audience of the token names one tool. A different tool rejects it. |
| A compromised agent tries to reach a tool that the user cannot use | Keycloak does not issue a scope that the user does not have. |
| A workload presents the identity of a different workload | The node attests the SPIFFE identity. A workload cannot assert an identity. |
| An agent card declares capabilities that the agent does not have | Rossoctl validates the signature against the trust bundle of SPIRE, and can also check the identity binding. |
| An attacker uses a long-lived credential that leaked | In SPIFFE mode there is no long-lived credential. The identity documents are short-lived. |

## What the model does not prevent

You must know the limits of the model.

- **A correctly authenticated request that the user did not ask for.** An agent that reads a document
  with a hidden instruction produces a valid request. Authentication cannot detect the difference. See
  [Intent-based access](../concepts/experiments/intent-based-access.md), which is an alpha feature.
- **A tool call with an invented argument.** See
  [Tool call validation](../concepts/experiments/tool-validation.md), which is an alpha feature.
- **Traffic that avoids the sidecar.** An agent that opens a connection outside its proxy is outside the
  model.
- **An action that the user is permitted to do.** The delegation is exact. If a user can delete
  production data, an agent that acts for that user can also delete it. Give each user the minimum roles
  that the user needs.
- **The MCP Gateway is not an access control boundary.** Most authentication in the gateway is not
  implemented. Keep the enforcement in each sidecar active. See
  [MCP Gateway](../concepts/experiments/mcp-gateway.md).

## Configure the model

- [Authentication modes](authentication-modes.md) compares client secrets and SPIFFE. Select SPIFFE if
  you install SPIRE.
- [Workload identity](workload-identity.md) shows how to confirm that SPIRE operates.
- [AuthBridge](authbridge.md) describes the sidecar and how to examine it.
