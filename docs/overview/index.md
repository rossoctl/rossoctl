---
title: What is Rossoctl?
sidebar_label: What is Rossoctl?
description: The problem Rossoctl solves and the three parts it is built from.
sidebar_position: 1
---

Rossoctl is an open-source platform for deploying, securing, and governing AI agents. It is
framework-neutral: agents built with LangGraph, CrewAI, AG2, or a hand-written loop all run on it,
as do agent harnesses like Claude Code. It is built on two open standards — [A2A](https://a2a-protocol.org/latest/)
for agent-to-agent communication and [MCP](https://modelcontextprotocol.io) for tools.

## The problem

AI agents are not ordinary cloud applications. They pick their tools at runtime, treat data and
instructions as the same thing, drift from the task they were given, and cannot reliably report
what they actually did.

Kubernetes separated application logic from the guarantees production needs — admission, isolation,
failure recovery. Agents need the same separation. The guarantees have to hold no matter which
framework wrote the agent, which means they cannot live inside the agent's code.

## Three parts

**RossoCortex** is the data plane. It sits between an agent and everything outside it: models,
tools, users, and other agents. From that one position it enforces the guarantees an agent cannot
give on its own — identity, access control, and inspection of what passes through. Agents connect
to it through an SDK, harness hooks, a proxy, or a gateway. See [RossoCortex](../concepts/cortex.md).

**Services** are the building blocks agents need to do real work: skills, tools, memory, knowledge,
and sandboxes. They are provided by the platform rather than assembled per agent.

**Tooling** covers the rest of running agents in production: observability, security, governance,
and administration — the UI, the CLI, and the Kubernetes operator.

## What that gets you

- **A verifiable identity per agent.** Every workload gets a SPIFFE identity from SPIRE, so the
  platform knows who is acting before it decides what they may do.
- **Delegated access, not shared secrets.** An agent calling a tool on your behalf gets a token
  scoped to that tool and to your permissions. It never holds the tool's own credentials.
- **Deployment without rewriting your agent.** Point Rossoctl at a container image or a Git
  repository. It builds, deploys, enrols, and exposes the agent.
- **A record of what happened.** Traces, network topology, and token cost per agent.

## Two ways to run it

Rossoctl runs at two very different scales, and you do not have to start with the larger one.

| | On your laptop | On Kubernetes |
| --- | --- | --- |
| What you install | One binary | The full platform |
| Time to first result | ~5 minutes | ~20 minutes |
| What you get | Traffic visibility, identity, guardrails, cost control for a local agent | Everything, plus deployment, discovery, the UI, and the MCP Gateway |
| Start at | [Quickstart: your laptop](../get-started/laptop.md) | [Quickstart: Kubernetes](../get-started/kubernetes.md) |

## Next

- [Capabilities and maturity](capabilities.md) — what is ready to depend on today.
- [Architecture at a glance](architecture.md) — the components and how they connect.
- [Choose your path](choose-your-path.md) — a route through the docs for your role.
