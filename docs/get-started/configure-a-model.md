---
title: Configure a model
description: Point agents at a local Ollama model or a cloud provider.
sidebar_position: 4
---

Rossoctl agents work with any OpenAI-compatible model endpoint. You do not change agent code to
switch between them — you set three environment variables when you deploy.

| Variable | What it is | Ollama example | OpenAI example |
| --- | --- | --- | --- |
| `LLM_API_BASE` | The endpoint URL | `http://host.docker.internal:11434/v1` | `https://api.openai.com/v1` |
| `LLM_API_KEY` | The API key | `dummy` — Ollama ignores it | your OpenAI key |
| `LLM_MODEL` | The model name | `qwen2.5:3b` | `gpt-4o-mini-2024-07-18` |

When you deploy an agent through the console you pick an `ollama` or `openai` preset and these are
filled in for you.

## Option A: Ollama on your machine

Free, no account, and the default for local development.

```bash
# Install from https://ollama.com/download, then:
ollama pull qwen2.5:3b
OLLAMA_HOST=0.0.0.0 ollama serve
```

Leave `ollama serve` running. `OLLAMA_HOST=0.0.0.0` matters — agents inside the cluster reach your
machine from another network namespace, and the default loopback bind is not visible to them.

On Kind, the `ollama` preset points at `http://host.docker.internal:11434/v1`, which resolves to
your machine from inside the container. Nothing else to configure — select the **ollama** preset
when you deploy.

### On Linux without Docker Desktop

`host.docker.internal` may not resolve. Find the gateway address and use that instead:

```bash
docker network inspect kind | grep Gateway
```

Set `LLM_API_BASE` to `http://<that-address>:11434/v1`.

### Tested models

| Model | Size | Notes |
| --- | --- | --- |
| `qwen2.5:3b` | 3B | Default in CI. Good enough for demos. |
| `llama3.2:3b-instruct-fp16` | 3B | Default in the `ollama` preset. |
| `granite3.3:8b` | 8B | Better quality. Tested on Apple M3 with 64 GB. |
| `gpt-oss:latest` | 20B | Tested on Apple M3 with 64 GB. |

Smaller is faster. If responses crawl or the pod is OOMKilled, drop to a 3B model.

## Option B: A cloud provider

Store the key in a Kubernetes Secret rather than putting it in a deployment. Create one in every
namespace where you run agents:

```bash
kubectl create secret generic openai-secret -n team1 \
  --from-literal=apikey="<YOUR_OPENAI_API_KEY>"
```

Then reference it from the agent's environment. In the console you can import a `.env` file that
points at the Secret rather than embedding the value:

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

See [Deploy an agent](../workloads/deploy-an-agent.md#environment-variables) for the full syntax.

For a provider other than OpenAI, set `LLM_API_BASE` to its `/v1` endpoint and `LLM_MODEL` to a
model it serves. vLLM, llama.cpp server, and LocalAI all work.

## On OpenShift

Ollama cannot run on your machine, because agents run in a remote cluster. Either run Ollama as a
Deployment in the cluster and point `LLM_API_BASE` at
`http://ollama.rossoctl-system.svc.cluster.local:11434/v1`, or use a cloud provider. See
[Install on OpenShift](../operate/install-openshift.md#models).

## If an agent cannot reach its model

The agent log shows a connection reset or an incomplete chunked read, and the console reports a 503.
Nine times out of ten `ollama serve` is not running. Check what the pod actually got:

```bash
kubectl exec -n team1 <agent-pod> -- env | grep LLM_
```

More in [Troubleshooting](../operate/troubleshooting.md).
