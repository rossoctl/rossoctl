---
title: AuthBridge
description: The identity and access layer of Cortex — inbound validation and outbound token exchange.
sidebar_position: 3
---

AuthBridge is the identity and access-control part of [RossoCortex](../concepts/cortex.md). It is what
makes an agent's calls authenticated and correctly scoped without the agent doing anything about it.

Two plugins do the work, and both are on by default:

| Plugin | Direction | What it does |
| --- | --- | --- |
| `jwt-validation` | Inbound | Validates the caller's JWT — signature via JWKS, issuer, and optionally audience. Returns 401 on failure. |
| `token-exchange` | Outbound | Exchanges the agent's token for one scoped to the target it is calling, per [RFC 8693](https://tools.ietf.org/html/rfc8693). |

## What gets injected

When the operator enrols a workload, the mutating webhook adds three containers to its pod:

| Container | Job |
| --- | --- |
| `authbridge-proxy` | Envoy plus a Go extension processor. Runs the inbound and outbound pipelines. |
| `spiffe-helper` | Keeps the workload's SVIDs fresh on disk. |
| client registration | Registers the workload with Keycloak on startup. |

Your agent container is untouched.

## The path a request takes

![AuthBridge architecture: the operator registers the workload with Keycloak, the agent obtains a token, and the injected proxy validates it inbound and exchanges it outbound](../images/authbridge-architecture.svg)

```
Operator                    Agent pod                     Keycloak            Target
   │                            │                             │                  │
   │ 1. enrol + label workload  │                             │                  │
   │ 2. register OAuth client ──┼────────────────────────────► │                  │
   │                            │                             │                  │
   │                   ┌────────┴────────┐  3. get token       │                  │
   │                   │      agent      │────────────────────►│                  │
   │                   │                 │◄────────────────────│                  │
   │                   └────────┬────────┘   aud: agent        │                  │
   │                            │                             │                  │
   │                   ┌────────┴────────┐  4. request + token │                  │
   │                   │ authbridge-proxy│                     │                  │
   │                   │  5. validate,   │────────────────────►│                  │
   │                   │     then exchange│◄───────────────────│                  │
   │                   │                 │   aud: target       │                  │
   │                   └────────┬────────┘─────────────────────┼─────────────────►│
   │                            │                             │  6. validate aud │
```

1. The operator reconciles the `AgentRuntime`, labels the workload, and triggers sidecar injection.
2. The operator registers the workload as an OAuth client in Keycloak.
3. The agent obtains a token.
4. The agent makes a request.
5. The proxy validates the inbound token — signature, expiry, issuer via JWKS — returning 401 if it is
   bad, then exchanges the token for one whose audience is the target.
6. The target validates that the audience is itself.

Sequence diagrams for each stage are in [Authentication flows](flows.md).

## Client registration

You do not create Keycloak clients. The operator's client-registration controller does it:

1. Reconciles `AgentRuntime` resources and labels the target workload `rossoctl.io/type: agent` or
   `tool`.
2. Reads Keycloak admin credentials from `keycloak-admin-secret` in the operator's namespace
   (`rossoctl-system`).
3. Uses the workload's SPIFFE ID as the client identifier.
4. Registers the client and writes the credentials into a Secret in the workload's namespace.

Admin credentials stay in the operator's namespace. Agent namespaces never see them. That isolation is
the point of doing registration centrally.

In the console, this happens when you tick **Secure with AuthBridge** while deploying. There are no init
containers to add and nothing to configure.

## Inspect an agent's configuration

See the live pipelines, in execution order, with each plugin's error policy and configuration:

```bash
rossoctl agents authbridge get orders
rossoctl agents authbridge get orders --json
```

Replace them:

```bash
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml
```

The file is sent verbatim as `text/plain`, so comments and key order survive and the server validates
rather than the CLI. Add `--wait` to poll until the running configuration differs from what it was.

:::note
`--wait` detects *change*, so re-applying the configuration already in effect cannot be confirmed — it
times out and exits non-zero. That is expected, not a failure.
:::

## Run it without Kubernetes

The same binary runs on your machine, which is the fastest way to see the pipeline work:

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
```

See [Quickstart: your laptop](../get-started/laptop.md) and [Install the CLI](../get-started/cli.md).

## Keycloak endpoints

For scripting or debugging against the Kind install:

```
POST http://keycloak.keycloak.svc.cluster.local:8080/realms/rossoctl/protocol/openid-connect/token
GET  http://keycloak.keycloak.svc.cluster.local:8080/realms/rossoctl/protocol/openid-connect/userinfo
POST http://keycloak.keycloak.svc.cluster.local:8080/realms/rossoctl/protocol/openid-connect/token/introspect
```

The admin console is at `http://keycloak.localtest.me:8080/admin/rossoctl/console/`. Get credentials
with `./.github/scripts/local-setup/show-services.sh`.

## Related

- [Identity and trust](../concepts/identity.md) — why delegation is shaped this way.
- [Authentication modes](authentication-modes.md) — client secrets versus SPIFFE.
- [Authentication flows](flows.md) — the diagrams.
- [Plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md) — every
  plugin and its configuration.
