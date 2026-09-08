---
title: RossoCortex
sidebar_label: RossoCortex
description: The data plane — where it sits, what it controls, and how its plugin pipeline works.
sidebar_position: 3
---

RossoCortex is the Rossoctl data plane. It is an intercept: it sits between an agent and everything
outside it — models, tools, users, and other agents — and from that one position enforces guarantees
the agent cannot give on its own.

The point of intercepting rather than integrating is that the guarantees do not depend on the agent's
code. An agent you did not write, cannot modify, or do not trust gets the same treatment as one you
built yourself.

![RossoCortex overview: agents reach a common interface through an SDK, hooks, a gateway, or orchestration; capabilities such as AuthBridge identity and access control, IBAC, SPARC, and context-guru run as plugins](../images/rossocortex-overview.svg)

## Where it runs

Cortex is one binary with several deployment shapes:

| Shape | Where | Used for |
| --- | --- | --- |
| **Sidecar** | Beside each workload in a pod | The standard Kubernetes deployment. Injected by the operator. |
| **Standalone proxy** | On your machine | [Laptop use](../get-started/laptop.md) — `abctl`, or `rossoctl authbridge exec`. |
| **Gateway** | In front of a group of workloads | Shared enforcement for traffic that has no sidecar. |

In Kubernetes the sidecar is an Envoy proxy plus a Go extension processor. Envoy moves the bytes; the
processor holds the logic.

## Four points of control

Cortex separates requests from responses, in both directions. That gives four distinct control
points around every workload:

```
 ┌────────┐  1. inbound request   ┌──────────────────────────┐  2. outbound request  ┌──────────────┐
 │        │ ────────────────────► │ CORTEX ┌───────┐ CORTEX  │ ────────────────────► │              │
 │ CALLER │                       │ inbound│ AGENT │ outbound│                       │ TARGET AGENT │
 │        │ ◄──────────────────── │        └───────┘         │ ◄──────────────────── │   OR TOOL    │
 └────────┘  4. inbound response  └──────────────────────────┘  3. outbound response └──────────────┘
```

1. **Inbound request** — traffic arriving at the agent. Cortex verifies the caller's identity and
   that the request belongs to a task from a user with the right role.
2. **Outbound request** — traffic the agent initiates. Cortex checks that the agent, acting for this
   user, may reach this target, and that the content does not leak sensitive data.
3. **Outbound response** — the reply to something the agent asked for. Cortex checks the reply is not
   an attempt to take over the calling agent.
4. **Inbound response** — the agent's reply to its caller. Cortex checks it does not return data this
   user should not see.

Most platforms only guard point 1. Points 2 and 3 are where agent-specific risks live: an agent that
read a poisoned document and is now acting on its instructions produces a perfectly authenticated
outbound request that nobody asked for.

## The plugin pipeline

Each of those four points runs an ordered chain of plugins. A plugin can read the traffic, add
findings to a shared request context, rewrite the body, or stop the request.

The default pipeline handles authentication and delegation:

| Plugin | Point | What it does |
| --- | --- | --- |
| `jwt-validation` | Inbound request | Validates the JWT's signature, issuer, and audience against Keycloak's JWKS. Returns 401 on failure. |
| `token-exchange` | Outbound request | Performs [RFC 8693](https://tools.ietf.org/html/rfc8693) token exchange, so the agent presents a token scoped to the target it is calling. |

Everything else is opt-in. Parsers (`a2a-parser`, `mcp-parser`, `inference-parser`) decode traffic
into structured context so later plugins can reason about it. Guardrails
([`ibac`](../guardrails/ibac.md), [`sparc`](../guardrails/sparc.md)) and efficiency plugins
([`context-guru`](../guardrails/context-compaction.md), `tool-prune`) act on that context.

See [Guardrails and efficiency](../guardrails/index.md) for what is available and its maturity, and
the [plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md)
for configuration of each one.

## Authentication and authorization are different decisions

The pipeline treats them differently on purpose.

**Authentication** — is this identity real? A missing or cryptographically invalid token is rejected
immediately, at the edge. There is nothing to deliberate about, and failing fast protects the
platform from having to process junk.

**Authorization** — should this identity be allowed to do this? Here plugins are meant to *report*
rather than block. A plugin that finds a problem records it in the request context, and a single
decision point evaluates all the findings together.

The reason is operational. A single user task can produce dozens of requests across an agent graph.
If every plugin at every control point could independently drop traffic, a cluster would have
thousands of scattered enforcement decisions and no one place to look when a task breaks. Reporting
into a shared context keeps the decision — and the audit record — in one place.

Cortex is converging on [CPEX](https://github.com/contextforge-org/cpex) for that decision layer,
composing verdicts from policy engines such as Cedar and OPA. The capabilities above stay the same
whichever engine hosts them.

## What Cortex does not do

- It does not make your agent smarter or change how it reasons.
- It does not replace your agent framework. It sits beneath your agent, not in place of it.
- It does not secure traffic that bypasses it. An agent that talks to the outside world without going
  through its proxy is outside the model.

## Related

- [Identity and trust](identity.md) — where the identities Cortex checks come from.
- [AuthBridge](../security/authbridge.md) — the identity and access plugins in detail.
- [Authentication flows](../security/flows.md) — sequence diagrams of the full path.
