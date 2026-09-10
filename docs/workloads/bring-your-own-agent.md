---
title: Bring your own agent
description: The requirements for your agent, and what you do not have to change.
sidebar_position: 2
---

Rossoctl is neutral about frameworks because it requires a network interface, not a library. If your
agent meets the requirements below, it runs on Rossoctl. You do not import a Rossoctl library, you do
not inherit from a Rossoctl class, and you do not change how your agent reasons.

## The requirements

Your agent must be a container that serves the A2A protocol over HTTP:

| Endpoint | Method | Function |
| --- | --- | --- |
| `/.well-known/agent-card.json` | `GET` | Returns your agent card. |
| `/` | `POST` | Receives an A2A message or task. |
| `/tasks/{id}` | `GET` | Returns the status of a task. |

These three endpoints are the complete requirement. Streaming is optional. If your agent supports
streaming, declare it in the card.

Most frameworks have an A2A server component. The
[A2A specification](https://a2a-protocol.org/latest/) gives the message format if you write your own.
[rossoctl/examples](https://github.com/rossoctl/examples) contains an example for each of several
frameworks.

## The agent card

The platform and other agents use the card to find your agent. This example is a minimal card:

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

Rossoctl reads this card at a fixed interval and stores it in an
[`AgentCard` resource](../concepts/core/control-plane.md#discovery). Keep the `version` field correct.
An operator uses that field to identify the build that runs.

You can sign the card. A signature lets the platform confirm that the card comes from the workload that
the card describes. A signature is necessary for the strict
[identity binding](../concepts/core/control-plane.md#identity-binding) mode. For the format, see the
section on signatures in the [A2A specification](https://a2a-protocol.org/latest/).

## The variables that your agent must read

Rossoctl gives the configuration to your agent in environment variables. Read these variables. Do not
put a fixed value in your code.

| Variable | Use it for |
| --- | --- |
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | The address, the key and the name of the model. |
| `MCP_URL` | One MCP address. It is one tool, or the gateway. |
| `MCP_URLS` | More than one MCP address. Separate them with commas. |

If your agent reads these variables, you can change the model between Ollama, OpenAI and any compatible
endpoint with no change to the code. You can also change between direct tools and the gateway in the
same way. See [Configure a model](../get-started/configure-a-model.md).

## What you must not do

**Do not add authentication code.** The RossoCortex sidecar validates each token before the request
reaches your program. When your code runs, the caller is authenticated.

**Do not hold a credential for a tool.** The sidecar exchanges the token for you. Your agent calls
`http://weather-tool:8080/mcp`, and the sidecar adds a token that is valid only for that tool. Never put
a key that belongs to a tool in your agent.

**Do not add code to send traces.** The operator configures the trace destination. You can add your own
spans for detail, but the transport is present.

**Do not open a connection that avoids the proxy.** Traffic that does not pass through RossoCortex is
outside the security model. Read the `HTTP_PROXY` and `HTTPS_PROXY` variables. Most HTTP libraries read
them automatically.

## How to package the agent

- Write a `Dockerfile` that produces a container. The container must listen on one HTTP port.
- For a build from source, put the code on GitHub, in a **subdirectory** that contains the `Dockerfile`.
  The code must not be in the root directory. The repository must be reachable with the token that you
  gave to the installer.
- Do not put a secret in the image. Use an environment variable and a Kubernetes Secret.

## Frameworks with an example

| Framework | Notes |
| --- | --- |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Most of the samples use this framework. |
| [CrewAI](https://www.crewai.com/) | For a group of agents with roles. |
| [AG2, formerly AutoGen](https://microsoft.github.io/autogen/) | For agents that hold a conversation. |
| [Llama Stack](https://github.com/meta-llama/llama-stack) | For the ReAct pattern. |
| [BeeAI](https://github.com/i-am-bee/bee-agent-framework) | — |
| Agent programs such as Claude Code | These run behind RossoCortex directly. See [Quickstart on a laptop](../get-started/laptop.md). |
| Your own loop | No framework is necessary. Serve the three endpoints. |

This table lists the frameworks that have an example. It is not a limit. Any program that serves the
three endpoints operates.

## Next

1. Push your image, or confirm that Rossoctl can reach your repository.
2. Follow [Deploy an agent](deploy-an-agent.md).
3. Give the agent a tool. See [Deploy a tool](deploy-a-tool.md).
4. Enable identity. See [Security](../security/index.md).
