---
title: Read the numbers
sidebar_label: Read the numbers
description: What Cortex shows for each session, what each number means, and how to act on it.
sidebar_position: 3
---

You installed Cortex and started `abctl observe`. Now you see traffic. This page explains what the
numbers mean and what to do with them.

Cortex shows you what your coding agent sent and what it cost. It shows the model calls, the tool
calls and the token counts for each session, on your own computer, as they happen. Your agent does
not report this. Your model provider reports a monthly total, not one session while you work. Cortex
is the view between the two.

:::note The data stays on your computer
Cortex captures this traffic on your computer and keeps it there. It does not collect the data and it
does not send the data to Rossoctl or to any other service. The data is for you to read and to inspect.
When you stop the service, the data goes with it. See [Manage the service](laptop.md#manage-the-service).
:::

<!-- VERIFY v0.9.0: confirm the local-only claim once persistence (#901, sqlite) lands — the store is
     on-disk and local, and no telemetry is sent by default. Central reporting is a separate, opt-in
     feature (#898), not part of the laptop tool. -->


<!-- VERIFY v0.9.0: the metrics view, the token/cost/latency figures and the pruning figure depend
     on #950, #951 and #952. Confirm the field names, the labels and the layout against `abctl
     observe` from a v0.9.0 binary before release, and replace the worked example below with a
     captured session. -->

## What the numbers tell you

The numbers support four decisions:

- **Find an expensive prompt.** One session that costs much more than the others shows you where the
  cost is.
- **See whether caching operates.** A high cache-read count means the model reuses your prompt. A low
  count means it does not, and you pay the full rate each turn.
- **Catch a session that does not end.** A token count that grows without a result is an agent in a
  loop. You stop it before it costs more.
- **Decide whether to prune tool definitions.** The pruning figure shows the tokens that Cortex
  removed, so you know if the feature is worth enabling. See [Cost control](../concepts/experiments/cost-control.md).

You can read this page before you install Cortex. It describes what Cortex shows you that you cannot
otherwise see.

## Watch a session

`abctl observe` opens a terminal interface. It has three views.

- **Sessions.** A list of the sessions, with the most recent one first. Each row shows the identifier,
  the time of the last event, the event count and the token total.
- **Events.** The calls in one session. Each row shows the time, the direction, the protocol, the
  model or the method, the status, the duration and the host. Press `Enter` on a session to open it.
- **Detail.** The full content of one event, as formatted JSON. Press `Enter` on an event to open it.

### Keys

| Key | Action |
| --- | --- |
| `↑` `↓` or `k` `j` | Move between rows |
| `Enter` | Open the selected row |
| `Esc` | Return to the previous view |
| `/` | Filter the events |
| `p` | Pause and resume the stream |
| `y` | Write the event to a file in `/tmp` |
| `g` `G` | Move to the top or the bottom |
| `q` or `Ctrl+C` | Quit |

The `/` key filters the events by a **substring match on the method**. For example, `messages` shows
only the events whose method contains that text. It is a text match on the method, not a query
language. You cannot filter on a condition such as a duration.

## Read the tokens

A model call has a cost in tokens. Cortex separates the tokens into five categories, because each
category has a different price.

| Category | What it is | Why it is separate |
| --- | --- | --- |
| **Input** | The prompt tokens that the model read for the first time | You pay the full rate for these. |
| **Cache read** | The prompt tokens that the model read from its cache | Much less than the input rate. This is caching that operates. |
| **Cache write** | The prompt tokens that the model wrote to its cache | More than the input rate. This is the one-time cost to store the prompt. |
| **Output** | The tokens that the model generated | |
| **Reasoning** | The output tokens that the model used to reason | A part of the output on some models. |

### Why cache read and cache write are two numbers

A model can cache a part of your prompt. The next call that sends the same part reads it from the
cache. This is useful for a coding agent, because the agent sends the same system prompt and the same
files on each turn.

The two cache numbers have different prices, so Cortex keeps them apart:

- **A cache write costs more than an input token.** You pay a premium once, to store the prompt.
- **A cache read costs a fraction of an input token.** You save on each later turn that reuses the
  prompt.

The split tells you whether caching earns its cost:

- A large **cache-read** count means the cache operates. You pay the low rate for most of the prompt.
- A **cache-write** count that repeats, with little cache-read, means the cache does not hold. You pay
  the premium again and again and get no saving. This happens when the prompt changes on each turn.

## Read the cost

Cortex applies a price to each token category and adds the results. The figure is the cost of the
session.

- **The cost is an estimate, unless the provider returns an exact figure.** Cortex computes the cost
  from published rates for each model. When the provider returns an exact cost (for example, the
  `x-litellm-response-cost` header from LiteLLM), Cortex uses that figure instead.
- **The rates come from a table for each model.** A model that Cortex does not recognize has no rate,
  so its cost is zero even when its token counts are correct.

<!-- VERIFY v0.9.0: confirm the rate source (built-in table vs. config), and the exact provider
     headers Cortex reads for an authoritative cost, once #950/#952 land. -->

## Read the latency

Cortex records two times for each model call.

- **Time to first token.** The time from the request to the first part of the reply. For a reply that
  streams, this is the time until you see the first word. It is the number that decides how fast the
  agent feels.
- **Total response time.** The time from the request to the last part of the reply. It depends on the
  length of the reply.

For a set of calls, Cortex reports percentiles.

- **p50** is the middle value. Half of the calls are faster. It is the typical experience.
- **p95** and **p99** are the slow calls. Ninety-five or ninety-nine percent of the calls are faster.
  These are the calls that a user notices. A p50 that is good with a p99 that is bad means that most
  calls are fast, but the slow calls are very slow.

## Read the pruning savings

If you enable tool pruning, Cortex removes the tool definitions that the agent does not use, before
the request goes to the model. The savings figure is the tokens and the cost that the pruning
removed. See [Cost control](../concepts/experiments/cost-control.md).

- **A figure above zero** is the saving for that session. You paid less because Cortex sent a smaller
  request.
- **A figure of zero** means that Cortex removed nothing. The usual cause is an agent with no tools.
  An agent that sends no tool definitions has nothing to prune, so zero is the correct figure and not
  a failure.

This figure is the answer to one question: what does pruning do for me? You enable pruning, you read
the figure, and you decide if the saving is worth the feature.

## A worked example

:::note
These are representative figures for the data that Cortex captures. They show the shape of a real
session. Replace them with a session that you capture before you rely on the exact values.
:::

<!-- VERIFY v0.9.0: replace this table with a real `abctl observe` capture from a v0.9.0 binary. -->

One session of a coding agent, with tool pruning enabled:

| Field | Value |
| --- | --- |
| Model | `claude-sonnet-4` |
| Events | 34 |
| Input tokens | 12,400 |
| Cache read | 486,000 |
| Cache write | 61,200 |
| Output tokens | 8,900 |
| Reasoning tokens | 3,100 |
| Cost | 2.14 USD |
| Time to first token (p50) | 0.7 s |
| Time to first token (p95) | 2.9 s |
| Total response time (p95) | 24 s |
| Tokens pruned | 41,000 |
| Cost saved by pruning | 0.12 USD |

How to read it:

- **Caching operates.** The cache-read count (486,000) is much larger than the input count (12,400).
  The agent sends the same context on each turn, and the model reads almost all of it from the cache.
  Without the cache, the input cost is many times higher.
- **The cache-write count is a one-time cost.** The 61,200 cache-write tokens are the first turn that
  stored the context. Later turns read it, and do not write it again.
- **The slow tail is visible.** The typical first token arrives in 0.7 s, but the slowest calls take
  2.9 s. If the agent felt slow, the p95 is the reason, not the p50.
- **Pruning earns a small amount here.** It saved 0.12 USD, because it removed 41,000 tokens of unused
  tool definitions across the session. On an agent with many tools, this figure is larger.

## Why leave Cortex running

One session is useful. A week of sessions is more useful. The value is in the change over time:

- A prompt that grows more expensive each day.
- A cache-read count that falls, because a change to the agent broke the cache.
- A session that costs ten times the others.

You see these only if Cortex runs while you work. It runs as a background service and adds no step to
your day. See [Manage the service](laptop.md#manage-the-service).

## Related pages

- [Quickstart on a laptop](laptop.md) installs Cortex and starts `abctl observe`.
- [Cost control](../concepts/experiments/cost-control.md) reduces the token cost.
- [Context compaction](../concepts/experiments/context-compaction.md) makes large tool output smaller.
- [Troubleshooting](../operate/troubleshooting.md) covers the case of no events or wrong numbers.
- [RossoCortex](../concepts/core/cortex.md) explains the program that captures this data.
