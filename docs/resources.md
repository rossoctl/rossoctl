---
title: Resources
description: Demonstrations, examples, community and support.
sidebar_position: 7
---

## Demonstrations

Each demonstration is a complete example that you can run.

| Demonstration | What it shows |
| --- | --- |
| [Weather agent](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/weather-agent) | An agent and a tool, deployed from the web console, with token exchange between them. Start with this one. |
| [Intent-based access](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/ibac) | An agent reads a poisoned email and tries to send data to an external server. See [Intent-based access](concepts/experiments/intent-based-access.md). |
| [Tool validation](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/finance-sparc) | An agent invents a transaction identifier. See [Tool call validation](concepts/experiments/tool-validation.md). |
| [Context compaction](https://github.com/rossoctl/cortex/tree/main/authbridge/demos/context-guru) | Tool output that is larger than the context window of the model. See [Context compaction](concepts/experiments/context-compaction.md). |

The weather agent demonstration needs a Kubernetes cluster. See
[Quickstart on Kubernetes](get-started/kubernetes.md).

## Example agents and tools

[rossoctl/examples](https://github.com/rossoctl/examples) contains agents for several frameworks. The
MCP tools are in [examples/mcp](https://github.com/rossoctl/examples/tree/main/mcp).

Each example agent has an `.env.openai` file and an `.env.ollama` file. The default values in these
files assume that the tool is in the same namespace as the agent.

## Security tests

[capture-the-flag](https://github.com/rossoctl/capture-the-flag) contains attack scenarios. Run them
to confirm what the security model prevents.

## Repositories

| Repository | Contents |
| --- | --- |
| [rossoctl](https://github.com/rossoctl/rossoctl) | Installer, web console, backend and these documents |
| [operator](https://github.com/rossoctl/operator) | The Kubernetes operator and the custom resources |
| [cortex](https://github.com/rossoctl/cortex) | The data plane, its plugins and its demonstrations |
| [rossoctl-cli](https://github.com/rossoctl/rossoctl-cli) | The command-line interface |
| [examples](https://github.com/rossoctl/examples) | Example agents and tools |

The [organization profile](https://github.com/rossoctl) lists every repository, and marks each one as
core or experimental.

## Releases

- [Releases and release notes](https://github.com/rossoctl/rossoctl/releases)
- [Concepts](concepts/index.md) gives the status of each feature in the current release.

## Read and watch

- [Blog](https://medium.com/rossoctl-the-agentic-platform)
- [Videos](https://www.youtube.com/@Rossoctl)

## Get help

| Channel | Use it for |
| --- | --- |
| [Slack](https://ibm.biz/rossoctl-slack) | Questions. This is the fastest channel. |
| [Issues](https://github.com/rossoctl/rossoctl/issues) | Defects and feature requests |
| `rossoctl-maintainers@googlegroups.com` | Messages to the maintainer team |

## Contribute

Read the [contributing guide](https://github.com/rossoctl/rossoctl/blob/main/CONTRIBUTING.md). The
[maintainers file](https://github.com/rossoctl/rossoctl/blob/main/MAINTAINERS.md) lists the
maintainers.

Corrections to these documents are welcome. Each page has an **Edit this page** link.

Rossoctl uses the [Apache 2.0 licence](https://github.com/rossoctl/rossoctl/blob/main/LICENSE).
