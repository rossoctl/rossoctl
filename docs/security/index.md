---
title: Security overview
sidebar_label: Overview
description: What Rossoctl enforces, where it enforces it, and what it does not cover.
sidebar_position: 1
---

Everything in this section is **Ready**: enabled by default, tested end to end, and safe to depend on.
Optional guardrails at earlier maturity live in [Guardrails and efficiency](../guardrails/index.md).

If you are reviewing Rossoctl for approval, read these four pages in order and you will have the whole
picture:

1. This page — the model.
2. [Workload identity](workload-identity.md) — where identity comes from.
3. [AuthBridge](authbridge.md) — what enforces it.
4. [Authentication flows](flows.md) — the sequence diagrams.

## The model

Rossoctl assumes an attacker may already be inside the cluster. Nothing is trusted for being local:
not another agent, not a tool, not the network between them. Every request is authenticated and
authorized on its own merits.

Three commitments follow:

- **Every workload has a provable identity.** Issued by SPIRE, derived from what the workload is,
  rotated automatically. Not a credential someone handed it.
- **Agents act by delegation.** An agent calling a tool for you carries your identity and a token
  scoped to that tool. It never holds the tool's own secrets, and it can never exceed what you and it
  both hold.
- **Enforcement sits outside the agent.** It is in the sidecar, so it does not depend on the agent
  behaving, being well written, or even being code you wrote.

## Where enforcement happens

Each enrolled workload has a Cortex sidecar controlling four points:

| Point | What is checked |
| --- | --- |
| Inbound request | Caller identity. Token signature, issuer, expiry, audience. |
| Outbound request | Whether this agent, acting for this user, may reach this target. Token exchanged for the target. |
| Outbound response | Whether the reply is trying to take over the calling agent. |
| Inbound response | Whether the reply returns data this user should not see. |

Points 1 and 2 are enforced by default. Points 3 and 4 are where the optional
[guardrail plugins](../guardrails/index.md) act.

See [RossoCortex](../concepts/cortex.md) for the mechanism.

## The pieces

| Component | Role |
| --- | --- |
| **SPIFFE / SPIRE** | Issues and rotates workload identity. |
| **Keycloak** | Authenticates users, holds roles, issues and exchanges tokens. |
| **Cortex sidecar** | Validates inbound tokens, exchanges outbound ones, runs plugins. |
| **Rossoctl operator** | Registers OAuth clients, injects sidecars, verifies agent cards. |
| **Istio ambient mesh** | mTLS between workloads. Optional — `--with-istio`. |
| **Kubernetes RBAC and NetworkPolicy** | Cluster-level authorization and isolation. |

## What this stops

| Attack | Why it fails |
| --- | --- |
| An unauthenticated caller reaches an agent | Inbound validation rejects it with a 401. |
| A stolen agent token is replayed at another tool | The audience names one tool. Others reject it. |
| A compromised agent reaches a tool the user cannot use | Keycloak will not issue a scope the user does not hold. |
| A workload impersonates another to obtain credentials | SPIFFE identity is attested by the node, not asserted by the workload. |
| A tampered agent card claims false capabilities | JWS signature verification against SPIRE's trust bundle, and optional identity binding. |
| A leaked long-lived credential is used later | There are none to leak in SPIFFE mode; SVIDs are short-lived and rotated. |

## What this does not stop

Be clear about the boundary.

- **A correctly authenticated request the user never asked for.** An agent that read a poisoned
  document produces a perfectly valid request. Authentication cannot tell the difference. That is what
  [intent-based access control](../guardrails/ibac.md) addresses, at beta.
- **A hallucinated but well-formed tool call.** See [SPARC](../guardrails/sparc.md), at beta.
- **Traffic that bypasses the sidecar.** An agent that opens a connection outside its proxy is outside
  the model.
- **Anything the user is genuinely allowed to do.** Delegation is faithful. If a user may delete
  production data, an agent acting for that user may too. Scope user roles accordingly.
- **The MCP Gateway is not an access-control boundary yet.** Most authentication in the gateway is not
  implemented. Keep per-workload enforcement on.

## Configure it

- [Authentication modes](authentication-modes.md) — client secrets or SPIFFE. Choose SPIFFE if you have
  SPIRE.
- [Workload identity](workload-identity.md) — verify SPIRE is working.
- [AuthBridge](authbridge.md) — what the sidecar does and how to inspect it.
