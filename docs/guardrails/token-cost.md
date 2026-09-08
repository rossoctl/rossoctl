---
title: Reduce token cost
description: Trim what agents send to models, and cap what they spend.
sidebar_position: 5
---

Agents waste tokens in predictable ways. Cortex has plugins for the two biggest: sending tool
definitions the agent never calls, and having no spending limit at all.

:::warning Alpha
The plugins on this page are alpha in 0.7. Behaviour and configuration will change.
:::

Start here rather than with [IBAC](ibac.md) or [SPARC](sparc.md) if you want a quick result — these do
not judge the agent's decisions, so there is much less to go wrong.

## See what you are spending first

You cannot trim what you have not measured. On your laptop this takes one command:

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/cortex/main/authbridge/install.sh \
  | sh -s -- --claude-code
```

Then run `abctl` in one terminal and your agent in another. Every model call, tool call, and
agent-to-agent message streams in as it happens. See
[Quickstart: your laptop](../get-started/laptop.md).

In a cluster, the same data reaches your trace backend — see
[Observability](../operate/observability.md).

## Prune unused tool definitions

Agents send the full definition of every tool they *might* call on every single turn. In practice they
call a handful. On a typical coding agent the definitions the agent never touches are **4–20% of the
prompt, every turn** — paid for repeatedly, for the whole session.

The `tool-prune` plugin removes them from inference requests before they leave the pod.

This is the cheapest saving available: it changes no agent logic and no answers, because the removed
definitions are ones the agent was not going to use.

Configuration is in the
[plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md#tool-prune).

:::note
Pruning is a judgement about what an agent will need. If an agent legitimately uses a rarely-called
tool, verify it still can after enabling this.
:::

## Cap spending

Two plugins, for two different limits.

### Per session

`session-budget` enforces token, call, and duration limits for a single session, using Redis to hold
the counters. It runs on the outbound chain.

Use this to stop a single runaway task — an agent stuck in a loop calling a model hundreds of times.

### Per day

`litellm-budget-track` reads the `x-litellm-response-cost` header that LiteLLM returns and enforces a
daily limit.

Where you place it depends on your topology:

| Your setup | Chain |
| --- | --- |
| Cortex fronts the model endpoint | Inbound |
| Cortex hosts an agent via `authbridge exec` | Outbound |

Configuration for both is in the
[plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md).

## Compact large tool output

If your problem is not the number of calls but the size of what tools return, pruning will not help.
See [Context compaction](context-compaction.md).

## Order of operations

1. **Measure.** Install Cortex and watch a real session. Find out where the tokens actually go.
2. **Prune.** Enable `tool-prune`. No behavioural risk, immediate saving.
3. **Cap.** Add `session-budget` so a runaway task cannot cost unboundedly.
4. **Compact**, if large tool output is the real cost. Do this last — it changes what the model sees.

## Related

- [Context compaction](context-compaction.md).
- [Observability](../operate/observability.md) — metrics and traces per agent.
- [RossoCortex](../concepts/cortex.md) — where these plugins sit.
