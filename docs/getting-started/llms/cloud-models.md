---
description: Use OpenAI or other hosted models
sidebar_label: Use cloud LLMs
---

# Using Cloud LLMs

Rossoctl supports any OpenAI-compatible model backend. This guide covers configuring Rossoctl to use OpenAI and other cloud providers

---

## Overview

Rossoctl agents use three environment variables to configure their LLM backend:

| Variable | Description | Example (Ollama) | Example (OpenAI) |
|----------|-------------|------------------|-------------------|
| `LLM_API_BASE` | API endpoint URL | `http://host.docker.internal:11434/v1` | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key | `dummy` (Ollama ignores this) | Your OpenAI API key |
| `LLM_MODEL` | Model identifier | `qwen2.5:3b` | `gpt-4o-mini-2024-07-18` |

When deploying agents through the Rossoctl UI, you select an LLM preset (`ollama` or `openai`) that populates these values automatically. No code changes are needed to switch between backends.

The preset specifies OpenAI, and retrieves the OpenAI key from a Kubernetes secret.

## Storing your API key in a Secret

Rossoctl currently offers examples with OpenAI `.env` files that read an API key from a Kubernetes secret.

To create this secret, for each Kubernetes namespace you use for Rossoctl agents,

```bash
kubectl create secret generic openai-secret -n team1 \
  --from-literal=apikey="<YOUR_OPENAI_API_KEY>"
kubectl create secret generic openai-secret -n team2 \
  --from-literal=apikey="<YOUR_OPENAI_API_KEY>"
```

## Other hosting providers

When deploying on other cloud providers, override LLM_API_BASE to point to your provider's endpoint.
