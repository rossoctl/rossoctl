
# Rossoctl

[![CI](https://github.com/rossoctl/rossoctl/actions/workflows/ci.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/ci.yaml)
[![E2E K8s 1.35.0 (Kind)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-kind.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-kind.yaml)
[![E2E OCP 4.20.21 (HyperShift)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-hypershift.yaml/badge.svg)](https://github.com/rossoctl/rossoctl/actions/workflows/e2e-hypershift.yaml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/rossoctl/rossoctl/badge)](https://scorecard.dev/viewer/?uri=github.com/rossoctl/rossoctl)
[![GitHub Release](https://img.shields.io/github/v/release/rossoctl/rossoctl)](https://github.com/rossoctl/rossoctl/releases/latest)
[![License](https://img.shields.io/github/license/rossoctl/rossoctl)](LICENSE)
[![Slack](https://img.shields.io/badge/Slack-Join%20us-4A154B?logo=slack&logoColor=white)](https://ibm.biz/rossoctl-slack)

## The Rossoctl umbrella

Rossoctl is the umbrella project for open-source infrastructure to run, connect, and benchmark AI coding agents — built in the open at [rossoctl.dev](https://rossoctl.dev/).

### Core projects

- **[moca](https://github.com/rossoctl/moca)** - Dense, warm process-manager runtime for stateful AI coding agents — sessions resume exactly where they left off (Go)
- **[cortex](https://github.com/rossoctl/cortex)** - The proxy layer between coding agents and everything they touch — see what your agent sends and pay less for it (Go) — [install stats](https://rossoctl.github.io/cortex/install-stats/) (estimated from GitHub download counts, not from user machines)
- **[eventing-lab](https://github.com/rossoctl/eventing-lab)** - Signed-event agent wake path: a Kafka message wakes a coding agent and every step streams back as CloudEvents (Python)
- **[autobench](https://github.com/rossoctl/autobench)** - Automated benchmarking of agentic AI workloads — deploys the workload, collects per-task telemetry, publishes durable artifacts (Python)
- **[state-lab](https://github.com/rossoctl/state-lab)** - Demo flows exploring state requirements for distributed agents, from durability to passability

For context & governance, automation, and the other repositories under the umbrella, see the [Rossoctl organization](https://github.com/rossoctl) on GitHub.

### This repository

This repository is the **agentic platform installer for Kubernetes**: the installer, the web console, and the documentation for the Rossoctl platform.

- What the platform provides and how to install it → **[The Rossoctl platform installer](./INSTALLER.md)**
- Straight to the commands → [Quickstart on Kubernetes](./docs/get-started/kubernetes.md)

## Documentation

Full documentation is at [rossoctl.dev/docs](https://rossoctl.dev/docs/).

| Topic | Link |
|-------|------|
| **Get started on your laptop** | [Quickstart — laptop](./docs/get-started/laptop.md) (no Kubernetes) |
| **Get started on Kubernetes** | [Quickstart — Kubernetes](./docs/get-started/kubernetes.md) |
| **What is ready, what is an experiment** | [Concepts](./docs/concepts/index.md) |
| **Architecture** | [Architecture](./docs/concepts/core/architecture.md) |
| **Bring your own agent** | [Bring your own agent](./docs/workloads/bring-your-own-agent.md) |
| **Deploy agents and tools** | [Deploy an agent](./docs/workloads/deploy-an-agent.md) · [Deploy a tool](./docs/workloads/deploy-a-tool.md) |
| **Skills** | [Skills](./docs/concepts/experiments/skills.md) |
| **Identity, security, and AuthBridge** | [Security overview](./docs/security/index.md) · [AuthBridge](./docs/security/authbridge.md) |
| **Install and operate** | [Install and operate](./docs/operate/index.md) |
| **CLI, CRDs, glossary** | [Reference](./docs/reference/index.md) |
| **Demos and examples** | [Resources](./docs/resources.md) |
| **Troubleshooting** | [Troubleshooting](./docs/operate/troubleshooting.md) |
| **Developer guide** | [Developer's Guide](./docs/_internal/dev-guide.md) |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## Contact

To reach the maintainer team, email **rossoctl-maintainers@googlegroups.com** or join us on [Slack](https://ibm.biz/rossoctl-slack).

## License

[Apache 2.0](./LICENSE)

## QR Code for rossoctl.dev

This QR Code links to <https://rossoctl.dev>

<img src="./docs/images/Rossoctl.QRcode.png" alt="rossoctl.dev QR Code" width="200"/>
