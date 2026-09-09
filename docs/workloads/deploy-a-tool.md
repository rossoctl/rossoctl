---
title: Deploy a tool
description: Package an MCP tool, deploy it, and connect an agent to it.
sidebar_position: 4
---

An MCP tool gives an agent access to an external service, an interface or a set of data. The procedure
is the procedure for an agent. The differences are the ports, the registry options, and the method that
an agent uses to find the tool.

## What a tool must be

A tool is a container that uses the [MCP protocol](https://modelcontextprotocol.io) over HTTP:

| Endpoint | Method | Function |
| --- | --- | --- |
| `/mcp` | `POST` | Receives MCP messages |

The default service port is `9090`. For examples in several languages, see
[examples/mcp](https://github.com/rossoctl/examples/tree/main/mcp).

## Deploy from a container image

### With the console

Select **Tools**, then **Import new tool**, then **Deploy from existing image**. Enter the image
address, add the environment variables that the tool needs, and select **Deploy**.

### With the CLI

```bash
rossoctl tools import from-image \
  --name weather-mcp \
  --containerImage ghcr.io/acme/weather-mcp:v1.0.0

rossoctl tools wait weather-mcp
```

To set the ports, use the `--ports` option. The format is `name:port:targetPort[:protocol]`. The default
is `http:9090:9090:TCP`. A number alone means `http:<port>:<port>:TCP`.

```bash
rossoctl tools import from-image --name weather-mcp \
  --containerImage ghcr.io/acme/weather-mcp:v1.0.0 \
  --ports grpc:9000:9001:TCP,8080
```

Each other option is the option for an agent. See
[Deploy an agent](deploy-an-agent.md#deploy-from-a-container-image).

## Build from source

The requirements are the requirements for an agent: the `--with-builds` option, a GitHub repository, and
a subdirectory that contains a `Dockerfile`.

For a tool you can also select the destination of the image:

| Field | Function |
| --- | --- |
| Registry URL | Where to send the image. Use `registry.cr-system.svc.cluster.local:5000` for the registry in the cluster, or an address such as `quay.io/myorg`. |
| Registry Secret | The Kubernetes Secret that holds the registry credentials. It is necessary for an external registry. |
| Image tag | The default is `v0.0.1`. |

Rossoctl selects the build strategy from the registry, in the same way that it does for an agent.

:::note A build needs more time than the default limit
The `rossoctl tools wait` command has a default limit of 60 seconds. A build from source needs more
time. Give a longer limit:

```bash
rossoctl tools wait weather-mcp --timeout 10m
```

If the build fails, the command reports `Build Failed` and exits at once. It does not wait for the time
limit.
:::

## Connect an agent

Set `MCP_URL` on the agent to the address of the tool in the cluster:

```
MCP_URL=http://weather-tool:8080/mcp
```

For more than one tool, use `MCP_URLS` with a list that commas separate. For many tools and many
agents, use the [MCP Gateway](../concepts/experiments/mcp-gateway.md).

To change an agent that already runs:

```bash
kubectl set env deployment/weather-service -n team1 \
  MCP_URL="http://weather-tool:8080/mcp"
```

The example agents in [rossoctl/examples](https://github.com/rossoctl/examples) have an `.env.openai`
file and an `.env.ollama` file. The default values in those files assume that the tool is in the same
namespace as the agent.

## Examine a tool

```bash
rossoctl tools list
rossoctl tools list --all-namespaces
rossoctl tools get weather-mcp
rossoctl tools get weather-mcp --json
```

In the console, the **MCP Gateway** page can start the MCP Inspector for a registered tool. The Inspector
is the fastest method to read the list of functions that a tool gives.

## Delete a tool

```bash
rossoctl tools delete weather-mcp
```

An agent that has the address of that tool then fails each tool call. Change the `MCP_URL` value of each
such agent first.

## Related pages

- [MCP Gateway](../concepts/experiments/mcp-gateway.md) gives one address for all tools.
- [Agents and tools](../concepts/core/agents-and-tools.md) describes the two protocols.
