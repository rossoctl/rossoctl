---
title: Install for laptop
description: CLI and RossoCortex guide.
sidebar_label: Install for laptop
sidebar_position: 20
---

:::tip

Check back in early August for the quickstart guide for local rossoctl without Kubernetes. For now, here is a Context Guru example without Kubernetes or Docker

:::

### First, obtain Cortex source code

```bash
git clone git@github.com:rossoctl/cortex.git
cd cortex/authbridge/cmd/authbridge-proxy
```

### Then, run Cortex with AuthBridge + ContextGuru

```bash
LOG_LEVEL=debug go run -tags include_plugin_contextguru . --config ../../demos/context-guru/context-guru-tls-bridge.yaml
```

### Finally, run Claude against LiteLLM through AuthBridge

Do this in a separate window.

```bash
NODE_EXTRA_CA_CERTS=/tmp/tls-bridge-ca/ca.crt HTTPS_PROXY=http://localhost:8081 claude
```

At this point, ask Claude `what is 2+2?` and see log messages from Context Guru.

---

For the full demo, with

```
export CG_MODEL_BASE=https://api.openai.com
export CG_MODEL_NAME=gpt-4o-mini
export CG_MODEL_KEY=...
```

see https://github.com/rossoctl/cortex/tree/main/authbridge/demos/context-guru
