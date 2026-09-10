---
title: Control plane
description: What the operator does, and the two custom resources that it manages.
sidebar_position: 5
---

The operator makes a standard Kubernetes workload into a platform workload. You deploy a normal
Deployment. The operator adds the identity, the sidecars, the OAuth registration, the discovery and
the traces.

For each field of each resource, see [Custom resources](../../reference/custom-resources.md).

## How a workload joins the platform

You do not add labels to your Deployment. You create one resource that points to it:

```yaml
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: weather-agent
spec:
  type: agent            # or "tool"
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weather-agent
```

The operator then does five things:

1. It adds the label `rossoctl.io/type: agent` or `rossoctl.io/type: tool` to the workload.
2. It adds a label to the pod template. A webhook then injects the RossoCortex sidecars when
   Kubernetes next creates a pod.
3. It registers the workload as an OAuth client in Keycloak. The client identifier is the SPIFFE
   identity of the workload. The operator writes the credentials to a Secret in the namespace of the
   workload.
4. It writes a hash of the resolved configuration to the pod template. When the configuration changes,
   the hash changes, and Kubernetes starts a rolling update.
5. For an agent, it creates an `AgentCard` resource, and discovery starts.

If you delete the `AgentRuntime` resource, the operator removes the label and the workload leaves the
platform.

The web console and the CLI create this resource for you.

## Discovery

An `AgentCard` resource records what an agent says about itself:

```yaml
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentCard
metadata:
  name: weather-agent-deployment-card
spec:
  syncPeriod: 30s
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weather-agent
```

The operator reads `/.well-known/agent-card.json` from the agent at each `syncPeriod` interval. It
stores the result in the status of the resource. The status contains the name, the description, the
version, the address, the capabilities and the skills.

You can therefore query the data of an agent with `kubectl`. The record also stays correct after you
deploy the agent again.

The operator names a card that it creates automatically with this pattern: `{name}-{kind}-card`.

### Signature validation

An agent card can contain JWS signatures. The operator validates them against the X.509 trust bundle
of SPIRE, and writes the result to the status:

| Field | Meaning |
| --- | --- |
| `validSignature` | The signature is valid for the trust bundle. |
| `signatureSpiffeId` | The SPIFFE identity from the certificate chain of the signature. |
| `signatureIdentityMatch` | The signature is valid **and** the identity binding passed. |
| `cardId` | A hash of the content of the card. Use it to detect a change. |

### Identity binding

A valid signature proves that a holder of a valid certificate signed the card. Identity binding proves
that the signer is the workload that the card describes. The operator compares the identity from the
certificate with the expected identity of the workload.

There are two modes:

```yaml
spec:
  identityBinding:
    trustDomain: localtest.me   # replaces the default of the operator
    strict: false               # audit only
```

- **`strict: false` is the default.** The operator writes the result to the status. It takes no other
  action.
- **`strict: true`** makes the operator create a network policy that isolates the workload when the
  binding fails.

Start with the audit mode. Change to the strict mode after you confirm that your agents sign their
cards correctly.

## Configuration layers

The operator resolves the configuration from two ConfigMaps. The more specific layer wins.

1. **Namespace defaults.** A ConfigMap with the label `rossoctl.io/defaults=true`, in the namespace of
   the workload.
2. **Cluster defaults.** The `rossoctl-platform-config` ConfigMap, in the `rossoctl-system` namespace.

Feature gates are separate. The `rossoctl-feature-gates` ConfigMap applies to the whole cluster. A
namespace cannot replace it, and an `AgentRuntime` resource cannot replace it. It controls which
RossoCortex components run, and whether skill discovery is active. This design is deliberate: the
owner of a namespace must not be able to disable the security components of the platform.

## Deployment types

A workload in the platform can be a `Deployment`, a `StatefulSet` or a `Sandbox`.

| Type | Use it for |
| --- | --- |
| `Deployment` | Agents and tools that keep no state. This type is the default. |
| `StatefulSet` | An agent that needs durable storage. |
| `Sandbox` | An agent that needs stronger isolation. See [Sandboxes](../experiments/sandboxes.md). |

## Other operator functions

- **Traces.** The operator finds an MLflow instance, creates an experiment for each agent, and
  configures the workload to send traces there. See [Observability](../../operate/observability.md).
- **Skill discovery.** When the `skillDiscovery` feature gate is on, the operator reads the
  `rossoctl.io/skills` annotation and resolves the names into the status of the resource. See
  [Skills](../experiments/skills.md).
- **Network policy.** The operator isolates a workload that fails identity binding in the strict mode.
