---
title: Get started
sidebar_label: Which path to take
description: Choose between the laptop quickstart and the Kubernetes quickstart.
sidebar_position: 1
---

There are two ways to start. Choose the one that matches your goal.

## Quickstart on a laptop

Time: approximately 5 minutes.

You install one program. You do not need a Kubernetes cluster and you do not need a model API key.
The program shows the model calls, the tool calls and the agent messages that your agent makes.

Choose this path if you want to see how Rossoctl works before you install the full platform. Choose
it also if you want to reduce the token cost of an agent.

Go to [Quickstart on a laptop](laptop.md).

## Quickstart on Kubernetes

Time: approximately 20 minutes.

You install the full platform on a local Kubernetes cluster. The installation includes the operator,
Keycloak, the web console and a sample agent.

Choose this path if you want to deploy agents, or if you must evaluate Rossoctl as a platform.

Your container runtime must have 18 GiB of memory and 6 CPUs. A smaller machine can complete the
installation, but a build from source then fails.

Go to [Quickstart on Kubernetes](kubernetes.md).

## After a quickstart

Do these steps in order:

1. [Configure a model](configure-a-model.md). An agent cannot answer a question until you give it a
   model.
2. [Deploy your first agent](first-agent.md).
3. [Connect your first tool](first-tool.md).
4. [Install the CLI](cli.md), if you prefer a terminal to the web console.

## Next

- To put your own agent on the platform, read [Bring your own agent](../workloads/bring-your-own-agent.md).
- To enable identity and token exchange, read [Security](../security/index.md).
- To install on OpenShift or with Helm, read [Install and operate](../operate/index.md).
