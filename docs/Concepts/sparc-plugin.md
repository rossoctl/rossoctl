---
description: Verify LLM tool calls before execution.
---

# SPARC (Pre-Tool Reflection)

SPARC is a [Rossoctl Cortex](https://github.com/rossoctl/cortex) plugin that verifies that an agent's proposed tool call is *grounded* in the
conversation and the available tool specifications before it executes — catching
**hallucinated / ungrounded arguments** (e.g. an invented transaction id) and inappropriate
tool selection. On a reflected reject it returns SPARC's clarification to the agent so the
agent re-asks the user; the bad call never runs.

SPARC is the `SPARCReflectionComponent` from the
[`agent-lifecycle-toolkit`](https://pypi.org/project/agent-lifecycle-toolkit/) (ALTK) Python
package, served over HTTP by the companion SPARC reflection service.
Because AuthBridge plugins are Go, this plugin calls the service over HTTP (the same shape
`ibac` uses for its judge). All enforcement policy lives in the plugin; the service only
returns SPARC's verdict.

It is **complementary to [`ibac`](ibac-plugin.md)**: SPARC verifies argument *grounding*;
IBAC verifies *intent alignment* (prompt-injection / exfiltration).

## Generic by design — works for any agent

SPARC's three inputs are collected from exactly what the agent produces, with no per-agent
wiring or out-of-band data:

- **conversation history, including the system prompt** — from the agent's LLM call captured
  by `inference-parser` (`pctx.Extensions.Inference.Messages`, every role preserved);
- **tool specifications in OpenAI function-calling format** — from the same call
  (`pctx.Extensions.Inference.Tools`);
- **the proposed tool call** — from the outbound MCP `tools/call` (`mcp` mode) or from the LLM
  response (`inference` mode).

If the conversation/tool context isn't available (no `inference-parser`, or session tracking
off), the plugin **skips** (`no_inference_context`) rather than reflect on partial data.

## Enforcement is format-aware

The verdict is returned to the agent in the shape it expects, selected by `enforcement`:

- **`mcp` (default — the rossoctl norm).** Gate the outbound MCP `tools/call`. The tool call
  comes from the MCP request; conversation + tool specs are correlated from the session's most
  recent inference request (robust to LLM streaming). On a reflected reject, return SPARC's
  clarification as a **JSON-RPC MCP tool result** (`Reject` + `Violation{Status:200, Body}`);
  the agent's MCP client consumes it like any tool output.
- **`inference` (for non-MCP agents).** Gate the agent's LLM response, where all three inputs
  are co-located. On a reflected reject, rewrite the completion (via `SetResponseBody`) so the
  assistant turn carries the clarification and the tool_call is dropped — norms-correct for any
  OpenAI-style agent.

## On-reject policy

When SPARC returns `reject`, `on_reject_action` decides, with optional score escalation:

| `on_reject_action` | Behavior | Session record |
|---|---|---|
| `observe` | Log only, let the call through (shadow). | `observe` / `reject_observed` |
| `reflect` (default) | Return SPARC's clarification to the agent (MCP result or rewritten completion). | `modify` / `reflected` |
| `deny` | Hard block (403 in `mcp` mode; refusal completion in `inference` mode). | `deny` / `blocked` |

When `deny_score_threshold > 0` and SPARC's `overall_avg_score` (normalized 0..1, higher = better
grounded) is `<=` it, any reject is escalated to `deny`.

> **`fail_policy` defaults to `open`** — when SPARC is unreachable, times out, or returns
> `decision=error`, the proposed tool call is allowed through (and recorded). This is deliberate
> and **diverges from `ibac`, which fails closed**: SPARC is a grounding *quality gate*, not an
> auth control, so reflector downtime shouldn't take the agent's tools offline. Set
> `fail_policy: closed` when you want tool execution gated on reflector availability (e.g. a
> high-assurance deployment where an unverified call is worse than a failed one). The same policy
> governs the case where the conversation/tool context is missing (no `inference-parser` event):
> `open` skips and records `no_inference_context`; `closed` blocks.

See the [Cortex](https://github.com/rossoctl/cortex) repo for configuration and flows.
