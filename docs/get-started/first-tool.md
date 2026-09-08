---
title: Connect your first MCP tool
description: Deploy an MCP tool and let an agent call it.
sidebar_position: 6
---

Tools give agents something to do. A Rossoctl tool is a container that speaks
[MCP](https://modelcontextprotocol.io) on `/mcp`. This deploys one and connects an agent to it.

## Deploy the tool

1. In the console, go to **Tools** and choose **Import new tool**.
2. Select **Deploy from existing image** and give it an image URI. For the sample:

   ```
   ghcr.io/rossoctl/examples/weather-tool:latest
   ```

3. Add any environment variables the tool needs — an upstream API key, for example.
4. Tick **Enable external access to the tool endpoint** if you want to reach it directly.
5. Choose **Deploy**.

Rossoctl creates a Deployment and a Service, and enrols the workload the same way it does an agent.

Browse [rossoctl/examples/mcp](https://github.com/rossoctl/examples/tree/main/mcp) for more tools.

## Point an agent at it

Agents find tools through environment variables:

| Variable | Use it when |
| --- | --- |
| `MCP_URL` | The agent uses one tool, or reaches tools through the MCP Gateway. |
| `MCP_URLS` | The agent connects directly to several tools. Comma-separated. |

For a tool in the same namespace as the agent:

```
MCP_URL=http://weather-tool:8080/mcp
```

Set this when you deploy the agent, or patch a running one:

```bash
kubectl set env deployment/weather-service -n <namespace> \
  MCP_URL="http://weather-tool:8080/mcp"
```

:::note Sandbox agents
`kubectl set env` does not work on `Sandbox` resources. Edit the `Sandbox` spec instead, then delete
the pod to force a restart. See [MCP Gateway](../workloads/mcp-gateway.md#sandbox-agents).
:::

## Check that the agent can call it

Open the agent's **Chat** tab and ask something only the tool can answer. If the agent answers
correctly, the connection works. If it makes something up or says it has no tools, the URL is wrong
or the tool is not ready.

Check the tool is running:

```bash
kubectl get pods -n <namespace> -l app=weather-tool
```

## Reaching several tools through one URL

Wiring each agent to each tool does not scale. The MCP Gateway gives you one endpoint that fronts
every registered tool, and lets you prefix tool names to avoid collisions.

See [MCP Gateway](../workloads/mcp-gateway.md).

## Build from source instead

The same rules as agents: GitHub, a subdirectory, a `Dockerfile`, and `--with-builds` at install
time. Tools additionally let you set the target registry and image tag. See
[Deploy a tool](../workloads/deploy-a-tool.md).

## Next

- [MCP Gateway](../workloads/mcp-gateway.md) — register tools centrally.
- [Install the CLI](cli.md) — do all of this from a terminal.
