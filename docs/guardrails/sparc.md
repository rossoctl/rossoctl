---
title: Tool call validation
sidebar_label: SPARC
description: Block tool calls whose arguments are not grounded in the conversation.
sidebar_position: 3
---

SPARC checks that a proposed tool call is grounded — in the conversation so far and in the tool's own
specification — before it runs. It catches invented arguments and the wrong tool for the job.

:::info Beta
The capability is beta in 0.7. Configuration may change between releases.
:::

## What it catches

Models invent plausible-looking values. Asked to look up a transaction the user never named, a model
will often produce a well-formed transaction ID that does not exist — or call a transfer tool when the
user asked for a lookup.

These calls are not attacks and not malformed. They are syntactically valid, correctly typed, properly
authenticated, and wrong. Nothing in [Security and identity](../security/index.md) has any reason to
stop them.

SPARC checks two things:

- **Argument grounding** — is every argument traceable to something in the conversation or the tool
  spec, or did the model make it up?
- **Tool selection** — is this the right tool for what was asked?

## What happens on a reject

The call does not run. SPARC's clarification is returned to the agent, so the agent can ask the user for
the missing detail rather than failing or guessing again.

That is the useful part: a blocked call becomes a question instead of an error.

## How it works

SPARC runs on the **outbound** chain, and needs the tool and inference parsers ahead of it.

The reflection logic is the `SPARCReflectionComponent` from the
[agent-lifecycle-toolkit](https://pypi.org/project/agent-lifecycle-toolkit/), a Python package. Cortex
plugins are Go, so the plugin calls a companion SPARC reflection service over HTTP — the same shape
[IBAC](ibac.md) uses for its judge.

All enforcement policy lives in the plugin. The service only returns a verdict.

That means you deploy two things: the plugin, enabled in the pipeline, and the reflection service it
calls.

## Configuration

Configuration is in the
[plugin catalog](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md#sparc).
As with IBAC, decide the failure behaviour before you enable it: if the reflection service is
unreachable, you are choosing between blocking real work and letting ungrounded calls through.

## SPARC and IBAC together

They answer different questions and are meant to run side by side.

| | Question | Fails when |
| --- | --- | --- |
| **SPARC** | Are these arguments grounded? | The model invented a value, or picked the wrong tool. |
| **IBAC** | Does this action match what the user asked for? | The agent was redirected — by injection or drift. |

A hallucinated transaction ID is a SPARC problem: it is on task, just made up. An exfiltration POST is
an IBAC problem: it may be perfectly well-formed, it just is not what anyone asked for.

## Try it

- [SPARC demo](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/finance-sparc) — a finance
  agent asked about a transaction it has no grounding for.

## Related

- [IBAC](ibac.md).
- [RossoCortex](../concepts/cortex.md) — the pipeline and parser ordering.
