---
title: Custom resources
description: Each field of AgentRuntime and AgentCard.
sidebar_position: 3
---

Both resources use the API group `agent.rossoctl.dev` and the version `v1alpha1`. For the function of each
resource, see [Control plane](../concepts/core/control-plane.md).

The [operator API reference](https://github.com/rossoctl/operator/blob/main/operator/docs/api-reference.md)
is the source of this page. The project generates that document from the resource definitions.

## AgentRuntime

This resource adds a workload to the platform. The short names are `art` and `agentrt`.

```yaml
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: weather-agent
  namespace: team1
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weather-agent
```

### The spec fields

| Field | Type | Necessary | Function |
| --- | --- | --- | --- |
| `type` | string | Yes | `agent` or `tool`. |
| `targetRef` | [TargetRef](#targetref) | Yes | The workload that this resource configures. |

### What the operator adds to the workload

Labels on the workload:

| Label | Value |
| --- | --- |
| `rossoctl.io/type` | `agent` or `tool`, from the `spec.type` field. |
| `app.kubernetes.io/managed-by` | `rossoctl-operator`. The operator removes this label when you delete the `AgentRuntime` resource. |

Annotations on the workload:

| Annotation | Value |
| --- | --- |
| `rossoctl.io/skills` | A JSON array of skill names, for example `["weather-forecast"]`. The operator **reads** this annotation. It does not write it. The backend writes it, or you write it. The operator then writes the result to the `status.linkedSkills` field, when the `skillDiscovery` feature gate is on. |

On the pod template:

| Key | Value |
| --- | --- |
| `rossoctl.io/type`, a label | `agent` or `tool`. It marks each pod of this workload. |
| `rossoctl.io/config-hash`, an annotation | A hash of the resolved configuration. A change starts a rolling update. |

### Configuration layers

The operator calculates the hash from two ConfigMaps. The more specific layer wins.

1. **The namespace layer.** A ConfigMap with the label `rossoctl.io/defaults=true`, in the namespace of the
   workload.
2. **The cluster layer.** The `rossoctl-platform-config` ConfigMap, in the `rossoctl-system` namespace.

:::note Two items are outside the hash
The `authBridgeMode` and `mtlsMode` fields of one resource are **not** in the hash. The webhook reads them
when Kubernetes creates a pod.

The feature gates in the `rossoctl-feature-gates` ConfigMap apply to the whole cluster. A namespace cannot
replace them, and an `AgentRuntime` resource cannot replace them. They control which RossoCortex components
run, which are the proxy, the identity helper and the client registration. They also control whether skill
discovery is active.
:::

## AgentCard

This resource reads and stores the data of an agent, for discovery. The short names are `agentcards` and
`cards`.

The operator creates this resource for each agent. It uses this pattern for the name:
`{name}-{kind}-card`. A Deployment with the name `weather-agent` therefore receives a resource with the
name `weather-agent-deployment-card`.

```yaml
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentCard
metadata:
  name: weather-agent-deployment-card
  namespace: team1
spec:
  syncPeriod: 30s
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weather-agent
  identityBinding:
    trustDomain: localtest.me
    strict: false
```

### The spec fields

| Field | Type | Necessary | Function |
| --- | --- | --- | --- |
| `targetRef` | [TargetRef](#targetref) | Yes | The workload of this agent. |
| `syncPeriod` | string | No | The interval between two reads of the card. The default is `30s`. Use the Go duration format. |
| `identityBinding` | object | No | See the next table. |

#### identityBinding

| Field | Type | Function |
| --- | --- | --- |
| `trustDomain` | string | Replaces the `--spire-trust-domain` value of the operator, for this resource only. An empty value selects the value of the operator. |
| `strict` | boolean | `false`, the default, writes the result to the status only. `true` makes a failure start a network isolation. |

The operator reads the SPIFFE identity from the SAN URI of the first certificate in the `x5c` chain of the
signature.

### The status fields

| Field | Type | Function |
| --- | --- | --- |
| `card` | object | The stored agent card. See [The card data](#the-card-data). |
| `conditions` | array | The standard Kubernetes conditions for the read operation. |
| `lastSyncTime` | timestamp | The time of the last successful read. |
| `protocol` | string | The protocol that the operator found, for example `a2a`. |
| `targetRef` | TargetRef | The workload that the operator found. |
| `validSignature` | boolean | Whether the signature of the card is valid. |
| `signatureVerificationDetails` | string | A description of the last validation. |
| `signatureKeyId` | string | The `kid` value from the header of the signature. |
| `signatureSpiffeId` | string | The SPIFFE identity from the header of the signature. The operator writes this field only when the signature is valid. |
| `signatureIdentityMatch` | boolean | `true` when the signature is valid **and** the identity binding passed. |
| `cardId` | string | A hash of the content of the card. Use it to detect a change. |
| `expectedSpiffeID` | string | The identity that the operator used for the binding. |
| `bindingStatus` | object | See the next table. |

#### bindingStatus

| Field | Type | Function |
| --- | --- | --- |
| `bound` | boolean | Whether the identity is in the permitted list. |
| `reason` | string | `Bound`, `NotBound` or `AgentNotFound`. |
| `message` | string | A description. |
| `lastEvaluationTime` | timestamp | The time of the last evaluation. |

### The card data

The `status.card` field has the structure of an [A2A agent card](https://a2a-protocol.org/latest/).

| Field | Type | Function |
| --- | --- | --- |
| `name` | string | The name of the agent. |
| `description` | string | What the agent does. |
| `version` | string | The version of the agent. |
| `url` | string | The address of the agent. |
| `documentationUrl` | string | The address of the documents of the agent. |
| `iconUrl` | string | The address of an icon. |
| `provider` | object | The `organization` field and the `url` field. |
| `capabilities` | object | The `streaming`, `pushNotifications` and `extensions` fields. |
| `defaultInputModes` | []string | The media types that the agent accepts. |
| `defaultOutputModes` | []string | The media types that the agent produces. |
| `skills` | []object | See [The skills in a card](#the-skills-in-a-card). |
| `supportsAuthenticatedExtendedCard` | boolean | Whether a second card exists. |
| `signatures` | []object | The signatures, as section 8.4.2 of the A2A specification describes. |

#### capabilities.extensions

| Field | Type | Function |
| --- | --- | --- |
| `uri` | string | The identifier of the extension. |
| `description` | string | What the extension does. |
| `required` | boolean | Whether a client must support the extension. |
| `params` | object | The configuration of the extension. |

#### The skills in a card

| Field | Type | Function |
| --- | --- | --- |
| `id` | string | The identifier of the skill. |
| `name` | string | The name of the skill. |
| `description` | string | What the skill does. |
| `tags` | []string | Words that describe the type of the skill. |
| `examples` | []string | Example situations. |
| `inputModes`, `outputModes` | []string | The media types. |
| `parameters` | []object | The `name`, `type`, `description`, `required` and `default` fields. |

#### signatures

| Field | Type | Function |
| --- | --- | --- |
| `protected` | string | The protected header, in base64url. It contains the `alg`, `kid`, `typ` and `x5c` values. |
| `signature` | string | The signature, in base64url. |
| `header` | object | Optional header values, for example `timestamp`. |

## TargetRef

Both resources use this type.

| Field | Type | Necessary | Function |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | For example `apps/v1`. |
| `kind` | string | Yes | `Deployment`, `StatefulSet` or `Sandbox`. |
| `name` | string | Yes | The name of the workload. |

## Related pages

- [Control plane](../concepts/core/control-plane.md) explains the function of these resources.
- [Deploy an agent](../workloads/deploy-an-agent.md#with-a-custom-resource) shows how to use them directly.
