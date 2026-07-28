---
title: Quickstart
description: Install Rossoctl on a Kubernetes cluster
---

## Prerequisites

For this Quickstart, we'll install on a laptop-hosted Kubernetes using `kind`.

For more install options, see the [Installation Guide](../getting-started/install.md).

- Docker Desktop, Rancher Desktop, or Podman (16GB RAM, 6 cores recommended)
- [Kind](https://kind.sigs.k8s.io)
- (optional) [Ollama](https://ollama.com/download) for local LLM inference.
  - Alternatively, use OpenAI or a [cloud-hosted LLM](../getting-started/llms/cloud-models.md).

## Install

Clone the repository:

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl
```

Check out the latest stable release (recommended). Find the current version at https://github.com/rossoctl/rossoctl/releases/latest.

```bash
git checkout v0.7.0-alpha.6
```

Copy and configure secrets (optional). Edit `deployments/envs/.secret_values.yaml` with your values.

```bash
cp deployments/envs/secret_values.yaml.example deployments/envs/.secret_values.yaml
```

Deploy to `kind` self-hosted Kubernetes cluster:

```bash
scripts/kind/setup-rossoctl.sh --with-ui --with-spire --with-agent-sandbox --with-builds
```

## Access the Rossoctl Dashboard

Show service URLs and credentials:

```bash
.github/scripts/local-setup/show-services.sh
```

Open the dashboard and log in with the credentials from the `show-services.sh` output:

```bash
open http://rossoctl-ui.localtest.me:8080
```

## Install a self-hosted LLM

:::note

You may skip this step and see [Cloud Models](../getting-started/llms/cloud-models.md) if you are using a cloud-hosted LLM.

:::

1. Install Ollama: <https://ollama.com/download>
2. Pull a model:

   ```bash
   ollama pull llama3.2:3b-instruct-fp16
   ```

3. Start Ollama (listening on all interfaces):

   ```bash
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```

## Next step

Run the [weather agent](../demos/demo-weather-agent.md).
