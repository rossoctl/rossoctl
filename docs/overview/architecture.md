---
title: Architecture at a glance
description: The components of a Rossoctl cluster and how a request flows through them.
sidebar_position: 3
---

A Rossoctl cluster has four layers: the workloads you deploy, the data plane beside them, the
control plane that manages them, and the infrastructure they all rely on.

![Rossoctl architecture: components and their deployment namespaces within a Kubernetes cluster](../images/architecture.svg)

## Workloads

**Agents** are containers that expose the A2A protocol. They serve an agent card at
`/.well-known/agent-card.json` and accept messages at `/`. Rossoctl does not care how the agent
reasons internally.

**Tools** are containers that expose MCP at `/mcp`. Agents call them directly or through the
MCP Gateway.

Both are ordinary Kubernetes Deployments (or StatefulSets, or Sandboxes). What makes them
Rossoctl workloads is an `AgentRuntime` custom resource pointing at them.

## Data plane — RossoCortex

Every enrolled workload gets a Cortex sidecar injected next to it. The sidecar is an Envoy proxy
plus a Go extension processor, and it handles traffic in both directions:

- **Inbound** — validates the caller's JWT against Keycloak's JWKS. Invalid tokens get a 401 and
  never reach your agent.
- **Outbound** — exchanges the agent's token for one scoped to the target it is calling, then
  applies whichever guardrail plugins you have enabled.

The sidecar also runs a SPIFFE helper that keeps the workload's identity documents fresh, and a
client-registration step that registers the workload with Keycloak.

See [RossoCortex](../concepts/cortex.md) for the request path in detail.

## Control plane

**The operator** (`rossoctl-operator`) watches `AgentRuntime` and `AgentCard` resources. It labels
workloads, injects the Cortex sidecars through a mutating webhook, registers OAuth clients in
Keycloak, fetches and verifies agent cards, and configures tracing. See
[Control plane and custom resources](../concepts/control-plane.md).

**The backend and UI** (`rossoctl-backend`, `rossoctl-ui`) give you a REST API and a web
console for importing agents and tools, chatting with them, and viewing traces. The
[CLI](../reference/cli.md) talks to the same API.

**The MCP Gateway** brokers tool traffic. Register a tool once with an `HTTPRoute` and an
`MCPServerRegistration`, and every agent can reach it through a single URL. See
[MCP Gateway](../workloads/mcp-gateway.md).

## Infrastructure

| Component | Role | Required? |
| --- | --- | --- |
| cert-manager | Certificates for webhooks and gateways | Always installed |
| Gateway API + Istio Gateway controller | Ingress for the UI, Keycloak, and agents | Always installed |
| Keycloak | Identity provider, OAuth2 tokens, token exchange | Always installed |
| SPIRE | Issues SPIFFE identities to workloads | `--with-spire` |
| Istio ambient mesh | mTLS between workloads | `--with-istio` |
| Shipwright + Tekton | Builds agents and tools from source | `--with-builds` |
| OpenTelemetry collector | Collects traces | `--with-otel` |
| MLflow | Trace backend | `--with-mlflow` |
| Kiali + Prometheus | Network topology and metrics | `--with-kiali` |

:::note
The Istio Gateway controller and the Istio ambient mesh are two different things. The Gateway
controller is core and always installed — it serves all `*.localtest.me:8080` ingress. The
ambient mesh (`--with-istio`) adds mTLS between workloads and is optional.
:::

## How a request flows

A user asks an agent to do something, and the agent calls a tool:

1. The user logs in to the UI. Keycloak issues an access token.
2. The UI sends an A2A message to the agent, carrying that token.
3. The agent's inbound Cortex sidecar validates the token. If it is bad, the request stops here.
4. The agent reasons, and decides to call a tool.
5. The agent's outbound Cortex sidecar exchanges the user's token for one scoped to that tool, then
   runs any enabled guardrail plugins. A plugin may block the call.
6. The tool's inbound sidecar validates the exchanged token and checks that the audience is itself.
7. The tool runs and responds. The response travels back through both sidecars.

The user's identity is carried through the whole chain, and no step holds more authority than the
user and the agent both have. See [Authentication flows](../security/flows.md) for the diagrams.
