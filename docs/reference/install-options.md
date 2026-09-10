---
title: Install options
description: Each installer option, the supported versions and the namespaces.
sidebar_position: 4
---

## The Kind installer

The script is `scripts/kind/setup-rossoctl.sh`. It always installs the core components. Each other
component has an option.

### The core components

cert-manager, the Gateway API resources, the Istio gateway controller, Keycloak, the operator and the
webhook.

### The component options

| Option | What it adds | What it also enables |
| --- | --- | --- |
| `--with-istio` | The Istio ambient mesh: mTLS and waypoints | — |
| `--with-spire` | SPIRE and the SPIFFE identity provider | — |
| `--with-backend` | The Rossoctl backend | — |
| `--with-ui` | The console | `--with-backend` |
| `--with-mcp-gateway` | The MCP Gateway | — |
| `--with-kuadrant` | The Kuadrant operator | `--with-mcp-gateway` |
| `--with-otel` | The OpenTelemetry collector | — |
| `--with-mlflow` | MLflow | `--with-otel`, `--with-istio` |
| `--with-builds` | Tekton and Shipwright | — |
| `--with-kiali` | Kiali and Prometheus | `--with-istio` |
| `--with-skills` | The skills flags and a skill store in the cluster | `--with-backend`, `--with-ui` |
| `--with-examples` | The weather agent and the weather tool | — |
| `--with-all` | Each option above | — |

### The other options

| Option | Function |
| --- | --- |
| `--skip-cluster` | Uses a Kind cluster that exists. |
| `--build-images` | Builds the platform images from source and copies them into Kind. |
| `--preload-images` | Downloads the third-party images first, then copies them into the node. This option avoids the rate limits of Docker Hub. |
| `--secrets-file FILE` | Names a file of secrets. The default is `charts/rossoctl/.secrets.yaml`, when that file exists. |
| `--cluster-name NAME` | Names the Kind cluster. The default is `rossoctl`. |
| `--domain DOMAIN` | Sets the domain for each address. The default is `localtest.me`. |
| `--rossoctl-values FILE` | A Helm values file for the `rossoctl` chart. |
| `--rossoctl-deps-values FILE` | A Helm values file for the `rossoctl-deps` chart. |
| `--dry-run` | Prints each command. It makes no change. |

The script gives the `--rossoctl-values` file to Helm as `--values`. Each valid Helm value is therefore
accepted.

For the current list, run `scripts/kind/setup-rossoctl.sh --help`.

## The OpenShift installer

The script is `scripts/ocp/setup-rossoctl.sh`.

| Option | Function |
| --- | --- |
| `--rossoctl-repo PATH\|URL` | A local directory or a GitHub address. The default action is a clone of `main` into `~/.cache/rossoctl`. |
| `--realm REALM` | The Keycloak realm. The default is `rossoctl`. |
| `--skip-ovn-patch` | Omits the OVN routing change. |
| `--skip-mcp-gateway` | Omits the MCP Gateway. |
| `--skip-ui` | Omits the console and the backend. |
| `--skip-mlflow` | Omits MLflow. |
| `--operator-image IMG:TAG` | Uses a different operator image. |
| `--dry-run` | Prints each command. It makes no change. |

## Remove an installation

```bash
scripts/kind/cleanup-rossoctl.sh                    # Remove Rossoctl. Keep the cluster.
scripts/kind/cleanup-rossoctl.sh --destroy-cluster  # Remove both.
```

## The feature flags

Set each flag in the Helm values, during the installation or with the `--reuse-values` option.

| Flag | What it controls |
| --- | --- |
| `featureFlags.skills` | Import, list and delete a skill, and give a skill to an agent. |
| `featureFlags.externalSkills` | References to an external skill registry. It needs `skills` also. |
| `components.skillberryStore.enabled` | Installs the skill store in the cluster. |
| `ui.backend.contextServiceUrl` | Enables [agent context](../concepts/experiments/agent-context.md). An empty value disables it. |
| `meshSelfHeal.enabled` | For Kind only. Adds a CronJob that restarts the data plane after a certificate expires. |

The `rossoctl-feature-gates` ConfigMap is separate. It applies to the whole cluster. It controls which
RossoCortex components run, and whether skill discovery is active. A namespace cannot replace it, and a
workload cannot replace it. See
[Custom resources](custom-resources.md#configuration-layers).

## The supported versions

### The tools

| Tool | Version |
| --- | --- |
| kubectl | 1.32.1 or later |
| Helm | 3.18.0 or later, below 4 |
| git | 2.48.0 or later |
| Ollama | 0.11.0 or later, when you use it |
| `oc` | 4.16.0 or later, for OpenShift |

### The platforms

| Platform | Status |
| --- | --- |
| Kubernetes on Kind | The primary target for development. The test pipeline uses version 1.35.0. |
| OpenShift | The project tested version 4.19. The test pipeline uses version 4.20 with HyperShift. |
| Another Kubernetes distribution | It must operate with [Helm](../operate/install-helm.md). The test pipeline does not cover it. |

For the state of each test pipeline, see the
[repository README](https://github.com/rossoctl/rossoctl).

### The machine size

| Profile | Memory | CPUs | What operates |
| --- | --- | --- | --- |
| Recommended | 18 GiB | 6 | The ambient mesh, SPIRE, the console, the backend and a build from source. |
| Minimum | 16 GiB | 4 | The core platform and the console. Images only. |
| Below the minimum | — | 4 or fewer | The installation usually completes. A build stays in `Pending`. |

The installer gives a warning below the recommended values. It does not stop.

## The namespaces

| Namespace | Contents |
| --- | --- |
| `rossoctl-system` | The operator, the webhook, the backend, the console and MLflow |
| `keycloak` | Keycloak and its database |
| `istio-system` | The Istio control plane, ztunnel and the gateways |
| `spire-system` | The SPIRE agent |
| `zero-trust-workload-identity-manager` | The SPIRE DaemonSets |
| `gateway-system` | The Envoy proxy of the MCP Gateway |
| `mcp-system` | The controller, the broker and the router of the MCP Gateway |
| `cr-system` | The container registry in the cluster |
| Your own namespaces | Your agents and tools |
