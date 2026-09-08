---
title: Choose your path
description: Where to start in the docs, by what you are trying to do.
sidebar_position: 4
---

The sidebar is ordered by how much you have to commit: read, then run a binary, then run a cluster.
You do not have to follow it in order. Find yourself below.

## I use a coding agent and want to see what it sends

You want traffic visibility and lower token cost. You do not need Kubernetes.

1. [Quickstart: your laptop](../get-started/laptop.md) — one command, then watch the traffic.
2. [Reduce token cost](../guardrails/token-cost.md) — trim unused tool definitions and cap spend.
3. [Context compaction](../guardrails/context-compaction.md) — shrink tool output before it reaches
   the model.

## I have an agent and want to deploy it

You have working agent code and want identity, tools, and a place to run it.

1. [Quickstart: Kubernetes](../get-started/kubernetes.md) — get a cluster running.
2. [Deploy your first agent](../get-started/first-agent.md) — walk through with the sample agent.
3. [Bring your own agent](../workloads/bring-your-own-agent.md) — what your agent must expose.
4. [Connect your first MCP tool](../get-started/first-tool.md) and
   [MCP Gateway](../workloads/mcp-gateway.md).

## I run the platform for a team

You need to install Rossoctl somewhere real and keep it running.

1. [Architecture at a glance](architecture.md) — what you are about to install.
2. [Install on Kubernetes](../operate/install-kubernetes.md) or
   [Install on OpenShift](../operate/install-openshift.md).
3. [Authentication modes](../security/authentication-modes.md) — choose client secrets or SPIFFE.
4. [Observability](../operate/observability.md) and [Troubleshooting](../operate/troubleshooting.md).

## I have to sign off on the security of this

You are deciding whether agents can be allowed near your systems.

1. [Capabilities and maturity](capabilities.md) — what is actually enforced today.
2. [Security overview](../security/index.md) — the model and its four control points.
3. [Workload identity](../security/workload-identity.md) and [AuthBridge](../security/authbridge.md).
4. [Authentication flows](../security/flows.md) — the sequence diagrams.
5. [Guardrails](../guardrails/index.md) — what is available beyond authentication, and its maturity.

## I want to extend or contribute to Rossoctl

1. [RossoCortex](../concepts/cortex.md) — the plugin pipeline you would extend.
2. [Control plane and custom resources](../concepts/control-plane.md).
3. [Reference](../reference/index.md) — CLI and custom resource fields.
4. [Contributing](https://github.com/rossoctl/rossoctl/blob/main/CONTRIBUTING.md).
