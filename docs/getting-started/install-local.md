---
title: Install for laptop
description: CLI and RossoCortex guide.
sidebar_label: Install for laptop
sidebar_position: 2
---

:::tip

Check back in early August for the quickstart guide for local rossoctl without Kubernetes.  For now, here is a Context Guru example without Kubernetes or Docker

:::

### First, Obtain Cortex source code

```bash
git clone git@github.com:rossoctl/cortex.git
cd cortex/authbridge/cmd/authbridge-proxy
```

### Next, create a ContextGuru config that whose unused reverse proxy binds to a random port

```bash
cat ../../demos/context-guru/k8s/authbridge-config.yaml | sed 's/:8080/:0/' > /tmp/authbridge-config.yaml
```

### Then, Run Cortex with AuthBridge + ContextGuru

```bash
LOG_LEVEL=debug go run -tags include_plugin_contextguru . --config /tmp/authbridge-config.yaml
```

### Finally, run Claude against LiteLLM through AuthBridge

Do this in a separate window.

```bash
HTTPS_PROXY=http://localhost:8081 claude --model haiku
```

At this point, ask Claude `what is 2+2?` and see log messages from Context Guru.
