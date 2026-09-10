---
title: Configure a model
description: Give an agent a local model or a model from a cloud provider.
sidebar_position: 4
---

A Rossoctl agent operates with any model endpoint that is compatible with the OpenAI interface. You do
not change the code of the agent to change the model. You set three environment variables when you
deploy the agent.

| Variable | Function | Value for Ollama | Value for OpenAI |
| --- | --- | --- | --- |
| `LLM_API_BASE` | The address of the endpoint | `http://host.docker.internal:11434/v1` | `https://api.openai.com/v1` |
| `LLM_API_KEY` | The API key | `dummy`. Ollama does not read it. | Your OpenAI key |
| `LLM_MODEL` | The name of the model | `qwen2.5:3b` | `gpt-4o-mini-2024-07-18` |

When you deploy an agent from the console, you select the `ollama` preset or the `openai` preset. The
console then sets these three variables for you.

## Option A: Ollama on your computer

This option has no cost and needs no account. It is the default for local development.

Install Ollama from <https://ollama.com/download>. Then run these commands:

```bash
ollama pull qwen2.5:3b
OLLAMA_HOST=0.0.0.0 ollama serve
```

Leave the `ollama serve` command active.

The `OLLAMA_HOST=0.0.0.0` value is necessary. An agent in the cluster is in a different network
namespace. It cannot reach the default loopback address.

On Kind, the `ollama` preset uses the address `http://host.docker.internal:11434/v1`. That name
resolves to your computer from inside the container. There is no other configuration. Select the
**ollama** preset when you deploy the agent.

### On Linux without Docker Desktop

The name `host.docker.internal` can fail to resolve. Find the address of the gateway:

```bash
docker network inspect kind | grep Gateway
```

Then set `LLM_API_BASE` to `http://<that-address>:11434/v1`.

### Models that the project tested

| Model | Size | Notes |
| --- | --- | --- |
| `qwen2.5:3b` | 3B | The default in the test pipeline. It is sufficient for a demonstration. |
| `llama3.2:3b-instruct-fp16` | 3B | The default in the `ollama` preset. |
| `granite3.3:8b` | 8B | Better quality. Tested on an Apple M3 with 64 GB of memory. |
| `gpt-oss:latest` | 20B | Tested on an Apple M3 with 64 GB of memory. |

A smaller model is faster. If the answers are slow, or Kubernetes stops the pod for a memory limit, use
a 3B model.

## Option B: a cloud provider

Put the key in a Kubernetes Secret. Do not put the key in a deployment. Create one Secret in each
namespace that runs an agent:

```bash
kubectl create secret generic openai-secret -n team1 \
  --from-literal=apikey="<YOUR_OPENAI_API_KEY>"
```

Then reference the Secret from the environment of the agent. In the console you can import a `.env` file
that names the Secret instead of the value:

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

For the complete syntax, see
[Deploy an agent](../workloads/deploy-an-agent.md#environment-variables).

For a provider that is not OpenAI, set `LLM_API_BASE` to the `/v1` address of that provider, and set
`LLM_MODEL` to a model that the provider serves. vLLM, the llama.cpp server and LocalAI all operate.

## On OpenShift

Ollama cannot run on your computer for an OpenShift cluster, because the agent is in a remote cluster
and cannot reach your computer. Use one of these methods:

- Run Ollama as a Deployment in the cluster, and set `LLM_API_BASE` to
  `http://ollama.rossoctl-system.svc.cluster.local:11434/v1`.
- Use a cloud provider.

See [Install on OpenShift](../operate/install-openshift.md#models).

## If an agent cannot reach its model

The log of the agent shows a reset connection or an incomplete read. The console shows the status 503.

In almost all cases, the `ollama serve` command is not active. Confirm which values the pod received:

```bash
kubectl exec -n team1 <agent-pod> -- env | grep LLM_
```

For more information, see [Troubleshooting](../operate/troubleshooting.md).
