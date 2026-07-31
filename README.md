
# Rossoctl

[![CI](https://github.com/rossoctl/rossoctl/actions/workflows/ci.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/ci.yaml)
[![E2E K8s 1.35.0 (Kind)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-kind.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-kind.yaml)
[![E2E OCP 4.20.21 (HyperShift)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-hypershift.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-hypershift.yaml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/rossoctl/rossoctl/badge)](https://scorecard.dev/viewer/?uri=github.com/rossoctl/rossoctl)
[![GitHub Release](https://img.shields.io/github/v/release/rossoctl/rossoctl)](https://github.com/rossoctl/rossoctl/releases/latest)
[![License](https://img.shields.io/github/license/rossoctl/rossoctl)](LICENSE)
[![Slack](https://img.shields.io/badge/Slack-Join%20us-4A154B?logo=slack&logoColor=white)](https://ibm.biz/rossoctl-slack)

## Platform primitives for trustworthy AI agents

Rossoctl is a set of platform primitives for agent security, resilience, reliability, and efficiency. It has three parts: **RossoCortex**, a data plane; a set of callable **services**; and **tooling** for observability, security, governance, and administration.

It is open source, framework-neutral, and built on open standards, supporting [A2A](https://a2a-protocol.org/latest/) and [MCP](https://modelcontextprotocol.io).

> **Get started** → [Quickstart](./docs/getting-started/install.md) · Learn more at [rossoctl.dev](https://rossoctl.dev/)

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
git checkout v0.6.0

# Copy and configure secrets (optional)
cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# Edit charts/rossoctl/.secrets.yaml with your values

# Deploy to Kind cluster
scripts/kind/setup-rossoctl.sh --with-ui --with-spire --with-agent-sandbox --with-builds
```

Use `scripts/kind/setup-rossoctl.sh --help` for all available options. For detailed instructions including OpenShift, refer to the [Installation Guide](./docs/getting-started/install.md).

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

To learn how to deploy agents and MCP tools, follow the **[Weather Agent Demo](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/weather-agent/demo-ui.md)** — the recommended getting-started tutorial that walks you through deploying an agent and tool via the UI and chatting with it end-to-end. For more demos, see the [full demo list](./docs/demos/README.md).

## Documentation

| Topic | Link |
|-------|------|
| **Installation** | [Installation Guide](./docs/getting-started/install.md) (Kind & OpenShift) |
| **Components** | [Component Details](./docs/components.md) |
| **Demos & Tutorials** | [Demo Documentation](./docs/demos/README.md) |
| **Developing Rossoctl Apps** | [Application Development Guide](./docs/developing-rossoctl-app.md) · [App Demo Example](./rossoctl/examples/app-demo/README.md) |
| **Import Your Own Agent** | [New Agent Guide](./docs/new-agent.md) |
| **Import Your Own Tool** | [New Tool Guide](./docs/new-tool.md) |
| **Skills Configuration & Usage** | [Skills Guide](./docs/skills.md) |
| **Architecture Details** | [Technical Details](./docs/concepts/tech-details.md) |
| **Identity, Security, and Auth Bridge** | [Identity and Auth Bridge](./docs/concepts/identity-guide.md) |
| **Fine-Grained Zero-Trust Access Control** | [Access Control](./docs/access-control/README.md) |
| **Developer Guide** | [Contributing](./docs/dev-guide.md) |
| **Troubleshooting** | [Troubleshooting Guide](./docs/troubleshooting.md) |
| **Blog Posts** | [Rossoctl Blog](./docs/blogs.md) |

## Supported Protocols

- **[A2A (Agent-to-Agent)](https://a2a-protocol.org/latest/)** — Standard protocol for agent communication
- **[MCP (Model Context Protocol)](https://modelcontextprotocol.io)** — Protocol for tool/server integration

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## Contact

To reach the maintainer team, email **rossoctl-maintainers@googlegroups.com** or join us on [Slack](https://ibm.biz/rossoctl-slack).

## License

[Apache 2.0](./LICENSE)

## QR Code for rossoctl.dev

This QR Code links to <https://rossoctl.dev>

<img src="./docs/images/Rossoctl.QRcode.png" alt="rossoctl.dev QR Code" width="200"/>
