# Context Service

Rosso can optionally use [Context Service](https://github.com/rossoctl/context-service)
to provision named storage resources and attach them to StatefulSet or Sandbox agents.
Context Service is installed separately from Rosso.

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

## Create and attach a context

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
