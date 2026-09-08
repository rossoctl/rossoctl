---
title: Custom resources
description: AgentRuntime and AgentCard field reference.
sidebar_position: 3
---

Both resources are in API group `agent.rossoctl.dev`, version `v1alpha1`. For what they are for, see
[Control plane](../concepts/control-plane.md).

The authoritative source is the
[operator API reference](https://github.com/rossoctl/operator/blob/main/operator/docs/api-reference.md),
generated from the CRD schemas.

## AgentRuntime

Enrols a workload into the platform. Short names: `art`, `agentrt`.

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

### Spec

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | `agent` or `tool`. |
| `targetRef` | [TargetRef](#targetref) | Yes | The workload this runtime configures. |

### What it applies to the target

Labels on the workload:

| Label | Value |
| --- | --- |
| `rossoctl.io/type` | `agent` or `tool`, from `spec.type`. |
| `app.kubernetes.io/managed-by` | `rossoctl-operator`. Removed when the `AgentRuntime` is deleted. |

Annotations on the workload:

| Annotation | Value |
| --- | --- |
| `rossoctl.io/skills` | A JSON array of skill names, for example `["weather-forecast"]`. **Read** by the operator, not set by it — the backend or you set it. Populates `status.linkedSkills` when the `skillDiscovery` feature gate is on. |

On the pod template:

| Key | Value |
| --- | --- |
| `rossoctl.io/type` (label) | `agent` or `tool`. Classifies pods this workload spawns. |
| `rossoctl.io/config-hash` (annotation) | SHA-256 of the resolved configuration. A change triggers a rolling update. |

### Configuration precedence

The controller computes the config hash from two layers, highest priority first:

1. **Namespace defaults** — a ConfigMap labelled `rossoctl.io/defaults=true` in the workload's namespace.
2. **Cluster defaults** — the `rossoctl-platform-config` ConfigMap in `rossoctl-system`.

:::note Two things are outside that hash
Per-resource overrides (`authBridgeMode`, `mtlsMode`) are **not** in the controller's config hash — the
webhook reads them at pod creation time instead.

Feature gates (`rossoctl-feature-gates`) are platform-wide policy and **cannot** be overridden by
namespace defaults or by an `AgentRuntime`. They control which Cortex components are enabled globally —
the Envoy proxy, the SPIFFE helper, client registration — and whether `skillDiscovery` is active.
:::

## AgentCard

Fetches and caches agent metadata for discovery. Short names: `agentcards`, `cards`.

Created automatically for agents, named `{name}-{kind}-card` — so a Deployment called `weather-agent`
gets `weather-agent-deployment-card`.

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

### Spec

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `targetRef` | [TargetRef](#targetref) | Yes | The workload backing this agent. |
| `syncPeriod` | string | No | How often to re-fetch the card. Default `30s`. Go duration format. |
| `identityBinding` | object | No | See below. |

#### identityBinding

| Field | Type | Description |
| --- | --- | --- |
| `trustDomain` | string | Overrides the operator's `--spire-trust-domain` for this card. Empty means use the operator's value. |
| `strict` | boolean | `false` (default) records binding results in status only. `true` makes a binding failure trigger network isolation. |

The SPIFFE ID is extracted from the leaf certificate's SAN URI in the signature's `x5c` chain during
verification.

### Status

| Field | Type | Description |
| --- | --- | --- |
| `card` | object | The cached agent card. See [Card data](#card-data). |
| `conditions` | array | Standard Kubernetes conditions for the indexing process. |
| `lastSyncTime` | timestamp | When the card was last fetched successfully. |
| `protocol` | string | Detected protocol, for example `a2a`. |
| `targetRef` | TargetRef | The resolved workload reference. |
| `validSignature` | boolean | Whether the card's JWS signature is valid. |
| `signatureVerificationDetails` | string | Human-readable detail about the last verification. |
| `signatureKeyId` | string | The `kid` from the JWS protected header. |
| `signatureSpiffeId` | string | SPIFFE ID from the JWS protected header. Set only when the signature is valid. |
| `signatureIdentityMatch` | boolean | `true` when signature verification **and** identity binding both pass. |
| `cardId` | string | SHA-256 of the card content, for drift detection. |
| `expectedSpiffeID` | string | The SPIFFE ID used for binding evaluation. |
| `bindingStatus` | object | See below. |

#### bindingStatus

| Field | Type | Description |
| --- | --- | --- |
| `bound` | boolean | Whether the verified SPIFFE ID is in the allowlist. |
| `reason` | string | `Bound`, `NotBound`, or `AgentNotFound`. |
| `message` | string | Human-readable description. |
| `lastEvaluationTime` | timestamp | When binding was last evaluated. |

### Card data

`status.card` mirrors the [A2A agent card](https://a2a-protocol.org/latest/) structure.

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Human-readable name. |
| `description` | string | What the agent does. |
| `version` | string | Agent version. |
| `url` | string | Where the agent can be reached. |
| `documentationUrl` | string | Link to the agent's own docs. |
| `iconUrl` | string | Link to an icon. |
| `provider` | object | `organization` and `url`. |
| `capabilities` | object | `streaming`, `pushNotifications`, and `extensions`. |
| `defaultInputModes` | []string | Media types accepted. |
| `defaultOutputModes` | []string | Media types produced. |
| `skills` | []object | See [Skills](#skills-in-a-card). |
| `supportsAuthenticatedExtendedCard` | boolean | Whether an extended card exists. |
| `signatures` | []object | JWS signatures, per A2A section 8.4.2. |

#### capabilities.extensions

| Field | Type | Description |
| --- | --- | --- |
| `uri` | string | Unique identifier for the extension. |
| `description` | string | What it does. |
| `required` | boolean | Whether a client must support it. |
| `params` | object | Extension-specific configuration. |

#### Skills in a card

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique identifier. |
| `name` | string | Skill name. |
| `description` | string | What it does. |
| `tags` | []string | Keywords describing the class of capability. |
| `examples` | []string | Sample scenarios. |
| `inputModes` / `outputModes` | []string | Media types. |
| `parameters` | []object | `name`, `type`, `description`, `required`, `default`. |

#### signatures

| Field | Type | Description |
| --- | --- | --- |
| `protected` | string | Base64url JWS protected header — contains `alg`, `kid`, `typ`, `x5c`. |
| `signature` | string | Base64url signature value. |
| `header` | object | Optional unprotected header parameters, for example `timestamp`. |

## TargetRef

Shared by both resources.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | For example `apps/v1`. |
| `kind` | string | Yes | `Deployment`, `StatefulSet`, or `Sandbox`. |
| `name` | string | Yes | Name of the target. |

## Related

- [Control plane](../concepts/control-plane.md) — what these resources do.
- [Deploy an agent](../workloads/deploy-an-agent.md#with-custom-resources) — using them directly.
