---
title: Bring your own agent
description: What your agent must expose to run on Rossoctl, and what you do not have to change.
sidebar_position: 2
---

Rossoctl is framework-neutral because it depends on a network contract, not a library. If your agent
meets the contract, it runs — and you do not import a Rossoctl SDK, inherit from a base class, or
change how your agent reasons.

## The contract

Your agent must be a container that serves A2A over HTTP:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/.well-known/agent-card.json` | `GET` | Returns your agent card. |
| `/` | `POST` | Accepts an A2A message or task. |
| `/tasks/{id}` | `GET` | Returns the status of a long-running task. |

That is the whole requirement. Streaming is optional; declare it in the card if you support it.

Most frameworks have an A2A server adapter, and the
[A2A specification](https://a2a-protocol.org/latest/) documents the wire format if you are writing
one yourself. Working examples for several frameworks are in
[rossoctl/examples](https://github.com/rossoctl/examples).

## The agent card

The card is how the platform and other agents discover you. A minimal one:

```json
{
  "name": "Orders agent",
  "description": "Looks up and updates customer orders.",
  "version": "1.2.0",
  "url": "http://orders.team1.svc.cluster.local:8080",
  "capabilities": { "streaming": true },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "order-lookup",
      "name": "Order lookup",
      "description": "Finds an order by ID or customer email.",
      "tags": ["orders", "read"]
    }
  ]
}
```

Rossoctl fetches this on a schedule and caches it in an
[`AgentCard` resource](../concepts/control-plane.md#discovery). Keep `version` accurate — it is how
operators tell which build is running.

You can sign the card. Signing lets the platform confirm the card came from the workload it describes,
and is required if you want to run with strict
[identity binding](../concepts/control-plane.md#identity-binding). See the
[A2A specification](https://a2a-protocol.org/latest/) section on signatures.

## Configuration your agent should read

Rossoctl passes configuration as environment variables. Read these rather than hardcoding anything:

| Variable | What to do with it |
| --- | --- |
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | Your model client's base URL, key, and model name. |
| `MCP_URL` | One MCP endpoint — a single tool, or the gateway. |
| `MCP_URLS` | Several MCP endpoints, comma-separated. |

Using these means your agent switches between Ollama, OpenAI, and any OpenAI-compatible endpoint with
no code change, and moves between direct tools and the gateway the same way. See
[Configure a model](../get-started/configure-a-model.md).

## What you do not do

**Do not implement authentication.** The Cortex sidecar validates inbound tokens before requests reach
your process. By the time your handler runs, the caller is authenticated.

**Do not manage credentials for tools.** The sidecar exchanges tokens on your behalf. Your agent calls
`http://weather-tool:8080/mcp` and the sidecar attaches a token scoped to that tool. Never put a
tool's own API key in your agent.

**Do not add tracing plumbing.** The operator configures trace export. Instrument your own spans if
you want detail, but the transport is handled.

**Do not open outbound connections that bypass the proxy.** Traffic that does not go through Cortex is
outside the security model. Respect `HTTP_PROXY` and `HTTPS_PROXY`, which most HTTP clients do by
default.

## Packaging

- A `Dockerfile` that produces a container listening on one HTTP port.
- If you want Rossoctl to build from source: the code must be on GitHub, reachable with the token
  given at install time, and in a **subdirectory** — not the repository root.
- Do not bake secrets into the image. Use environment variables backed by Kubernetes Secrets.

## Frameworks known to work

| Framework | Notes |
| --- | --- |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Used by most of the samples. |
| [CrewAI](https://www.crewai.com/) | Role-based multi-agent teams. |
| [AG2 / AutoGen](https://microsoft.github.io/autogen/) | Conversational agents. |
| [Llama Stack](https://github.com/meta-llama/llama-stack) | ReAct-style patterns. |
| [BeeAI](https://github.com/i-am-bee/bee-agent-framework) | |
| Agent harnesses — Claude Code, OpenClaw | Run behind Cortex directly; see [laptop quickstart](../get-started/laptop.md). |
| A hand-written loop | Nothing special required. Serve the three endpoints. |

This list is where samples exist, not a restriction. Anything that serves the contract works.

## Deploy it

1. Push your image, or make sure the repository is reachable.
2. Follow [Deploy an agent](deploy-an-agent.md).
3. Give it a tool: [Deploy a tool](deploy-a-tool.md) or [MCP Gateway](mcp-gateway.md).
4. Turn on identity: [Security and identity](../security/index.md).
