---
title: What is Rossoctl?
description: Introduction to the Rossoctl agent platform
---

Rossoctl is a *framework-neutral*, *scalable*, and *secure* platform for deploying and orchestrating AI agents through standardized agent communication protocols (A2A, MCP).

Rossoctl gives you:

- Zero-Trust Security Architecture
- Authentication and Authorization
- Trusted workload identity (SPIRE)
- Deployment and Configuration
- Scaling and Fault-tolerance
- Discovery of agents and tools
- State Persistence

Rossoctl addresses these challenges by enhancing existing agent frameworks with production-ready, framework-neutral infrastructure.

## Supported AI Use‑Case Types

Rossoctl is designed to support a broad range of AI‑agent deployment patterns, including knowledge services, synchronous and asynchronous user‑authorized assistants, continuous monitoring agents, and event‑driven workflows.

## Architecture

The goal of Rossoctl is to provide a pluggable agentic platform blueprint. Key functionalities are currently organized into four key pillars:
1. Lifecycle Orchestration
2. Networking
3. Security
4. Observability

## Core Components

Rossoctl provides a set of components and assets that make it easier to manage AI agents and tools and integrate their fine-grained authorization into modern cloud-native environments.

| Component | Description |
|-----------|-------------|
| **Rossoctl UI** | Dashboard for deploying agents/tools as Kubernetes Deployments, interactive testing, and monitoring |
| **[Identity & Auth Bridge](/docs/concepts/identity-guide)** | Identity pattern assets that capture common authorization scenarios and provide reusable building blocks for implementing consistent authorization across services |
| **[Agent Lifecycle Operator](https://github.com/rossoctl/operator)** | Kubernetes admission webhook for building agents from source, managing lifecycle, and coordinating platform services |
| **[MCP Gateway](https://github.com/Kuadrant/mcp-gateway/)** | Unified gateway for Model Context Protocol (MCP) servers and tools. It acts as the entry point for policy enforcement, handling requests and routing them through the appropriate authorization patterns |
