# Agent Context Infrastructure

Agent Context Infrastructure is the layer that provisions, attaches, and manages the durable
context used by agents. It includes workspaces, memory, knowledge, artifacts, and related runtime
state; it is distinct from the finite context window sent to an LLM.

Rosso can optionally use [Context Service](https://github.com/rossoctl/context-service) to provide
this infrastructure. The service provisions named storage resources and attaches them to
StatefulSet or Sandbox agents. Context Service is installed separately from Rosso.

## Configure Rosso

The integration is disabled when `CONTEXT_SERVICE_URL` is empty or unset. A cluster
administrator can enable it through the Rosso Helm chart:

```yaml
# context-service-values.yaml
ui:
  backend:
    contextServiceUrl: http://context-service.serverless-harness.svc.cluster.local:8080
```

Apply the setting to an existing installation:

```sh
helm upgrade rossoctl ./charts/rossoctl \
  --namespace rossoctl-system \
  --reuse-values \
  -f context-service-values.yaml
```

The equivalent command-line override is:

```sh
helm upgrade rossoctl ./charts/rossoctl \
  --namespace rossoctl-system \
  --reuse-values \
  --set-string ui.backend.contextServiceUrl=http://context-service.serverless-harness.svc.cluster.local:8080
```

Change the value and run `helm upgrade` again to move Rosso to another Context
Service endpoint. Disable the integration by setting the value to an empty string:

```sh
helm upgrade rossoctl ./charts/rossoctl \
  --namespace rossoctl-system \
  --reuse-values \
  --set-string ui.backend.contextServiceUrl=
```

For temporary development, the backend environment can be changed directly. A later
Helm upgrade will replace this manual setting:

```sh
kubectl -n rossoctl-system set env deployment/rossoctl-backend \
  CONTEXT_SERVICE_URL=http://context-service.serverless-harness.svc.cluster.local:8080
```

## Context types

The first integration supports four classifications over the same PVC-backed storage
contract:

| Type | Intended role |
| --- | --- |
| `workspace` | Mutable files used while an agent works |
| `memory` | Durable observations and experiences |
| `knowledge` | Synthesized, reusable understanding |
| `artifacts` | Produced reports, media, and other outputs |

The type is metadata today; it does not change provisioning or lifecycle behavior.
This keeps the API shape forward-compatible without claiming type-specific semantics
before they exist.

## Workspace

A **workspace** is a durable filesystem volume mounted at a chosen path inside an
agent. Agents can use it for checked-out repositories, source files, intermediate
results, and other mutable working data. Context Service currently implements every
context type as a Kubernetes PersistentVolumeClaim (PVC), so `memory`, `knowledge`,
and `artifacts` use the same filesystem mechanism today.

### Access modes

The access mode describes where Kubernetes may mount that volume for writing:

| CLI | Kubernetes access mode | Meaning |
| --- | --- | --- |
| default | `ReadWriteOnce` (RWO) | Writable from Pods on one cluster node at a time |
| `--shared` | `ReadWriteMany` (RWX) | Writable from Pods on multiple cluster nodes concurrently |

RWO does not mean that only one Pod can access the volume, nor is it a security
boundary. Multiple Pods on the same node may be able to mount it. RWX is useful when
agents distributed across several nodes need the same files, but it requires a
storage class and CSI driver that support `ReadWriteMany`.

The storage class determines the actual storage system. For example,
`ibm-scale-csi` can provision an IBM Storage Scale filesystem-backed PVC. Context
Service exposes the Kubernetes storage contract and does not require callers to know
the CSI driver's implementation details.

## Create and attach a context

List the storage classes made available by the cluster before selecting one:

```sh
rossoctl context storage-classes
```

The command works through the authenticated Rosso API and does not require direct
Kubernetes access. The result is a constrained set of storage choices rather than
raw Kubernetes StorageClass objects. Omitting `--storage-class` uses the cluster's
default storage behavior.

Create a shared GPFS workspace and inspect it:

```sh
rossoctl context create research \
  --shared \
  --size 1Gi \
  --storage-class ibm-scale-csi

rossoctl context list
rossoctl context get research
```

Other classifications use the same storage options:

```sh
rossoctl context create research-memory --type memory --size 5Gi
rossoctl context create research-knowledge --type knowledge --shared --size 10Gi
rossoctl context create research-results --type artifacts --shared --size 20Gi
```

Attach it to a StatefulSet agent:

```sh
rossoctl agents import \
  --deployment-type statefulset \
  --context research:/workspace \
  from-image \
  --name research-agent \
  --containerImage IMAGE
```

The same context can be attached to a Sandbox agent:

```sh
rossoctl agents import \
  --deployment-type sandbox \
  --context research:/workspace \
  from-image \
  --name research-sandbox \
  --containerImage IMAGE
```

Any currently supported context type can be mounted by choosing an appropriate path,
for example `--context research-memory:/memory`. Rosso accepts the attachment only
when Context Service returns a PVC claim.

Deleting an agent does not delete its independently managed context. Delete the
context explicitly when it is no longer needed:

```sh
rossoctl agents delete research-agent
rossoctl agents delete research-sandbox
rossoctl context delete research
```

### Current usage and deletion behavior

`rossoctl context list` currently reports whether storage is provisioning or ready;
it does not report which agents mount it or an in-use count. Likewise, context
deletion does not currently prompt or reject the request when an agent uses the
volume.

Kubernetes PVC protection prevents the underlying volume from being physically
removed while a running Pod still mounts it. In that case Kubernetes may leave the
PVC in `Terminating` state after the deletion request. This is a Kubernetes safety
net, not a substitute for user-facing dependency checks. Until usage reporting and
safe deletion are implemented, delete the attached agents before deleting their
context, as shown above. Follow
[context-service#2](https://github.com/rossoctl/context-service/issues/2) for the
usage-reporting and safe-deletion design.
