---
title: Quickstart on Kubernetes
sidebar_label: Quickstart — Kubernetes
description: Install Rossoctl on a local Kind cluster and open the console.
sidebar_position: 3
---

This procedure installs Rossoctl on a local [Kind](https://kind.sigs.k8s.io) cluster. The installation
includes the web console and a sample agent and tool. It needs approximately 20 minutes. Most of that
time is for the download of the container images.

For each installation option and each other target, see
[Install on Kubernetes](../operate/install-kubernetes.md).

## Before you start

| Tool | Version |
| --- | --- |
| A container runtime: Podman, Docker Desktop or Rancher Desktop | 18 GiB of memory, 6 CPUs |
| kubectl | 1.32.1 or later |
| Helm | 3.18.0 or later, below 4 |
| Kind | Any recent release |
| git | 2.48.0 or later |

:::warning Give the runtime 6 CPUs
Kind runs the complete platform on one node. The limits of that node come from your container runtime.
The platform pods alone can request almost 4 CPUs.

With 4 CPUs the installation usually completes. A build from source then fails, and the build pod stays
in the `Pending` state with the message `Insufficient cpu`.
:::

On a new Mac, install the tools with these commands:

```bash
brew install git kind kubectl helm@3 ollama
brew install podman
podman machine init --rootful --memory 18432 --cpus 6
podman machine start
```

The `--rootful` option is necessary. The rootless provider of Kind needs the systemd property
`Delegate=yes`. A new Podman machine does not set that property, so the creation of the cluster fails.

## Step 1: install the platform

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl
git checkout v0.7.0
```

```bash
scripts/kind/setup-rossoctl.sh --with-ui --with-examples
```

This command creates the Kind cluster. It then installs the core platform, which is cert-manager, the
Gateway API controller, Keycloak, the operator and the webhook. It also installs the console, the
backend, and the weather agent and tool samples.

Add more components when you need them. Use `--with-spire` for SPIFFE identity, and `--with-builds` to
build an agent from source. Use `--with-all` for every component. See
[Install options](../reference/install-options.md).

:::tip If the image downloads are slow
Add the `--preload-images` option. The script then downloads the images to your computer first, and
copies them into the node. This method avoids the rate limits of Docker Hub.
:::

## Step 2: open the console

Print the addresses and the credentials:

```bash
./.github/scripts/local-setup/show-services.sh
```

Then open the console:

```bash
open http://rossoctl-ui.localtest.me:8080
```

Sign in with the credentials from `show-services.sh`.

In the console you can import and deploy an agent, deploy a tool, send a message to an agent, and read
the traces and the network data.

## Step 3: confirm the installation

```bash
kubectl get deployments --all-namespaces
```

Each deployment must reach the `Available` state.

If you used the `--with-spire` option, confirm the identity services also:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
curl http://spire-oidc.localtest.me:8080/keys
```

If a deployment does not start, or the console shows an empty page, see
[Troubleshooting](../operate/troubleshooting.md).

## Remove the installation

```bash
# Remove Rossoctl. Keep the cluster.
scripts/kind/cleanup-rossoctl.sh

# Remove Rossoctl and delete the cluster.
scripts/kind/cleanup-rossoctl.sh --destroy-cluster
```

## Next

1. [Configure a model](configure-a-model.md). An agent cannot answer a question without a model.
2. [Deploy your first agent](first-agent.md).
