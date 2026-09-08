---
title: Agents and tools
description: What Rossoctl treats as an agent and a tool, and the protocols that define them.
sidebar_position: 2
---

Rossoctl runs two kinds of workload. It does not care how either one is written — only what it
exposes over the network.

## An agent

An agent is a container that speaks **A2A**, the [agent-to-agent protocol](https://a2a-protocol.org/latest/).
That means two endpoints:

```
GET  /.well-known/agent-card.json   # who I am and what I can do
POST /                              # send me a message or a task
GET  /tasks/{id}                    # how is that task going
```

Anything satisfying that contract is an agent as far as Rossoctl is concerned. The reasoning inside
is yours.

Because the contract is a network contract, Rossoctl is framework-neutral in practice rather than as
a claim. Agents built with LangGraph, CrewAI, AG2, Llama Stack, and BeeAI all run on it, as do agent
harnesses like Claude Code and hand-written loops over the OpenAI or MCP SDKs.

See [Bring your own agent](../workloads/bring-your-own-agent.md) for what this means for your code.

### The agent card

The agent card is how discovery works. It is a JSON document describing the agent's name, version,
endpoint, capabilities, and the skills it offers. Rossoctl fetches it, caches it in an
[`AgentCard` resource](control-plane.md#discovery), and re-fetches it on a schedule so the record
does not drift from reality.

Cards can be signed. Rossoctl verifies JWS signatures against SPIRE's trust bundle, and can extract
the signer's SPIFFE identity from the certificate chain to confirm the card came from the workload
it claims to describe. When a card fails that check, the operator can isolate the workload with a
NetworkPolicy — see [strict mode](control-plane.md#identity-binding).

## A tool

A tool is a container that speaks **MCP**, the [Model Context Protocol](https://modelcontextprotocol.io),
on one endpoint:

```
POST /mcp                           # MCP JSON-RPC messages
```

Tools expose callable functions, readable resources, and prompt templates. An agent discovers what a
tool offers by calling `tools/list`, then invokes what it needs.

## How they find each other

An agent learns about tools from its environment:

| Variable | Meaning |
| --- | --- |
| `MCP_URL` | One tool, or the MCP Gateway fronting many. |
| `MCP_URLS` | Several tools, directly, comma-separated. |

Two topologies:

**Direct.** The agent holds each tool's address. Simple, and fine for one or two tools. Every new
tool means reconfiguring every agent that needs it.

**Through the gateway.** Every agent points `MCP_URL` at the MCP Gateway. Tools register themselves
with the gateway once, and the gateway presents their combined tool list under name prefixes that
keep them apart. See [MCP Gateway](../workloads/mcp-gateway.md).

## Why the distinction matters

Agents and tools are enrolled the same way and get the same Cortex sidecar, but they sit on opposite
ends of a delegation chain. A user delegates to an agent; the agent delegates to a tool.

That chain is what the security model protects. The token an agent presents to a tool is scoped to
that tool and carries the original user's identity, so a tool can tell who is ultimately asking and
refuse if that person lacks permission. An agent never holds a tool's own credentials.

See [Identity and trust](identity.md).

## Skills

A skill is a reusable capability an agent can draw on — instructions, scripts, and configuration
stored in the cluster and linked to agents, rather than pasted into a prompt. Skills are stored as
ConfigMaps labelled `rossoctl.io/type=skill` and managed through the platform API.

Skills are behind a feature flag. See [Skills](../workloads/skills.md).
