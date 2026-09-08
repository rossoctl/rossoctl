---
title: Capabilities and maturity
description: What Rossoctl guarantees today, and which capabilities are still changing.
sidebar_position: 2
---

Rossoctl ships capabilities at three maturity levels. Read this page before you build on anything.

| Level | What it means |
| --- | --- |
| **Ready** | Enabled by default, covered by end-to-end tests, and safe to depend on. |
| **Beta** | Works and is documented. The configuration surface may change between releases. |
| **Alpha** | Usable for evaluation. Behaviour and interfaces will change. Do not depend on it. |

## RossoCortex capabilities

These are enforced by the data plane on the path of every agent interaction.

| Capability | Status in 0.7 | What it does | Docs |
| --- | --- | --- | --- |
| Agent identity | **Ready** | Every agent carries a verifiable identity, so the platform knows who is acting. | [Workload identity](../security/workload-identity.md) |
| Authorization and access | **Ready** | Agents act by delegation with least privilege, never with more authority than the user and agent both hold. | [AuthBridge](../security/authbridge.md) |
| Intent-based access | Beta | Access is tied to what the user actually asked for, so a drifting agent cannot reuse its access for something else. | [IBAC](../guardrails/ibac.md) |
| Tool semantic validation | Beta | Tool calls are checked for grounding before they run, catching malformed or off-task calls. | [SPARC](../guardrails/sparc.md) |
| Failure recovery | Beta | The platform detects a stalled agent and returns it to a known state. | — |
| User interaction | Beta | A person approves high-stakes steps before the agent acts. | — |
| Context compaction | Alpha | Trims what goes into the model's context, lowering token cost. | [Context compaction](../guardrails/context-compaction.md) |
| Data-flow analysis | Alpha | Tracks where the data behind a decision came from, so provenance can gate what happens next. | — |

Capabilities with no docs link are implemented but not yet documented here. Track them in the
[cortex repository](https://github.com/rossoctl/cortex).

## Platform features

| Feature | Status | Notes |
| --- | --- | --- |
| Agent and tool deployment from image | **Ready** | UI, CLI, or `AgentRuntime` custom resource. |
| Agent and tool build from source | **Ready** | Shipwright. Needs `--with-builds` and 6 CPUs. |
| Agent discovery via A2A | **Ready** | `AgentCard` custom resource, with JWS signature verification. |
| Keycloak client registration | **Ready** | Automatic, handled by the operator. |
| Observability — traces and network topology | **Ready** | OpenTelemetry, MLflow, Kiali. |
| MCP Gateway | Beta | Routing works. Most authentication and authorization is not implemented yet. |
| Skills | Beta | Behind the `skills` feature flag. |
| Agent context — workspaces and memory | Beta | Needs Context Service, installed separately. |
| Sandboxed agents | Alpha | Uses the upstream `Sandbox` resource. Some operations need manual pod restarts. |

## Install targets

| Target | Status |
| --- | --- |
| Kind (local Kubernetes) | **Ready** — the primary development and CI target |
| OpenShift | **Ready** — tested on 4.19, CI runs against 4.20 |
| Helm / OCI charts on other clusters | Beta — works, less exercised than the two above |
| Laptop, no Kubernetes | **Ready** for traffic visibility and guardrails; no deployment or discovery |

## Getting a status corrected

If a capability behaves differently from what this page says, that is a documentation bug. Open an
issue on [rossoctl/rossoctl](https://github.com/rossoctl/rossoctl/issues) or raise it in
[Slack](https://ibm.biz/rossoctl-slack).
