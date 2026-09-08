---
title: Install on Kubernetes
description: Full install on a Kind cluster, with every option.
sidebar_position: 2
---

`scripts/kind/setup-rossoctl.sh` creates a Kind cluster and installs Rossoctl. Core components always
install; everything else is a `--with-*` flag.

For the short path, see [Quickstart: Kubernetes](../get-started/kubernetes.md).

## Prerequisites

| Tool | Version | For |
| --- | --- | --- |
| kubectl | ≥ 1.32.1 | Kubernetes CLI |
| [Helm](https://helm.sh/docs/intro/install/) | ≥ 3.18.0, < 4 | Charts |
| git | ≥ 2.48.0 | Cloning |
| [Kind](https://kind.sigs.k8s.io) | any recent | The cluster |
| Container runtime | 18 GiB RAM, 6 CPUs | Podman, Docker Desktop, or Rancher Desktop |
| [Ollama](https://ollama.com/download) | ≥ 0.11.0 | Local inference, optional |
| GitHub token | — | Only for private repositories or registries. Scopes: `repo`, `read:packages` |

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

`--rootful` is required. Kind's rootless provider needs the systemd property `Delegate=yes`, which a
fresh Podman machine does not configure, so cluster creation fails without it.

### Resizing an existing Podman machine

Changing CPUs is not enough on its own — the Kind node caches the old limit, so recreate the cluster:

```bash
podman machine stop
podman machine set --cpus 6
podman machine start

kind delete cluster --name rossoctl
scripts/kind/setup-rossoctl.sh --with-istio --with-spire --with-ui --with-backend
```

### If you are stuck on 4 CPUs

- Skip what you do not need — leave off `--with-mlflow`, `--with-kuadrant`, `--with-kiali`.
- Deploy agents with **Deploy from image** rather than **Build from source**.
- Or scale down non-essential deployments before triggering a build.

## Install

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl
git checkout v0.7.0
```

Everything:

```bash
scripts/kind/setup-rossoctl.sh --with-all
```

Or only what you need:

```bash
# Console and backend
scripts/kind/setup-rossoctl.sh --with-ui

# Ambient mesh and the console
scripts/kind/setup-rossoctl.sh --with-istio --with-ui

# Mesh, SPIFFE identity, and source builds
scripts/kind/setup-rossoctl.sh --with-istio --with-spire --with-builds
```

### Core, always installed

cert-manager, Gateway API CRDs, the Istio Gateway controller (`istio-base` and `istiod`), Keycloak, the
Rossoctl operator, and the webhook.

:::warning Two Istio layers — do not confuse them
The **Istio Gateway controller** is core and always installed. It implements the
`gatewayClassName: istio` Gateway fronting all `*.localtest.me:8080` ingress — the console, Keycloak,
and agents — so it cannot be skipped.

`--with-istio` is a **different** layer: the ambient mesh, adding mTLS and waypoints. It is optional. You
do not need it for the AuthBridge weather demo, which enforces auth through its own injected sidecar
rather than the mesh.
:::

### Optional components

See [Install options](../reference/install-options.md) for the full flag reference. In brief:

| Flag | Adds |
| --- | --- |
| `--with-istio` | Istio ambient mesh — mTLS, waypoints |
| `--with-spire` | SPIRE and SPIFFE identity provider setup |
| `--with-ui` | Console, and the backend automatically |
| `--with-mcp-gateway` | MCP Gateway |
| `--with-builds` | Tekton and Shipwright, for source builds |
| `--with-otel` | OpenTelemetry collector |
| `--with-mlflow` | MLflow trace backend, plus OTel and ambient mesh |
| `--with-kiali` | Kiali and Prometheus, plus ambient mesh |
| `--with-skills` | Skills feature, plus an in-cluster skillberry store |
| `--with-examples` | Weather agent and tool samples |
| `--with-all` | All of the above |

## Secrets

```bash
cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# edit .secrets.yaml
scripts/kind/setup-rossoctl.sh --with-all --secrets-file charts/rossoctl/.secrets.yaml
```

If you do not pass `--secrets-file`, the installer picks up `charts/rossoctl/.secrets.yaml`
automatically when it exists.

To change a value later — a rotated `githubToken`, say — delete the derived Secret in every namespace it
was copied to, then re-run the installer:

```bash
kubectl get secret --all-namespaces
kubectl -n team1 delete secret github-token-secret
scripts/kind/setup-rossoctl.sh
```

## Faster and more reliable image pulls

```bash
scripts/kind/setup-rossoctl.sh --with-all --preload-images
```

This pulls third-party images on the host and side-loads them into the Kind node, avoiding Docker Hub
anonymous-pull rate limits. The list is in
[`scripts/kind/preload-images.txt`](https://github.com/rossoctl/rossoctl/blob/main/scripts/kind/preload-images.txt)
— one image per line. It covers `docker.io` only; `ghcr.io` and `quay.io` are not rate-limited.

## Reuse an existing cluster

```bash
scripts/kind/setup-rossoctl.sh --skip-cluster --with-all
```

For clusters that are not Kind, see [Install with Helm](install-helm.md).

## Verify

```bash
kubectl get deployments --all-namespaces
```

With `--with-spire`:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
curl http://spire-oidc.localtest.me:8080/keys
open http://spire-tornjak-ui.localtest.me:8080/
```

Keycloak:

```bash
open http://keycloak.localtest.me:8080/
```

All URLs and credentials:

```bash
./.github/scripts/local-setup/show-services.sh
```

## Uninstall

```bash
# Remove Rossoctl, keep the cluster
scripts/kind/cleanup-rossoctl.sh

# Remove Rossoctl and destroy the cluster
scripts/kind/cleanup-rossoctl.sh --destroy-cluster
```

## Next

- [Authentication modes](../security/authentication-modes.md) — choose client secrets or SPIFFE.
- [Observability](observability.md).
- [Troubleshooting](troubleshooting.md).
