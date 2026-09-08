---
title: Agent context
description: Give agents durable workspaces, memory, knowledge, and artifact storage.
sidebar_position: 7
---

Agent context is durable storage attached to an agent: files it works on, observations it keeps,
knowledge it builds, and outputs it produces. It is not the model's context window — it is the storage
that outlives a single run.

Rossoctl provides it through [Context Service](https://github.com/rossoctl/context-service), which
provisions storage and attaches it to StatefulSet or Sandbox agents.

:::info Beta — installed separately
Context Service is not part of the Rossoctl install. Deploy it first, then point Rossoctl at it.
:::

## Enable it

The integration is off while `CONTEXT_SERVICE_URL` is empty. A cluster administrator turns it on
through the chart:

```yaml
# context-service-values.yaml
ui:
  backend:
    contextServiceUrl: http://context-service.serverless-harness.svc.cluster.local:8080
```

```bash
helm upgrade rossoctl ./charts/rossoctl \
  --namespace rossoctl-system \
  --reuse-values \
  -f context-service-values.yaml
```

Or as a one-line override:

```bash
helm upgrade rossoctl ./charts/rossoctl \
  --namespace rossoctl-system --reuse-values \
  --set-string ui.backend.contextServiceUrl=http://context-service.serverless-harness.svc.cluster.local:8080
```

Disable it by setting the value to an empty string.

## Context types

Four classifications over the same storage contract:

| Type | What it is for |
| --- | --- |
| `workspace` | Mutable files the agent works on. The default. |
| `memory` | Durable observations and experiences. |
| `knowledge` | Synthesised, reusable understanding. |
| `artifacts` | Reports, media, and other outputs. |

:::note
Today the type is metadata only — every type is a PersistentVolumeClaim and behaves identically. The
distinction exists so the API stays stable when type-specific behaviour arrives. Do not expect
`memory` to do anything a `workspace` does not.
:::

## Access modes

| Flag | Kubernetes mode | Meaning |
| --- | --- | --- |
| default | `ReadWriteOnce` | Writable from pods on one node at a time. |
| `--shared` | `ReadWriteMany` | Writable from pods on several nodes at once. |

`ReadWriteOnce` is not a security boundary and does not mean only one pod can use the volume — pods on
the same node may all mount it. Use `--shared` when agents on different nodes need the same files, and
check your storage class supports `ReadWriteMany` first.

## Create a context

List what storage the cluster offers. This goes through the authenticated Rossoctl API, so you do not
need direct Kubernetes access:

```bash
rossoctl context storage-classes
```

Create one:

```bash
rossoctl context create research \
  --shared \
  --size 1Gi \
  --storage-class ibm-scale-csi

rossoctl context list
rossoctl context get research
```

Omitting `--storage-class` uses the cluster default.

Other types take the same options:

```bash
rossoctl context create research-memory    --type memory    --size 5Gi
rossoctl context create research-knowledge --type knowledge --shared --size 10Gi
rossoctl context create research-results   --type artifacts --shared --size 20Gi
```

## Attach it to an agent

Mount it at a path when you import the agent:

```bash
rossoctl agents import \
  --deployment-type statefulset \
  --context research:/workspace \
  from-image --name research-agent --containerImage IMAGE
```

Sandbox agents work the same way:

```bash
rossoctl agents import \
  --deployment-type sandbox \
  --context research:/workspace \
  from-image --name research-sandbox --containerImage IMAGE
```

Any type can be mounted at any path — `--context research-memory:/memory`, for example. Rossoctl accepts
the attachment only once Context Service returns a claim.

## Delete a context

Contexts have their own lifecycle. Deleting an agent does not delete its context:

```bash
rossoctl agents delete research-agent
rossoctl context delete research
```

Delete the agents before the context.

:::warning Deletion is not yet guarded
`rossoctl context list` reports whether storage is provisioning or ready, but not which agents mount it.
Deleting a context in use is not rejected or even flagged.

Kubernetes will not physically remove a volume a running pod mounts, so the claim sits in
`Terminating` instead. That is a safety net, not a dependency check. Track
[context-service#2](https://github.com/rossoctl/context-service/issues/2) for usage reporting and safe
deletion.
:::
