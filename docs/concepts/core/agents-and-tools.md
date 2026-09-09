---
title: Agents and tools
description: What Rossoctl accepts as an agent and as a tool.
sidebar_position: 2
---

Rossoctl runs two types of workload. For each type, Rossoctl requires only a network interface. It
does not require a specific programming language or a specific agent framework.

## An agent

An agent is a container that uses the A2A protocol. The container must serve three HTTP endpoints.

| Endpoint | Method | Function |
| --- | --- | --- |
| `/.well-known/agent-card.json` | `GET` | Returns the agent card |
| `/` | `POST` | Receives a message or a task |
| `/tasks/{id}` | `GET` | Returns the status of a task |

These three endpoints are the complete requirement. Streaming is optional. If your agent supports
streaming, declare it in the agent card.

Rossoctl is neutral about frameworks because the requirement is a network interface, not a library.
Agents that use LangGraph, CrewAI, AG2, Llama Stack or BeeAI all run on Rossoctl. Agent programs such
as Claude Code also run on Rossoctl. To adapt your own agent, read
[Bring your own agent](../../workloads/bring-your-own-agent.md).

## The agent card

The agent card is a JSON document. It gives the name, the version, the address, the capabilities and
the skills of the agent. Rossoctl reads the card and stores it in an `AgentCard` resource. Rossoctl
reads the card again at a fixed interval, so the record stays correct.

You can sign the agent card. Rossoctl then validates the signature against the trust bundle of SPIRE.
Rossoctl can also read the identity of the signer from the certificate chain. This confirms that the
card comes from the workload that the card describes. If the card fails this check, the operator can
isolate the workload with a network policy. See
[identity binding](control-plane.md#identity-binding).

## A tool

A tool is a container that uses the MCP protocol. The container must serve one HTTP endpoint:

| Endpoint | Method | Function |
| --- | --- | --- |
| `/mcp` | `POST` | Receives MCP messages |

A tool makes functions, files and prompt templates available to an agent. The agent calls `tools/list`
to find what the tool offers, and then calls the function that it needs.

## How an agent finds a tool

An agent reads the address of a tool from an environment variable.

| Variable | Use it when |
| --- | --- |
| `MCP_URL` | The agent uses one tool, or the agent uses the MCP Gateway. |
| `MCP_URLS` | The agent uses more than one tool. Separate the addresses with commas. |

There are two possible arrangements.

**Direct.** Each agent holds the address of each tool. This arrangement is simple. It is correct for
one or two tools. If you add a tool, you must change each agent that needs it.

**Through the gateway.** Each agent holds one address, and that address is the MCP Gateway. Each tool
registers with the gateway one time. The gateway then gives all agents one list of tools. See
[MCP Gateway](../experiments/mcp-gateway.md).

## Why the two types are different

Rossoctl adds an agent and a tool to the platform in the same way. Both receive the same sidecar. But
an agent and a tool are at opposite ends of a chain of delegation. A user delegates work to an agent.
The agent delegates work to a tool.

The security model protects this chain. The token that an agent gives to a tool is valid only for that
tool, and it names the user. A tool can therefore identify the user, and can refuse the request if the
user does not have the necessary permission. An agent never holds a credential that belongs to a tool.
See [Identity and trust](identity.md).
