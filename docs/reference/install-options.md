---
title: Install options
description: Installer flags, supported versions, and namespaces.
sidebar_position: 4
---

## Kind installer

`scripts/kind/setup-rossoctl.sh`. Core components always install; the rest are flags.

### Core, always installed

cert-manager, Gateway API CRDs, the Istio Gateway controller (`istio-base` and `istiod`), Keycloak, the
Rossoctl operator, and the Rossoctl webhook.

### Component flags

| Flag | Adds | Also enables |
| --- | --- | --- |
| `--with-istio` | Istio ambient mesh — mTLS, waypoints | |
| `--with-spire` | SPIRE and SPIFFE identity provider setup | |
| `--with-backend` | Rossoctl backend API | |
| `--with-ui` | Rossoctl console | `--with-backend` |
| `--with-mcp-gateway` | MCP Gateway | |
| `--with-kuadrant` | Kuadrant operator | `--with-mcp-gateway` |
| `--with-otel` | OpenTelemetry collector | |
| `--with-mlflow` | MLflow trace backend | `--with-otel`, `--with-istio` |
| `--with-builds` | Tekton and Shipwright, for source builds | |
| `--with-kiali` | Kiali and Prometheus | `--with-istio` |
| `--with-skills` | Skills feature flags and an in-cluster skillberry store | `--with-backend`, `--with-ui` |
| `--with-examples` | Weather agent and tool samples | |
| `--with-all` | Everything above | |

### Other flags

| Flag | Effect |
| --- | --- |
| `--skip-cluster` | Reuse an existing Kind cluster. |
| `--build-images` | Build platform images from source and load them into Kind — backend, ui-v2, agent-oauth-secret, mlflow-oauth-secret. |
| `--preload-images` | Pre-pull third-party images on the host and side-load them, avoiding Docker Hub rate limits. |
| `--secrets-file FILE` | YAML file of secrets. Defaults to `charts/rossoctl/.secrets.yaml` when it exists. |
| `--cluster-name NAME` | Kind cluster name. Default `rossoctl`. |
| `--domain DOMAIN` | Domain for services. Default `localtest.me`. |
| `--rossoctl-values FILE` | Helm override file for the `rossoctl` chart. |
| `--rossoctl-deps-values FILE` | Helm override file for the `rossoctl-deps` chart. |
| `--dry-run` | Print the commands without running them. |

`--rossoctl-values` is passed straight to Helm as `--values`, so anything valid there works.

Run `scripts/kind/setup-rossoctl.sh --help` for the current list.

## OpenShift installer

`scripts/ocp/setup-rossoctl.sh`.

| Flag | Effect |
| --- | --- |
| `--rossoctl-repo PATH\|URL` | Local path or GitHub URL. Defaults to cloning `main` into `~/.cache/rossoctl`. |
| `--realm REALM` | Keycloak realm. Default `rossoctl`. |
| `--skip-ovn-patch` | Skip the OVN gateway routing patch. The operator warns at startup if it is missing. |
| `--skip-mcp-gateway` | Do not install the MCP Gateway. |
| `--skip-ui` | Do not install the console or backend. |
| `--skip-mlflow` | Do not install the MLflow integration. |
| `--operator-image IMG:TAG` | Custom operator image. |
| `--dry-run` | Print the commands without running them. |

## Cleanup

```bash
scripts/kind/cleanup-rossoctl.sh                    # remove Rossoctl, keep the cluster
scripts/kind/cleanup-rossoctl.sh --destroy-cluster  # remove both
```

## Feature flags

Set through Helm values, at install or with `--reuse-values`.

| Flag | Controls |
| --- | --- |
| `featureFlags.skills` | Skills management — import, list, delete, and link to agents. |
| `featureFlags.externalSkills` | External skill registry references. Requires `skills`. |
| `components.skillberryStore.enabled` | Deploy the in-cluster skillberry store. |
| `ui.backend.contextServiceUrl` | Enable [agent context](../workloads/agent-context.md). Empty disables it. |
| `meshSelfHeal.enabled` | Kind only. A CronJob that restarts the ambient data plane after certificate expiry. |

`rossoctl-feature-gates` is a separate, cluster-wide ConfigMap controlling which Cortex components run and
whether `skillDiscovery` is active. It cannot be overridden per namespace or per workload — see
[Custom resources](custom-resources.md#configuration-precedence).

## Supported versions

### Tooling

| Tool | Version |
| --- | --- |
| kubectl | 1.32.1 or later |
| Helm | 3.18.0 or later, below 4 |
| git | 2.48.0 or later |
| Ollama | 0.11.0 or later, if used |
| `oc` | 4.16.0 or later, for OpenShift |

### Platforms

| Platform | Status |
| --- | --- |
| Kubernetes on Kind | Primary development target. CI runs against 1.35.0. |
| OpenShift | Tested on 4.19. CI runs against 4.20 via HyperShift. |
| Other Kubernetes distributions | Should work via [Helm](../operate/install-helm.md). Not covered by CI. |

CI status for each is on the [repository README](https://github.com/rossoctl/rossoctl).

### Machine sizing

| Profile | RAM | CPUs | Supports |
| --- | --- | --- | --- |
| Recommended | 18 GiB | 6 | Ambient mesh, SPIRE, console, backend, and source builds. |
| Minimum | 16 GiB | 4 | Core and console. Prebuilt images only. |
| Below | — | ≤ 4 | Often installs. Source builds stay `Pending`. |

The installer warns below the recommended figures but does not fail.

## Namespaces

| Namespace | Contains |
| --- | --- |
| `rossoctl-system` | Operator, webhook, backend, console, MLflow |
| `keycloak` | Keycloak and its database |
| `istio-system` | Istio control plane, ztunnel, gateways |
| `spire-system` | SPIRE agent |
| `zero-trust-workload-identity-manager` | SPIRE DaemonSets |
| `gateway-system` | MCP Gateway Envoy |
| `mcp-system` | MCP Gateway controller, broker, router |
| `cr-system` | In-cluster container registry |
| your own | Agents and tools |
