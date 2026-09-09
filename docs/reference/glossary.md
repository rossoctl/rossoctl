---
title: Glossary
description: Each term that these documents use.
sidebar_position: 5
---

## A2A

The [agent-to-agent protocol](https://a2a-protocol.org/latest/). It defines how an agent describes itself,
and how two agents exchange a message or a task. An agent must use A2A to run on Rossoctl. See
[Agents and tools](../concepts/core/agents-and-tools.md).

## abctl

The RossoCortex program for your computer. The `abctl observe` command shows the traffic that
RossoCortex reads. It is not `rossoctl`, which is the CLI for a cluster. See
[Quickstart on a laptop](../get-started/laptop.md).

## Agent

A container that uses the A2A protocol. Rossoctl does not control how the agent reasons. See
[Bring your own agent](../workloads/bring-your-own-agent.md).

## Agent card

A JSON document at `/.well-known/agent-card.json`. It gives the name, the version, the address, the
capabilities and the skills of an agent. It can contain a signature. Rossoctl uses it for discovery.

## AgentCard

The Kubernetes resource that stores an agent card, and the result of each signature check and identity
check. See [Custom resources](custom-resources.md#agentcard).

## Agent context

Durable storage that belongs to an agent. It holds files, memory, knowledge or results. It is not the
context window of a model. Context Service provides it. See
[Agent context](../concepts/experiments/agent-context.md).

## AgentRuntime

The Kubernetes resource that adds a workload to the platform. When you create this resource, a standard
Deployment becomes a Rossoctl agent or a Rossoctl tool. See
[Custom resources](custom-resources.md#agentruntime).

## Alpha

A maturity level. You can evaluate the feature. The behaviour and the interface will change. Do not depend
on it. See [Concepts](../concepts/index.md#maturity-levels).

## Ambient mesh

The mode of Istio that gives mTLS between workloads without a sidecar. The `ztunnel` DaemonSet provides
it. The `--with-istio` option installs it. It is different from the Istio gateway controller, which
Rossoctl always installs.

## AuthBridge

The identity and access control part of RossoCortex. It validates each token that arrives, and exchanges
each token that leaves. See [AuthBridge](../security/authbridge.md).

## Beta

A maturity level. The feature operates and this site documents it. The configuration can change in a later
release. See [Concepts](../concepts/index.md#maturity-levels).

## Context compaction

A method that makes tool output smaller before a model reads it. A task with more output than the context
window then completes. The plugin is `context-guru`. See
[Context compaction](../concepts/experiments/context-compaction.md).

## Core

The features that every Rossoctl installation uses. Each core feature is ready for production use. The
[Rossoctl organization](https://github.com/rossoctl) marks each repository as core or experimental.

## Cortex

See [RossoCortex](#rossocortex).

## CPEX

[CPEX](https://github.com/contextforge-org/cpex) is a policy runtime for AI agents. RossoCortex is moving
to CPEX for the layer that combines the results of policy engines such as Cedar and OPA.

## Experiment

A feature that is not ready for production use. Each experiment page gives the maturity level of the
feature. See [Concepts](../concepts/index.md).

## Ext proc

The external processing filter of Envoy. RossoCortex uses it to add its Go logic to the Envoy proxy.

## Feature gate

A setting in the `rossoctl-feature-gates` ConfigMap. It applies to the whole cluster. A namespace cannot
replace it, and a workload cannot replace it. See
[Custom resources](custom-resources.md#configuration-layers).

## IBAC

See [Intent-based access](#intent-based-access).

## Identity binding

A check that the SPIFFE identity that signed an agent card is the identity of the workload that the card
describes. The default mode writes the result to the status. The strict mode starts a network isolation
after a failure. See
[Control plane](../concepts/core/control-plane.md#identity-binding).

## Intent

The request of a user. The `a2a-parser` plugin reads it from a message and records it. The intent-based
access plugin compares each action with it.

## Intent-based access

A method that denies an outbound action that does not match the most recent request of the user. A model
makes the comparison. The plugin is `ibac`. See
[Intent-based access](../concepts/experiments/intent-based-access.md).

## JWKS

A JSON Web Key Set. It contains the public keys that RossoCortex uses to validate the signature of a
token. Keycloak provides it.

## Keycloak

The identity provider. It authenticates users, holds the roles, issues access tokens and exchanges tokens.
Each agent and each tool is also a Keycloak client, and the operator registers each one automatically.

## MCP

The [Model Context Protocol](https://modelcontextprotocol.io). An agent uses MCP to call a tool. A
Rossoctl tool uses MCP on the `/mcp` endpoint.

## MCP Gateway

A proxy that gives each agent one address for all tools. It adds a prefix to each tool name, to prevent a
conflict. Most authentication in the gateway is not implemented. See
[MCP Gateway](../concepts/experiments/mcp-gateway.md).

## MCPServerRegistration

The resource that registers a tool with the MCP Gateway. It has an `HTTPRoute` resource with it.

## Plugin

A step in a RossoCortex chain. It can read the traffic, add data to a shared record, change the content, or
stop the request. See the
[plugin catalogue](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md).

## Ready

A maturity level. Rossoctl enables the feature by default, tests cover it, and you can depend on it. See
[Concepts](../concepts/index.md#maturity-levels).

## RossoCortex

The data plane of Rossoctl. It is a proxy between an agent and each external service, which are models,
tools, users and other agents. It runs as a sidecar, as a local proxy or as a gateway. See
[RossoCortex](../concepts/core/cortex.md).

## Sandbox

A Kubernetes resource that gives an agent stronger isolation than a pod gives. Rossoctl uses the upstream
agent-sandbox project. See [Sandboxes](../concepts/experiments/sandboxes.md).

## Shipwright

The system that Rossoctl uses to make a container image from source code. It needs the `--with-builds`
option.

## Skill

A reusable capability that contains instructions, scripts and configuration. The cluster holds it as a
ConfigMap with the label `rossoctl.io/type=skill`. You give a skill to an agent instead of a copy of the
instructions in a prompt. See [Skills](../concepts/experiments/skills.md).

## Skillberry store

A registry in the cluster that manages a set of skills. It has plugins that evaluate, improve, remove
duplicates from and examine each skill. The `--with-skills` option installs it.

## SPARC

See [Tool call validation](#tool-call-validation).

## SPIFFE

[Secure Production Identity Framework For Everyone](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/).
The standard that Rossoctl uses for the identity of a workload. An identity has this form:
`spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}`.

## SPIRE

The program that implements SPIFFE. It issues and renews the identity of each workload. The `--with-spire`
option installs it. See [Workload identity](../security/workload-identity.md).

## SVID

A SPIFFE Verifiable Identity Document. SPIRE issues one. An X.509 document is for mTLS. A JWT document is
for an HTTP interface. Both are short-lived and SPIRE renews both automatically.

## Token exchange

The method that [RFC 8693](https://tools.ietf.org/html/rfc8693) describes. It replaces the token of a user
with a token that is valid only for one target. An agent can therefore act for a user without a credential
of the target, and without more permissions than the user has. See
[Identity and trust](../concepts/core/identity.md).

## Tool

A container that uses the MCP protocol. It makes functions, files and prompt templates available to an
agent. See [Deploy a tool](../workloads/deploy-a-tool.md).

## Tool call validation

A method that denies a tool call with an invented argument, or with an incorrect choice of tool. The plugin
is `sparc`. See [Tool call validation](../concepts/experiments/tool-validation.md).

## Tool prune

A plugin that removes the definition of each tool that an agent does not call. Those definitions are 4
percent to 20 percent of the prompt on each turn. See
[Cost control](../concepts/experiments/cost-control.md).

## Tornjak

A browser interface for SPIRE. It shows the registered workloads and the identity of each one.

## Trust domain

The first part of a SPIFFE identity. On a default Kind installation it is `localtest.me`. The `--domain`
option sets it.

## ztunnel

The node-level proxy of the Istio ambient mesh. It gives mTLS between workloads. You must restart it after
you suspend a computer for a long period. See
[Troubleshooting](../operate/troubleshooting.md#a-cluster-returns-503-after-you-suspend-the-computer).
