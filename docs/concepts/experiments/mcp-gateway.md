---
title: MCP Gateway
description: Register each tool one time, and give every agent one address.
sidebar_position: 1
---

:::info Beta
The [Rossoctl organization](https://github.com/rossoctl) marks the MCP Gateway as experimental. It is
[Kuadrant/mcp-gateway](https://github.com/Kuadrant/mcp-gateway), which is a separate project.

Routing operates correctly. **Most authentication in the gateway is not implemented.** The gateway
does not replace the checks that the RossoCortex sidecar makes. Do not use the gateway as your access
control boundary.
:::

If each agent holds the address of each tool, you must change every agent when you add a tool. The MCP
Gateway gives you one address for all tools. It also adds a prefix to each tool name, so two tools with
the same function name do not conflict.

Install the gateway with the `--with-mcp-gateway` option, or with `--with-all`.

## Confirm that the gateway runs

Envoy runs in the `gateway-system` namespace:

```bash
kubectl -n gateway-system get pods
# mcp-gateway-istio-...   1/1   Running
```

The controller, the broker and the router run in the `mcp-system` namespace:

```bash
kubectl -n mcp-system get pods
# mcp-broker-router-...   1/1   Running
# mcp-controller-...      1/1   Running
```

## Register a tool

Create two resources. The first is an `HTTPRoute` that tells Envoy how to reach the tool:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: weather-tool-route
  namespace: default
  labels:
    mcp-server: "true"        # required: the controller uses this label to find the route
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

The host name must match the listener of the gateway. Envoy uses it for internal routing only. It is
not a name that a client can resolve.

The second resource is an `MCPServerRegistration` that tells the broker to include the tool:

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: weather-tool-servers
  namespace: default
spec:
  prefix: weather_            # each tool from this server becomes weather_<name>
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: weather-tool-route
    namespace: default
```

The prefix keeps two tools separate when both have a function with the same name.

Both examples assume that the tool is in the `default` namespace. Change the namespaces to match your
deployment.

## Point the agents at the gateway

Set one address on each agent:

```
MCP_URL=http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp
```

For a Deployment that already runs:

```bash
kubectl set env deployment/weather-service -n team1 \
  MCP_URL="http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp"
```

:::note
This address will become the default value of `MCP_URL` after the gateway is stable. You will then not
set the variable for each agent.
:::

### For an agent that runs in a sandbox

The `kubectl set env` command does not operate on a `Sandbox` resource. You must change the
specification. The variable must already exist in the `env` array of the container. If the variable is
absent, add it first with `kubectl edit sandbox weather-service -n team1`.

```bash
kubectl get sandbox weather-service -n team1 -o json \
  | jq '(.spec.podTemplate.spec.containers[]
         | select(.name == "agent").env[]
         | select(.name == "MCP_URL")).value =
        "http://mcp-gateway-istio.gateway-system.svc.cluster.local:8080/mcp"' \
  | kubectl apply -f -
```

A change to the specification does not restart a pod that runs. This is an
[upstream limitation](https://github.com/kubernetes-sigs/agent-sandbox/issues/581). Delete the pod:

```bash
kubectl delete pod -n team1 -l app.kubernetes.io/name=weather-service
```

## For a tool that needs a credential

Some MCP servers need a token before they give their list of tools. Put the token in a Secret and add
a label to the Secret:

```bash
kubectl create secret generic slack-server-access-token \
  --from-literal=token="Bearer $ACCESS_TOKEN" \
  --namespace default

kubectl label secret slack-server-access-token mcp.kuadrant.io/credential=true
```

Then name the Secret in the registration:

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

## Confirm the registration

Discovery can need as much as 60 seconds.

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

The message gives the number of servers and the number of tools that the broker found. If the message
gives zero tools, the backend or the port in the `HTTPRoute` is wrong, or the tool needs a credential.

## Test the result

Open the chat page of an agent and ask for information that needs a registered tool. You can also
forward the port of the gateway and connect the MCP Inspector to it. The **MCP Gateway** page of the
console can start the Inspector for you.
