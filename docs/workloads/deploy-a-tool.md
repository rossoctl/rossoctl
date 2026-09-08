---
title: Deploy a tool
description: Package and deploy an MCP tool, and connect agents to it.
sidebar_position: 4
---

An MCP tool gives agents access to an external service, API, or dataset. Deploying one works like
deploying an agent — the differences are in the ports, the registry options, and how agents find it.

## What makes a tool

A container that speaks [MCP](https://modelcontextprotocol.io) over HTTP:

```
POST /mcp     # MCP JSON-RPC messages
```

The default service port is `9090`. Examples in several languages are in
[rossoctl/examples/mcp](https://github.com/rossoctl/examples/tree/main/mcp).

## From a container image

### Console

**Tools → Import new tool → Deploy from existing image.** Give it the image URI, add any environment
variables it needs, and deploy.

### CLI

```bash
rossoctl tools import from-image \
  --name weather-mcp \
  --containerImage ghcr.io/acme/weather-mcp:v1.0.0

rossoctl tools wait weather-mcp
```

Set ports with `--ports`, as `name:port:targetPort[:protocol]`. The default is
`http:9090:9090:TCP`, and a bare number means `http:<port>:<port>:TCP`:

```bash
rossoctl tools import from-image --name weather-mcp \
  --containerImage ghcr.io/acme/weather-mcp:v1.0.0 \
  --ports grpc:9000:9001:TCP,8080
```

Every other flag matches [Deploy an agent](deploy-an-agent.md#from-a-container-image).

## From source

Same requirements as agents: `--with-builds`, GitHub, and a subdirectory with a `Dockerfile`.

Tools additionally let you set where the built image goes:

| Field | Meaning |
| --- | --- |
| Registry URL | Where to push. `registry.cr-system.svc.cluster.local:5000` for the in-cluster registry, or `quay.io/myorg`. |
| Registry Secret | The Kubernetes Secret with registry credentials. Required for external registries. |
| Image tag | Defaults to `v0.0.1`. |

Build strategy is chosen from the registry, as it is for agents.

:::note Builds take longer than the default wait
`rossoctl tools wait` defaults to 60 seconds, which a source build will exceed. Allow more:

```bash
rossoctl tools wait weather-mcp --timeout 10m
```

A failed build reports `Build Failed` and ends the wait immediately rather than using the whole
timeout.
:::

## Connect an agent

Set `MCP_URL` on the agent to the tool's in-cluster address:

```
MCP_URL=http://weather-tool:8080/mcp
```

For several tools directly, use `MCP_URLS` with a comma-separated list. For many tools shared across
many agents, use the [MCP Gateway](mcp-gateway.md) instead.

Patch a running agent:

```bash
kubectl set env deployment/weather-service -n team1 \
  MCP_URL="http://weather-tool:8080/mcp"
```

The sample agents in [rossoctl/examples](https://github.com/rossoctl/examples) ship `.env.openai` and
`.env.ollama` files whose defaults assume the tool is in the **same namespace** as the agent.

## Inspect a tool

```bash
rossoctl tools list
rossoctl tools list --all-namespaces
rossoctl tools get weather-mcp
rossoctl tools get weather-mcp --json
```

In the console, the **MCP Gateway** page can launch the MCP Inspector against a registered tool, which
is the quickest way to see the tool list a tool actually advertises.

## Delete a tool

```bash
rossoctl tools delete weather-mcp
```

Agents pointing at it will start failing their tool calls. Update their `MCP_URL` first.

## Related

- [MCP Gateway](mcp-gateway.md) — one endpoint for many tools.
- [Agents and tools](../concepts/agents-and-tools.md) — the two protocols.
