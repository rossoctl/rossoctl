---
title: Get started
sidebar_label: Overview
description: Pick a quickstart and get a result in five or twenty minutes.
sidebar_position: 1
---

There are two ways in. Pick by how much you want to install.

## Quickstart: your laptop — about 5 minutes

One binary. No cluster, no Kubernetes, no model API key. You point your existing coding agent at it
and watch its model calls, tool calls, and agent messages as they happen.

Start with [Quickstart: your laptop](laptop.md).

Choose this if you want to see the idea working before committing to anything, or if what you care
about is traffic visibility and token cost.

## Quickstart: Kubernetes — about 20 minutes

The full platform on a local Kind cluster: the operator, Keycloak, the UI, and a sample agent and
tool. From here you can deploy your own agents, wire up MCP tools, and turn on identity.

Start with [Quickstart: Kubernetes](kubernetes.md).

Choose this if you want to deploy agents, or if you are evaluating Rossoctl as a platform.

You will need a container runtime with **18 GiB of RAM and 6 CPUs**. Less will often install but
fails when building agents from source.

## Then

1. [Configure a model](configure-a-model.md) — point agents at Ollama or a cloud provider.
2. [Deploy your first agent](first-agent.md) — the sample weather agent, end to end.
3. [Connect your first MCP tool](first-tool.md) — give the agent something to call.
4. [Install the CLI](cli.md) — do the same things from a terminal.

## Where to go after that

- Put your own agent on the platform: [Bring your own agent](../workloads/bring-your-own-agent.md).
- Turn on identity and token exchange: [Security and identity](../security/index.md).
- Install somewhere other than Kind: [Deploy and operate](../operate/index.md).
