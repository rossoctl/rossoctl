---
title: Agents and tools
sidebar_label: Overview
description: Put your own agents and tools on the platform.
sidebar_position: 1
---

This section is for a developer who has agent code and wants to run it on Rossoctl.

Read [Bring your own agent](bring-your-own-agent.md) first. It is short, and it tells you whether your
agent needs a change before the other pages apply.

| Page | Use it when |
| --- | --- |
| [Bring your own agent](bring-your-own-agent.md) | You adapt existing agent code. |
| [Deploy an agent](deploy-an-agent.md) | You need each deployment option: sources, builds, variables and secrets. |
| [Deploy a tool](deploy-a-tool.md) | You package an MCP tool. |

If you have not deployed anything yet, do [Deploy your first agent](../get-started/first-agent.md)
first. That page uses the same steps with a sample that is known to operate.

## Related experiments

Three experimental features extend an agent. Each one is optional.

| Feature | What it adds |
| --- | --- |
| [MCP Gateway](../concepts/experiments/mcp-gateway.md) | One address for all tools. |
| [Skills](../concepts/experiments/skills.md) | Reusable instructions that the cluster holds. |
| [Agent context](../concepts/experiments/agent-context.md) | Durable storage for files and memory. |
