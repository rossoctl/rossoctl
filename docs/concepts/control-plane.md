---
title: Control plane and custom resources
sidebar_label: Control plane
description: What the operator does, and the two custom resources it manages.
sidebar_position: 5
---

The Rossoctl operator turns an ordinary Kubernetes workload into a platform workload. You deploy a
clean Deployment; the operator adds identity, sidecars, OAuth registration, discovery, and tracing.

Field-level detail is in the [custom resources reference](../reference/custom-resources.md). This page
explains what the resources are for.

## Enrolment

You do not annotate your Deployment with a dozen labels. You create one resource pointing at it:

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

The operator then:

1. Labels the workload `rossoctl.io/type: agent` (or `tool`) and
   `app.kubernetes.io/managed-by: rossoctl-operator`.
2. Labels the pod template, which makes the mutating webhook inject the Cortex sidecars on the next
   pod creation — the Envoy proxy, the SPIFFE helper, and client registration.
3. Registers the workload as an OAuth client in Keycloak, using its SPIFFE ID as the client
   identifier, and writes the credentials into a Secret in the workload's namespace.
4. Stamps a config hash annotation on the pod template. When the resolved configuration changes, the
   hash changes and Kubernetes performs a rolling update.
5. Creates an `AgentCard` for agents, so discovery starts.

Deleting the `AgentRuntime` removes the `managed-by` label and unenrols the workload.

When you deploy through the console or the CLI, this resource is created for you.

## Discovery

An `AgentCard` records what an agent says about itself:

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

The controller fetches `/.well-known/agent-card.json` from the agent every `syncPeriod` and caches
the result in `status.card` — name, description, version, endpoint, capabilities, and skills. That
makes agent metadata queryable with `kubectl`, and keeps the record from drifting when an agent is
redeployed.

Cards created automatically follow the pattern `{name}-{kind}-card`.

### Signature verification

An agent card may carry JWS signatures. When it does, the controller verifies them against SPIRE's
X.509 trust bundle and records the result in status:

| Field | Meaning |
| --- | --- |
| `validSignature` | The signature verified against the trust bundle. |
| `signatureSpiffeId` | The SPIFFE ID from the signature's certificate chain. |
| `signatureIdentityMatch` | Both the signature verified **and** the identity binding passed. |
| `cardId` | SHA-256 of the card content, for detecting drift. |

### Identity binding

Verifying a signature proves *someone* with a valid certificate signed the card. Identity binding
proves it was the workload the card claims to describe, by comparing the SPIFFE ID from the
certificate against the expected identity for that workload.

Two modes:

```yaml
spec:
  identityBinding:
    trustDomain: localtest.me   # overrides the operator default
    strict: false               # audit only
```

- **`strict: false`** (default) — audit. Failures are recorded in `status.bindingStatus` and nothing
  else happens.
- **`strict: true`** — enforce. A binding failure makes the operator create a NetworkPolicy that
  isolates the workload.

Start in audit mode. Turn on strict once you know your agents sign their cards correctly.

## Configuration layering

Platform configuration resolves from two ConfigMaps, most specific first:

1. **Namespace defaults** — a ConfigMap labelled `rossoctl.io/defaults=true` in the workload's
   namespace.
2. **Cluster defaults** — the `rossoctl-platform-config` ConfigMap in `rossoctl-system`.

Feature gates are separate. The `rossoctl-feature-gates` ConfigMap is platform-wide policy and
**cannot** be overridden by a namespace or by an `AgentRuntime`. It controls which Cortex components
are enabled cluster-wide and whether skill discovery is active. This is deliberate: a namespace owner
should not be able to switch off the platform's security components.

## Deployment types

An enrolled workload can be a `Deployment`, a `StatefulSet`, or a `Sandbox`.

- **Deployment** — the default. Stateless agents and tools.
- **StatefulSet** — agents that need stable storage, for example one with an attached workspace.
- **Sandbox** — stronger isolation, using the upstream
  [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) resource.

:::warning Sandbox agents behave differently
`kubectl set env` does not apply to `Sandbox` objects — you edit the spec. Because of an
[upstream limitation](https://github.com/kubernetes-sigs/agent-sandbox/issues/581), a spec change does
not restart running pods, so you have to delete the pod yourself. Sandbox support is alpha.
:::

## Other things the operator does

- **Tracing.** Discovers MLflow instances, creates a per-agent experiment, and configures the workload
  to send traces there. See [Observability](../operate/observability.md).
- **Skill discovery.** When the `skillDiscovery` feature gate is on, reads the `rossoctl.io/skills`
  annotation — a JSON array of skill names, set by the backend or by you — and resolves it into
  `status.linkedSkills`. See [Skills](../workloads/skills.md).
- **Network policy.** Creates isolating NetworkPolicies for workloads that fail identity binding in
  strict mode.

## Related

- [Custom resources reference](../reference/custom-resources.md) — every field.
- [RossoCortex](cortex.md) — what the injected sidecars do.
- [Bring your own agent](../workloads/bring-your-own-agent.md) — enrolling your own workload.
