---
title: Agent context
description: Give an agent durable storage for files, memory and results.
sidebar_position: 4
---

Agent context is durable storage that belongs to an agent. It holds the files that the agent works on,
the observations that it keeps, the knowledge that it builds and the results that it produces.

Agent context is not the context window of a model. It is storage that continues to exist after a run
ends.

:::info Beta, and a separate installation
Rossoctl provides agent context through
[Context Service](https://github.com/rossoctl/context-service). Context Service is not part of the
Rossoctl installation. Install it first, and then configure Rossoctl to use it.
:::

## Enable the integration

The integration is inactive while `CONTEXT_SERVICE_URL` is empty. A cluster administrator sets the
address in the Helm chart:

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

To disable the integration, set the value to an empty string.

## The four context types

| Type | Purpose |
| --- | --- |
| `workspace` | Files that the agent changes. This type is the default. |
| `memory` | Observations that the agent keeps. |
| `knowledge` | Understanding that the agent builds and uses again. |
| `artifacts` | Reports, media and other results. |

:::note
The type is a label only. Each type is a Kubernetes PersistentVolumeClaim, and all four types operate
in the same way today. The four names exist so that the interface stays stable when type-specific
behaviour arrives. Do not expect `memory` to do more than `workspace` does.
:::

## The two access modes

| Option | Kubernetes mode | Meaning |
| --- | --- | --- |
| default | `ReadWriteOnce` | Pods on one node at a time can write. |
| `--shared` | `ReadWriteMany` | Pods on more than one node can write at the same time. |

`ReadWriteOnce` is not a security boundary. It does not limit the volume to one pod. Pods on the same
node can all use the volume.

Use `--shared` when agents on different nodes need the same files. Confirm first that your storage
class supports `ReadWriteMany`.

## Create a context

List the storage that the cluster offers. This command uses the Rossoctl interface, so you do not need
direct access to Kubernetes:

```bash
rossoctl context storage-classes
```

Create a context:

```bash
rossoctl context create research \
  --shared \
  --size 1Gi \
  --storage-class ibm-scale-csi

rossoctl context list
rossoctl context get research
```

If you omit `--storage-class`, the command uses the default storage class of the cluster.

The other types use the same options:

```bash
rossoctl context create research-memory    --type memory    --size 5Gi
rossoctl context create research-knowledge --type knowledge --shared --size 10Gi
rossoctl context create research-results   --type artifacts --shared --size 20Gi
```

## Give a context to an agent

Name the context and the path when you import the agent:

```bash
rossoctl agents import \
  --deployment-type statefulset \
  --context research:/workspace \
  from-image --name research-agent --containerImage IMAGE
```

A sandboxed agent uses the same option:

```bash
rossoctl agents import \
  --deployment-type sandbox \
  --context research:/workspace \
  from-image --name research-sandbox --containerImage IMAGE
```

You can attach any type at any path. For example, use `--context research-memory:/memory`. Rossoctl
accepts the attachment after Context Service returns a claim.

## Delete a context

A context has its own life cycle. When you delete an agent, its context continues to exist:

```bash
rossoctl agents delete research-agent
rossoctl context delete research
```

Delete the agents before you delete the context.

:::warning Deletion has no dependency check
The `rossoctl context list` command reports whether the storage is ready. It does not report which
agents use the storage. If you delete a context that an agent uses, Rossoctl does not reject the
request and does not give a warning.

Kubernetes does not remove a volume while a pod uses it. The claim stays in the `Terminating` state
instead. That behaviour is a protection, not a dependency check. For the design of usage reporting and
safe deletion, follow
[context-service#2](https://github.com/rossoctl/context-service/issues/2).
:::
