---
title: Rossoctl documentation
sidebar_label: Introduction
description: What Rossoctl does, and where to start.
slug: /
sidebar_position: 0
---

Rossoctl is an open-source platform that runs AI agents on Kubernetes. It gives each agent an
identity that the platform can verify. It controls which services the agent can reach. It records
what the agent did.

Rossoctl does not replace your agent framework. Your agent runs on Rossoctl without a change to its
code, if the agent uses the [A2A protocol](https://a2a-protocol.org/latest/).

## Where to start

| Your goal | Start here | Time |
| --- | --- | --- |
| See the model calls and tool calls that your agent makes | [Quickstart on a laptop](get-started/laptop.md) | 5 minutes |
| Understand the token counts and the cost of a session | [Read the numbers](get-started/reading-the-numbers.md) | — |
| Run the platform and deploy an agent | [Quickstart on Kubernetes](get-started/kubernetes.md) | 20 minutes |
| Put your own agent on the platform | [Bring your own agent](workloads/bring-your-own-agent.md) | — |
| Review the security model | [Security](security/index.md) | — |
| Find a command or a field | [Reference](reference/index.md) | — |

If you do not know which quickstart to use, read [Get started](get-started/index.md).

## The three parts of Rossoctl

**RossoCortex** is the data plane. It is a proxy that runs next to each agent. All traffic between
the agent and an external service goes through this proxy. The proxy applies the identity checks and
the access rules. See [RossoCortex](concepts/core/cortex.md).

**Services** are the parts that an agent uses to do work. They include tools, skills, sandboxes and
memory. See [Concepts](concepts/index.md).

**Tools for operators** include the web console, the `rossoctl` command-line interface and the
Kubernetes operator. See [Install and operate](operate/index.md).

## What Rossoctl gives you

- **An identity for each agent.** SPIRE gives each agent a cryptographic identity. The platform
  identifies the agent before it permits an action.
- **Access by delegation.** An agent that calls a tool for you receives a token. The token is valid
  only for that tool. The token gives the agent no more permissions than you have.
- **Deployment without a code change.** Give Rossoctl a container image or a Git repository. Rossoctl
  builds the agent, starts it and adds it to the platform.
- **A record of each action.** Rossoctl collects traces, network data and token costs for each agent.

## Maturity

Some features are ready for production use. Others are experiments. Read
[Concepts](concepts/index.md) for the status of each feature before you depend on it.
