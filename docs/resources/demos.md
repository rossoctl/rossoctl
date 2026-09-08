---
title: Demos
description: End-to-end scenarios you can reproduce.
sidebar_position: 2
---

Each of these is a complete, runnable scenario rather than a snippet. They are the fastest way to see a
capability working before you wire it into your own agents.

## Start here

### Weather agent

The canonical first tutorial. Deploys an agent and an MCP tool through the console, secures them with
AuthBridge, and chats with the agent end to end — including the token exchange between the two.

[Weather agent demo](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/weather-agent)

Needs a Kind cluster. See [Quickstart: Kubernetes](../get-started/kubernetes.md). You do **not** need
`--with-istio` for this one — it enforces auth through its own injected sidecar, not the mesh.

## Guardrails

### IBAC — prompt injection

The email-poisoning scenario: an agent asked to summarise emails reads one containing an injection
payload, and tries to POST data to an attacker. Shows the request succeeding without IBAC and being
denied with it.

[IBAC demo](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/ibac) ·
[IBAC docs](../guardrails/ibac.md)

### SPARC — ungrounded tool calls

A finance agent asked about a transaction it has no grounding for. Shows the model inventing a
transaction ID, and SPARC turning that into a clarifying question instead of a wrong tool call.

[SPARC demo](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/finance-sparc) ·
[SPARC docs](../guardrails/sparc.md)

### Context compaction

A finance agent whose audit-log context exceeds the model's window. Compare three modes — off, observe,
enforce — and watch the answer go from wrong to right as the context fits.

[context-guru demo](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/context-guru) ·
[Context compaction docs](../guardrails/context-compaction.md)

## Security testing

### Capture the flag

Scenarios built to demonstrate and test the platform's security posture. Run these when you want to
confirm what the guarantees actually stop, rather than take our word for it.

[capture-the-flag](https://github.com/rossoctl/capture-the-flag)

## Load and benchmarking

### Workload harness

Generates load against deployed agents, for capacity and performance work.

[workload-harness](https://github.com/rossoctl/workload-harness)

## Sample agents and tools

Not demos, but working code to copy from — agents in several frameworks and MCP tools in several
languages.

[rossoctl/examples](https://github.com/rossoctl/examples) ·
[MCP tools](https://github.com/rossoctl/examples/tree/main/mcp)

The sample agents ship `.env.openai` and `.env.ollama` files whose defaults assume the tool is in the
**same namespace** as the agent.
