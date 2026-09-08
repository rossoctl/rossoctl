---
title: Concepts
sidebar_label: Overview
description: The ideas you need before configuring anything.
sidebar_position: 1
---

These pages explain how Rossoctl works. They contain no procedures — for those, see
[Build agents and tools](../workloads/index.md) and [Deploy and operate](../operate/index.md).

- **[Agents and tools](agents-and-tools.md)** — what Rossoctl considers an agent, what it considers
  a tool, and the two protocols that define them.
- **[RossoCortex](cortex.md)** — the data plane. Where it sits, the four points it controls, and how
  its plugin pipeline works.
- **[Identity and trust](identity.md)** — how a workload gets an identity it can prove, and how that
  identity turns into access.
- **[Control plane and custom resources](control-plane.md)** — the operator, `AgentRuntime`, and
  `AgentCard`.

If you are evaluating rather than building, read [Architecture at a glance](../overview/architecture.md)
first — it is shorter and covers the same ground.
