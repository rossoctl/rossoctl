---
title: Context compaction
description: Shrink tool output before it reaches the model, so long tasks still fit.
sidebar_position: 4
---

Context compaction rewrites an agent's outbound model request to make its tool output smaller. Tasks
whose raw context would overflow the model's window fit instead — and the agent gets the right answer
*because* of the compaction, not despite it.

The plugin is `context-guru`.

:::warning Alpha
Alpha in 0.7. Behaviour and configuration will change. Use it for evaluation, and run it in observe mode
before enforcing.
:::

## What problem this solves

Agents accumulate tool output. A few calls returning audit logs or file listings can produce more text
than the model can accept. What happens then is the quiet failure mode: the request is truncated, the
model never sees the part that mattered, and it answers confidently and wrongly.

A measured example — one agent, one model, one 12K-token window, and the only variable is the plugin:

| Mode | What the model receives | Result |
| --- | --- | --- |
| **off** | ~18K tokens, truncated to fit 12K | Misses the anomaly. Invents a wrong answer. |
| **observe** | ~18K tokens, truncated — plugin measures only | Same wrong answer. Logs that it *would* have saved 52 KB → 30 KB. |
| **enforce** | ~10K tokens, compacted, fits | Finds the duplicate transaction and clears the rest. |

The observe row is the point of having an observe mode: it proves the measurement without changing
behaviour, so you can size the benefit before you take the risk.

## How it works

`context-guru` runs in-process in the Cortex outbound pipeline — not as a separate service. The agent's
model calls go through Cortex's forward proxy, and the plugin rewrites the request body before it leaves
the pod.

![context-guru architecture](../images/contextguru-architecture.svg)

Three techniques, applied to tool output:

- **Deduplicate** — collapse repeated content.
- **Extract** — pull out the significant parts, for example code from a large file listing.
- **Collapse** — summarise the rest.

`OnResponse` is currently a pass-through. Model-driven expansion and restore are a later integration.

## Enable it

The plugin is opt-in at **build** time, not just configuration time: its engine pulls a large dependency
set, so it is compiled in with `-tags include_plugin_contextguru`. Confirm your Cortex build includes it
before configuring it.

Key configuration:

| Setting | What it does |
| --- | --- |
| `paths` | Which inference paths to compact. Defaults to `/v1/chat/completions`, `/v1/completions`, `/v1/messages`. |
| `model` | An optional cheap model endpoint for the summarise and extract steps. Omit it and those degrade to deterministic behaviour. |
| `engine` | Native engine configuration — preset, pipeline, per-component, store. Defaults to `preset: balanced`. |

The `model` block takes `base_url`, `model`, `api_key`, `max_tokens` (default 4096), and `timeout_ms`
(default 150000).

Full reference in the
[plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md#context-guru).

## Rolling it out

1. Build or obtain a Cortex binary with the plugin compiled in.
2. Enable it in **observe** mode on one agent that handles large tool output.
3. Read the logs. They report what it would have saved.
4. If the saving is worth it, switch to **enforce** and check the agent's answers are still correct.

Step 4 matters. Compaction changes what the model sees. Verify on your own tasks rather than assuming.

## On your laptop

You do not need a cluster to try this:

```bash
rossoctl authbridge exec \
  --config https://raw.githubusercontent.com/rossoctl/rossoctl-cli/refs/heads/main/examples/context-guru-tls-bridge.yaml \
  -- claude "explain this repo"
```

See [Quickstart: your laptop](../get-started/laptop.md).

## Try it

- [context-guru demo](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/context-guru) — the
  finance-agent scenario above, reproducible.

## Related

- [Reduce token cost](token-cost.md) — cheaper wins with less behavioural risk.
- [context-guru](https://github.com/rossoctl/context-guru) — the engine.
