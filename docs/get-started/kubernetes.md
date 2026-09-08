---
title: "Quickstart: Kubernetes"
sidebar_label: Quickstart — Kubernetes
description: Install Rossoctl on a local Kind cluster and open the console.
sidebar_position: 3
---

This installs Rossoctl on a local [Kind](https://kind.sigs.k8s.io) cluster with the console and a
sample agent and tool. It takes about twenty minutes, most of it pulling images.

For every install option, other targets, and production settings, see
[Install on Kubernetes](../operate/install-kubernetes.md).

## What you need

| Tool | Version |
| --- | --- |
| Container runtime — Podman, Docker Desktop, or Rancher Desktop | 18 GiB RAM, 6 CPUs |
| kubectl | 1.32.1 or later |
| Helm | 3.18.0 or later, below 4 |
| Kind | any recent release |
| git | 2.48.0 or later |

:::warning Give the runtime 6 CPUs
Kind runs the whole platform on one node, and that node's limits come from your container runtime.
Platform pods alone can request close to 4 cores. With 4 CPUs the install usually succeeds but
building agents from source fails, with build pods stuck `Pending` on `Insufficient cpu`.
:::

On a new Mac:

```bash
brew install git kind kubectl helm@3 ollama
brew install podman
podman machine init --rootful --memory 18432 --cpus 6
podman machine start
```

`--rootful` is required: Kind's rootless provider needs the systemd property `Delegate=yes`, which
a fresh Podman machine does not set, so cluster creation fails without it.

## Install

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl
git checkout v0.7.0
```

```bash
scripts/kind/setup-rossoctl.sh --with-ui --with-examples
```

This creates the Kind cluster and installs the core platform — cert-manager, the Gateway API
controller, Keycloak, the operator, and the webhook — plus the console, the backend, and the
weather agent and tool samples.

Add more as you need it. `--with-spire` for SPIFFE identity, `--with-builds` to build agents from
source, `--with-all` for everything. See [Install options](../reference/install-options.md).

:::tip Slow image pulls
Add `--preload-images` to pull third-party images on the host first and side-load them into the
node. This avoids Docker Hub rate limits.
:::

## Open the console

Print the service URLs and credentials:

```bash
./.github/scripts/local-setup/show-services.sh
```

Then:

```bash
open http://rossoctl-ui.localtest.me:8080
```

Log in with the credentials from `show-services.sh`.

From the console you can import and deploy agents, deploy MCP tools, chat with an agent, and view
traces and network traffic.

## Check that it worked

```bash
kubectl get deployments --all-namespaces
```

Everything should reach `Available`. If you used `--with-spire`, also check:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
curl http://spire-oidc.localtest.me:8080/keys
```

If a deployment is stuck or the console shows a blank page, see
[Troubleshooting](../operate/troubleshooting.md).

## Clean up

```bash
# Remove Rossoctl, keep the cluster
scripts/kind/cleanup-rossoctl.sh

# Remove Rossoctl and destroy the cluster
scripts/kind/cleanup-rossoctl.sh --destroy-cluster
```

## Next

1. [Configure a model](configure-a-model.md) — agents need one before they can do anything.
2. [Deploy your first agent](first-agent.md).
