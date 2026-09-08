---
title: MCP Gateway
description: Register tools once and give every agent a single MCP endpoint.
sidebar_position: 5
---

Wiring each agent to each tool does not scale: every new tool means reconfiguring every agent. The
MCP Gateway gives you one endpoint that fronts all registered tools, and prefixes their tool names so
they do not collide.

The gateway is [Kuadrant's MCP Gateway](https://github.com/Kuadrant/mcp-gateway), an Envoy-based
broker installed with `--with-mcp-gateway` (or `--with-all`).

:::info Beta
Routing and tool aggregation work. Most authentication and authorization is **not yet implemented in
the gateway** — it does not replace the per-workload checks Cortex performs. Do not treat the gateway
as your access-control boundary.
:::

## Check that it is running

Envoy, in `gateway-system`:

```bash
kubectl -n gateway-system get pods
# mcp-gateway-istio-...   1/1   Running
```

The controller, broker, and router, in `mcp-system`:

```bash
kubectl -n mcp-system get pods
# mcp-broker-router-...   1/1   Running
# mcp-controller-...      1/1   Running
```

## Register a tool

Two resources. First an `HTTPRoute` telling Envoy how to reach the tool:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: weather-tool-route
  namespace: default
  labels:
    mcp-server: "true"        # required — this is how the controller finds the route
spec:
  parentRefs:
    - name: mcp-gateway
      namespace: gateway-system
  hostnames:
    - "weather-tool.mcp.local"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: weather-tool-mcp
          port: 9090
```

The hostname matches the gateway's listener and is only used for internal routing by Envoy. It is not
a name anything resolves publicly.

Then an `MCPServerRegistration` telling the broker to include the tool:

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: weather-tool-servers
  namespace: default
spec:
  prefix: weather_            # every tool from this server is exposed as weather_<name>
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: weather-tool-route
    namespace: default
```

The prefix is what keeps two tools that both export `search` apart.

Both examples assume the tool is in `default`. Adjust the namespaces to match your deployment.

## Point agents at the gateway

Set one URL on every agent:

```
MCP_URL=http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp
```

For a running Deployment:

```bash
kubectl set env deployment/weather-service -n team1 \
  MCP_URL="http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp"
```

:::note
Once the gateway implementation stabilises this will become the default `MCP_URL`, and you will not
have to set it per agent.
:::

### Sandbox agents

`kubectl set env` does not apply to `Sandbox` objects. Patch the spec and reapply. The variable must
already exist in the container's `env` array — if it does not, add it first with
`kubectl edit sandbox weather-service -n team1`.

```bash
kubectl get sandbox weather-service -n team1 -o json \
  | jq '(.spec.podTemplate.spec.containers[]
         | select(.name == "agent").env[]
         | select(.name == "MCP_URL")).value =
        "http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp"' \
  | kubectl apply -f -
```

Because of an [upstream limitation](https://github.com/kubernetes-sigs/agent-sandbox/issues/581), the
spec change does not restart running pods. Delete the pod:

```bash
kubectl delete pod -n team1 -l app.kubernetes.io/name=weather-service
```

## Tools that need credentials

Some MCP servers require a token before they will list their tools. Give the broker one through a
labelled Secret:

```bash
kubectl create secret generic slack-server-access-token \
  --from-literal=token="Bearer $ACCESS_TOKEN" \
  --namespace default

kubectl label secret slack-server-access-token mcp.kuadrant.io/credential=true
```

Then reference it from the registration:

```yaml
spec:
  prefix: slack_
  credentialRef:
    name: slack-server-access-token
    key: token
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: slack-tool-route
    namespace: default
```

## Confirm registration

Discovery can take up to 60 seconds.

```bash
kubectl get mcpserverregistrations weather-tool-servers -o yaml
```

Look for a `Ready` condition:

```yaml
status:
  conditions:
    - type: Ready
      status: "True"
      reason: Ready
      message: MCPServerRegistration successfully reconciled and validated 1 servers with 2 tools
```

The message tells you how many servers and tools the broker actually found. If it says zero tools, the
`HTTPRoute` backend or port is wrong, or the tool needs a credential.

## Test it end to end

Open an agent's **Chat** tab and ask for something that needs a gateway-registered tool. Or port-forward
the gateway and point the MCP Inspector at it — the console's **MCP Gateway** page can launch the
Inspector for you.

## Related

- [Deploy a tool](deploy-a-tool.md).
- [Agents and tools](../concepts/agents-and-tools.md) — direct versus gateway topologies.
