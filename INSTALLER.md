# The Rossoctl platform installer

This repository contains the **agentic platform installer for Kubernetes**: the installer, the web console, and the documentation for the Rossoctl platform. The platform is a set of platform primitives for agent security, resilience, reliability, and efficiency. It has three parts: **RossoCortex**, a data plane; a set of callable **services**; and **tooling** for observability, security, governance, and administration.

It is open source, framework-neutral, and built on open standards, supporting [A2A](https://a2a-protocol.org/latest/) and [MCP](https://modelcontextprotocol.io).

> **Get started** → [Quickstart](./docs/get-started/kubernetes.md) · Learn more at [rossoctl.dev](https://rossoctl.dev/)

## The problem

AI agents are not traditional cloud applications. They choose their tools at runtime, blur the line between data and instructions, drift from their original goals, and cannot reliably report what they actually did.

Kubernetes decoupled application logic from the guarantees production demands around admission, isolation, and failure recovery. An agent platform has to do the same for agents: decouple agent logic from the guarantees around admission, isolation, and failure recovery, so those guarantees hold no matter which framework built the agent.

## RossoCortex, the data plane

RossoCortex is an intercept. It sits transparently between an agent and everything external it touches: models, tools, users, and other agents. From that single vantage point it enforces guarantees an agent cannot provide on its own.

It is flexible by design: it works with different agent types, including black-box harnesses, integrates with different sandboxes, and works across container network choices.

| Capability | Status |
|------------|--------|
| Agent identity — every agent carries a verifiable identity, so the platform knows who is acting before it decides what they may do | Ready |
| Authorization and access | Ready |
| Intent-based access | beta in 0.7 |
| Tool semantic validation | beta in 0.7 |
| Context compaction | alpha in 0.7 |
| Data-flow analysis | alpha in 0.7 |
| Failure recovery | beta in 0.7 |
| User interaction | beta in 0.7 |

Agents integrate with RossoCortex through multiple paths — an **SDK**, agent **hooks**, a **gateway**, or an **orchestration** layer — behind a common intercept abstraction that spans MCP tools, API/CLI tools, and agents.

## Rossoctl services

Beyond the data plane, Rossoctl provides the building blocks agents need to do real work — lowering the risk of agentic workloads while using resources more efficiently:

- **Skills** — reusable, governed capabilities an agent can draw on, versioned and controlled rather than pasted in
- **Tools**
- **Memory**
- **Knowledge base**
- **Sandboxes**

## Quick Start

### Prerequisites

- Python ≥3.9 with [uv](https://docs.astral.sh/uv/getting-started/installation) installed
- Docker Desktop, Rancher Desktop, or Podman (16GB RAM, 4 cores recommended)
- [Kind](https://kind.sigs.k8s.io), [kubectl](https://kubernetes.io/docs/tasks/tools/), [Helm](https://helm.sh/docs/intro/install/)
- [Ollama](https://ollama.com/download) for local LLM inference

### Install

```bash
# Clone the repository
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl

# Check out the latest release
git checkout v0.7.0

# Copy and configure secrets (optional)
cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# Edit charts/rossoctl/.secrets.yaml with your values

# Deploy to Kind cluster
scripts/kind/setup-rossoctl.sh --with-ui --with-spire --with-agent-sandbox --with-builds
```

Use `scripts/kind/setup-rossoctl.sh --help` for all available options. For detailed instructions including OpenShift, refer to the [Installation Guide](./docs/operate/install-kubernetes.md).

### Access the UI

```bash
# Show service URLs and credentials
.github/scripts/local-setup/show-services.sh

open http://rossoctl-ui.localtest.me:8080
# Login with credentials from show-services.sh output
```

From the UI you can:
- Import and deploy A2A agents from any framework
- Deploy MCP tools directly from source
- Test agents interactively
- Monitor traces and network traffic

To learn how to deploy agents and MCP tools, follow the **[Weather Agent Demo](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/weather-agent/demo-ui.md)** — the recommended getting-started tutorial that walks you through deploying an agent and tool via the UI and chatting with it end-to-end. For more demos, see the [full demo list](./docs/resources.md).

## Documentation

Full documentation is at [rossoctl.dev/docs](https://rossoctl.dev/docs/). The source lives in the [`docs/`](./docs/index.md) directory of this repository.
