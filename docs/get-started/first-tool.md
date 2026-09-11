---
title: Connect your first tool
description: Deploy an MCP tool and let an agent call it.
sidebar_position: 7
---

A tool gives an agent the ability to do work. A Rossoctl tool is a container that uses the
[MCP protocol](https://modelcontextprotocol.io) on the `/mcp` endpoint. This procedure deploys a tool
and connects an agent to it.

## Step 1: deploy the tool

1. In the console, select **Tools**, and then select **Import new tool**.
2. Select **Deploy from existing image**. Enter this image address:

   ```
   ghcr.io/rossoctl/examples/weather-tool:latest
   ```

3. Add the environment variables that the tool needs. An example is a key for an external service.
4. To reach the tool directly, select **Enable external access to the tool endpoint**.
5. Select **Deploy**.

Rossoctl creates a Deployment and a Service, and adds the workload to the platform in the same way that
it adds an agent.

For more tools, see
[examples/mcp](https://github.com/rossoctl/examples/tree/main/mcp).

## Step 2: give the address to an agent

An agent reads the address of a tool from an environment variable.

| Variable | Use it when |
| --- | --- |
| `MCP_URL` | The agent uses one tool, or the agent uses the MCP Gateway. |
| `MCP_URLS` | The agent uses more than one tool directly. Separate the addresses with commas. |

For a tool in the same namespace as the agent, use this value:

```
MCP_URL=http://weather-tool:8080/mcp
```

Set the variable when you deploy the agent. To change an agent that already runs, use this command:

```bash
kubectl set env deployment/weather-service -n <namespace> \
  MCP_URL="http://weather-tool:8080/mcp"
```

:::note For an agent in a sandbox
The `kubectl set env` command does not operate on a `Sandbox` resource. You must change the
specification and then delete the pod. See [Sandboxes](../concepts/experiments/sandboxes.md).
:::

## Step 3: confirm that the agent can call the tool

Open the **Chat** tab of the agent. Ask a question that only the tool can answer.

If the agent gives a correct answer, the connection operates. If the agent invents an answer, or reports
that it has no tool, the address is wrong or the tool is not ready.

Confirm that the tool runs:

```bash
kubectl get pods -n <namespace> -l app=weather-tool
```

## For many tools and many agents

One address for each pair of agent and tool does not scale. The MCP Gateway gives each agent one
address for all tools, and adds a prefix to each tool name to prevent a conflict.

See [MCP Gateway](../concepts/experiments/mcp-gateway.md).

## To build the tool from source instead

The requirements are the same as the requirements for an agent: the `--with-builds` option, a GitHub
repository, and a subdirectory that contains a `Dockerfile`. For a tool you can also select the target
registry and the image tag. See [Deploy a tool](../workloads/deploy-a-tool.md).

## Next

- [MCP Gateway](../concepts/experiments/mcp-gateway.md) registers each tool one time.
- [Install the cluster CLI](cli.md) does these tasks from a terminal.
