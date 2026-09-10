---
title: Sandboxes
description: Isolate an agent more strongly than a standard pod does.
sidebar_position: 3
---

A sandbox gives an agent stronger isolation than a standard pod gives. Use a sandbox for an agent that
runs code that you do not control, or that a user supplies.

:::warning Alpha
Sandbox support is an experiment. The behaviour and the interface will change. Two operations need a
manual step, as this page describes. Do not use a sandbox in production.
:::

## What a sandbox is

Rossoctl uses the upstream
[agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) project. A `Sandbox` is a Kubernetes
resource, in the same way that a `Deployment` is a Kubernetes resource. An `AgentRuntime` resource can
point to a `Sandbox`, so a sandboxed agent joins the platform in the normal way and receives the same
RossoCortex sidecar.

The organization also has related experiments that are not part of an installation today:

| Repository | Purpose |
| --- | --- |
| [OpenShell](https://github.com/rossoctl/OpenShell) | A private runtime for an autonomous agent. This repository is a fork. |
| [openshell-driver-openshift](https://github.com/rossoctl/openshell-driver-openshift) | An OpenShell driver that creates sandboxes on OpenShift. |
| [serverless-harness](https://github.com/rossoctl/serverless-harness) | Runs an agent with no compute cost between turns, and resumes it later. |

## Deploy an agent in a sandbox

Set the deployment type when you import the agent.

With the CLI:

```bash
rossoctl agents import --deployment-type sandbox from-image \
  --name orders --containerImage ghcr.io/acme/orders:v1.2.0
```

In the console, select the sandbox type in the deployment form.

## Two limitations that you must know

### The `kubectl set env` command does not operate on a sandbox

To change an environment variable, you must change the specification of the `Sandbox` resource. This
example changes `MCP_URL`:

```bash
kubectl get sandbox weather-service -n team1 -o json \
  | jq '(.spec.podTemplate.spec.containers[]
         | select(.name == "agent").env[]
         | select(.name == "MCP_URL")).value = "http://new-address:8080/mcp"' \
  | kubectl apply -f -
```

The variable must already exist in the `env` array. If the variable is absent, add it first:

```bash
kubectl edit sandbox weather-service -n team1
```

### A change to the specification does not restart the pod

This is an [upstream limitation](https://github.com/kubernetes-sigs/agent-sandbox/issues/581). After
you change the specification, delete the pod:

```bash
kubectl delete pod -n team1 -l app.kubernetes.io/name=weather-service
```

## Related pages

- [Control plane](../core/control-plane.md#deployment-types) lists the three deployment types.
- [Agent context](agent-context.md) adds durable storage to a sandboxed agent.
