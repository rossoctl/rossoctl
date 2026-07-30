---
title: What is Rossoctl?
description: Introduction to the agent platform.
---

### Rossoctl: Solving Real Problems in Agentic AI

As a user of AI agents, you want to rein in their token use, manage their access permissions, ensure they don't drift from the goal, prevent mistakes from affecting your system, and ensure the skills you use are safe and optimal. As a platform provider, you want to know how you can help platform users answer these questions and get answers to them yourself.

**Rossoctl** provides solutions to these problems. It comes in the form of RossoCortex — a data plane controller for agent interactions. We are also working on a set of services agents will be able to use.

**RossoCortex** sits on the path of each interaction of an agent with the external world: LLMs, users, tools, and other agents. It observes and modifies them. It uses this visibility and control to provide pluggable capabilities: identity and access control (AuthBridge), context compaction ([ContextGuru](../concepts/contextguru.md)), semantic tool reflection ([SPARC](../concepts/sparc-plugin.md)), and intent-based access control ([IBAC](../concepts/ibac-plugin.md)).

There are three types of agents:

- Agent harnesses like Claude or OpenClaw, which users customize using skills and prompts
- Agents built with custom agent loops on top of popular frameworks like LangGraph or CrewAI
- Agents that rely on low-level SDKs such as OpenAI and MCP, which target specific tasks and are often AI-generated

RossoCortex provides a uniform control surface that works with all styles of agents. It can be deployed as a gateway or sidecar proxy, packaged as a CLI and plugged into harness hooks, or integrated into agent frameworks or SDKs.