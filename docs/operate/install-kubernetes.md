---
title: Install on Kubernetes
description: A complete installation on a Kind cluster, with each option.
sidebar_position: 2
---

The `scripts/kind/setup-rossoctl.sh` script creates a Kind cluster and installs Rossoctl. It always
installs the core components. Each other component has a `--with-*` option.

For the short procedure, see [Quickstart on Kubernetes](../get-started/kubernetes.md).

## Requirements

| Tool | Version | Function |
| --- | --- | --- |
| kubectl | 1.32.1 or later | The Kubernetes interface |
| [Helm](https://helm.sh/docs/intro/install/) | 3.18.0 or later, below 4 | The charts |
| git | 2.48.0 or later | Gets the repository |
| [Kind](https://kind.sigs.k8s.io) | Any recent release | The cluster |
| A container runtime | 18 GiB of memory, 6 CPUs | Podman, Docker Desktop or Rancher Desktop |
| [Ollama](https://ollama.com/download) | 0.11.0 or later | A local model. It is optional. |
| A GitHub token | — | For a private repository or a private registry only. It needs the `repo` and `read:packages` permissions. |

### On a new Mac

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git kind kubectl helm@3 ollama
brew install podman           # or: brew install --cask docker
```

```bash
podman machine init --rootful --memory 18432 --cpus 6
podman machine start
```

The `--rootful` option is necessary. The rootless provider of Kind needs the systemd property
`Delegate=yes`. A new Podman machine does not set that property, so the creation of the cluster fails.

### To change the size of a Podman machine

A change to the number of CPUs is not sufficient. The Kind node holds the previous limit. You must
create the cluster again:

```bash
podman machine stop
podman machine set --cpus 6
podman machine start

kind delete cluster --name rossoctl
scripts/kind/setup-rossoctl.sh --with-istio --with-spire --with-ui --with-backend
```

### If you have 4 CPUs only

Do one of these actions:

- Omit the components that you do not need. Do not use `--with-mlflow`, `--with-kuadrant` or
  `--with-kiali`.
- Deploy each agent with **Deploy from image** and not with **Build from source**.
- Reduce the number of replicas of the components that you do not need, before you start a build.

## Install the platform

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl
git checkout v0.7.0
```

For each component:

```bash
scripts/kind/setup-rossoctl.sh --with-all
```

For selected components:

```bash
# The console and the backend
scripts/kind/setup-rossoctl.sh --with-ui

# The ambient mesh and the console
scripts/kind/setup-rossoctl.sh --with-istio --with-ui

# The mesh, SPIFFE identity, and builds from source
scripts/kind/setup-rossoctl.sh --with-istio --with-spire --with-builds
```

### The core components

The script always installs cert-manager, the Gateway API resources, the Istio gateway controller,
Keycloak, the operator and the webhook.

:::warning The two Istio layers are different
The **Istio gateway controller** is a core component. The script always installs it. It serves each
address on `*.localtest.me:8080`, which includes the console, Keycloak and the agents. You cannot omit
it.

`--with-istio` installs a **different** layer, which is the ambient mesh. That layer adds mTLS and
waypoints, and it is optional. You do not need it for the AuthBridge weather demonstration, because that
demonstration uses its own sidecar and not the mesh.
:::

### The optional components

| Option | What it adds |
| --- | --- |
| `--with-istio` | The Istio ambient mesh: mTLS and waypoints |
| `--with-spire` | SPIRE and the SPIFFE identity provider |
| `--with-ui` | The console. It enables the backend also. |
| `--with-mcp-gateway` | The MCP Gateway |
| `--with-builds` | Tekton and Shipwright, for a build from source |
| `--with-otel` | The OpenTelemetry collector |
| `--with-mlflow` | MLflow. It enables the collector and the ambient mesh also. |
| `--with-kiali` | Kiali and Prometheus. It enables the ambient mesh also. |
| `--with-skills` | The skills feature and a skill store in the cluster |
| `--with-examples` | The weather agent and the weather tool |
| `--with-all` | Each option above |

For each option and each other flag, see [Install options](../reference/install-options.md).

## Secrets

```bash
cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# Add your values to .secrets.yaml
scripts/kind/setup-rossoctl.sh --with-all --secrets-file charts/rossoctl/.secrets.yaml
```

If you omit the `--secrets-file` option, the script uses `charts/rossoctl/.secrets.yaml` when that file
exists.

To change a value later, for example a new `githubToken` value, delete the Secret in each namespace that
received it, and then run the installer again:

```bash
kubectl get secret --all-namespaces
kubectl -n team1 delete secret github-token-secret
scripts/kind/setup-rossoctl.sh
```

## Faster and more reliable image downloads

```bash
scripts/kind/setup-rossoctl.sh --with-all --preload-images
```

The script downloads the images to your computer and then copies them into the Kind node. This method
avoids the rate limits of Docker Hub. The list of images is in
[`scripts/kind/preload-images.txt`](https://github.com/rossoctl/rossoctl/blob/main/scripts/kind/preload-images.txt),
with one image on each line. The list contains `docker.io` images only, because `ghcr.io` and `quay.io`
have no rate limit.

## Use a cluster that exists

```bash
scripts/kind/setup-rossoctl.sh --skip-cluster --with-all
```

For a cluster that Kind did not create, see [Install with Helm](install-helm.md).

## Confirm the installation

```bash
kubectl get deployments --all-namespaces
```

With the `--with-spire` option:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
curl http://spire-oidc.localtest.me:8080/keys
open http://spire-tornjak-ui.localtest.me:8080/
```

For Keycloak:

```bash
open http://keycloak.localtest.me:8080/
```

For each address and each credential:

```bash
./.github/scripts/local-setup/show-services.sh
```

## Remove the installation

```bash
# Remove Rossoctl. Keep the cluster.
scripts/kind/cleanup-rossoctl.sh

# Remove Rossoctl and delete the cluster.
scripts/kind/cleanup-rossoctl.sh --destroy-cluster
```

## Next

- [Authentication modes](../security/authentication-modes.md) to select client secrets or SPIFFE.
- [Observability](observability.md)
- [Troubleshooting](troubleshooting.md)
