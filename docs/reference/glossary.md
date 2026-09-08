---
title: Glossary
description: The vocabulary, in one place.
sidebar_position: 5
---

## A2A

The [agent-to-agent protocol](https://a2a-protocol.org/latest/). Defines how agents advertise
themselves and exchange messages and tasks. An agent must speak A2A to run on Rossoctl. See
[Agents and tools](../concepts/agents-and-tools.md).

## Agent

A container that speaks A2A. Rossoctl does not constrain how it reasons internally. See
[Bring your own agent](../workloads/bring-your-own-agent.md).

## Agent card

A JSON document at `/.well-known/agent-card.json` describing an agent — name, version, endpoint,
capabilities, and skills. Can be signed. How discovery works.

## AgentCard

The Kubernetes custom resource caching an agent card, and recording signature and identity-binding
results. See [Custom resources](custom-resources.md#agentcard).

## Agent context

Durable storage attached to an agent: workspace, memory, knowledge, or artifacts. Not the model's
context window. Provided by Context Service. See [Agent context](../workloads/agent-context.md).

## AgentRuntime

The Kubernetes custom resource that enrols a workload into the platform. Creating one is what turns a
plain Deployment into a Rossoctl agent or tool. See
[Custom resources](custom-resources.md#agentruntime).

## Ambient mesh

Istio's sidecar-free service mesh mode, providing mTLS between workloads through the `ztunnel`
DaemonSet. Optional — `--with-istio`. Distinct from the Istio Gateway controller, which is always
installed.

## AuthBridge

The identity and access-control part of Cortex: inbound JWT validation and outbound token exchange. See
[AuthBridge](../security/authbridge.md).

## `abctl`

The Cortex viewer. Streams the traffic Cortex sees on your machine. See
[Quickstart: your laptop](../get-started/laptop.md).

## Context compaction

Shrinking tool output before it reaches a model, so a task that would overflow the context window fits.
The plugin is `context-guru`. Alpha. See [Context compaction](../guardrails/context-compaction.md).

## Cortex

See [RossoCortex](#rossocortex).

## CPEX

[CPEX](https://github.com/contextforge-org/cpex), a policy-enforcement runtime for AI agents. Cortex is
converging on it as the layer that composes verdicts from policy engines such as Cedar and OPA.

## Ext proc

Envoy's external processing filter. How the Cortex Go plugin logic hooks into the Envoy proxy.

## Feature gate

Cluster-wide policy in the `rossoctl-feature-gates` ConfigMap, controlling which Cortex components run.
Deliberately **not** overridable per namespace or per workload. See
[Custom resources](custom-resources.md#configuration-precedence).

## IBAC

Intent-Based Access Control. Denies outbound agent actions that do not match the user's most recent
declared intent, judged by a model. Beta. See [IBAC](../guardrails/ibac.md).

## Identity binding

Confirming that the SPIFFE identity which signed an agent card matches the workload the card claims to
describe. In audit mode by default; in strict mode a failure triggers network isolation. See
[Control plane](../concepts/control-plane.md#identity-binding).

## Intent

What the user asked for, extracted from inbound A2A messages by `a2a-parser` and recorded on the
session. IBAC judges actions against it.

## JWKS

JSON Web Key Set. The public keys Cortex uses to validate inbound JWT signatures. Served by Keycloak.

## Keycloak

The identity provider. Authenticates users, holds roles, issues access tokens, and performs token
exchange. Every agent and tool is also a Keycloak client, registered automatically by the operator.

## MCP

The [Model Context Protocol](https://modelcontextprotocol.io). How agents call tools. A Rossoctl tool
speaks MCP on `/mcp`.

## MCP Gateway

An Envoy-based broker giving agents one endpoint fronting all registered tools, with name prefixes to
keep them apart. Beta — most authentication in the gateway is not implemented yet. See
[MCP Gateway](../workloads/mcp-gateway.md).

## MCPServerRegistration

The custom resource registering a tool with the MCP Gateway. Paired with an `HTTPRoute`.

## Plugin

A step in a Cortex pipeline. Reads traffic, adds findings to the request context, rewrites the body, or
stops the request. See the
[plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md).

## RossoCortex

The Rossoctl data plane. Sits between an agent and everything outside it — models, tools, users, other
agents — and enforces guarantees the agent cannot give itself. Runs as a sidecar, a standalone proxy, or
a gateway. See [RossoCortex](../concepts/cortex.md).

## Shipwright

The build system Rossoctl uses to turn source in a Git repository into a container image. Needs
`--with-builds`.

## Skill

A reusable capability — instructions, scripts, configuration — stored in the cluster as a ConfigMap
labelled `rossoctl.io/type=skill` and linked to agents, rather than pasted into a prompt. Beta, behind a
feature flag. See [Skills](../workloads/skills.md).

## Skillberry store

An in-cluster registry that curates skills, with plugins that evaluate, optimise, deduplicate, and
security-scan them. Deployed by `--with-skills`.

## SPARC

Pre-tool reflection. Checks that a proposed tool call's arguments are grounded in the conversation and
the tool specification before it runs. Beta. See [SPARC](../guardrails/sparc.md).

## SPIFFE

[Secure Production Identity Framework For Everyone](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/).
The standard for workload identity Rossoctl uses. Identities look like
`spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}`.

## SPIRE

The production implementation of SPIFFE. Issues and rotates workload identities. Installed with
`--with-spire`. See [Workload identity](../security/workload-identity.md).

## SVID

SPIFFE Verifiable Identity Document. What SPIRE issues — an X.509 certificate for mTLS, or a JWT for
HTTP APIs. Short-lived and rotated automatically.

## Token exchange

[RFC 8693](https://tools.ietf.org/html/rfc8693). Swapping a user's token for one scoped to a specific
target, so an agent can act for the user without holding the target's credentials and without exceeding
the user's permissions. See [Identity and trust](../concepts/identity.md).

## Tool

A container that speaks MCP. Exposes callable functions, readable resources, and prompt templates. See
[Deploy a tool](../workloads/deploy-a-tool.md).

## Tool prune

A Cortex plugin removing tool definitions an agent will not call from inference requests — typically
4–20% of the prompt on every turn. Alpha. See [Reduce token cost](../guardrails/token-cost.md).

## Tornjak

A browsable interface for SPIRE, showing registered workloads and their identities.

## Trust domain

The root of a SPIFFE identity namespace — `localtest.me` on a default Kind install. Set with `--domain`.

## `ztunnel`

Istio ambient mesh's node-level proxy, handling mTLS between workloads. The component that needs
restarting after a long host suspend. See
[Troubleshooting](../operate/troubleshooting.md#mesh-wide-503-after-host-suspend).
