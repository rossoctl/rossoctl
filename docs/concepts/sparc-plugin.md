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

---

## Try the Demo!

- [SPARC demo](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/finance-sparc)
