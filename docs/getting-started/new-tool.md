---
description: How to deploy your code onto Rossoctl.
sidebar_label: Import a New Tool
---

# Importing a New MCP Tool into the Platform

## Overview

MCP (Model Context Protocol) tools extend the capabilities of AI agents by providing access to external services, APIs, and resources. Rossoctl allows you to deploy MCP tools either from source code or from pre-existing container images.

## Pre-requisites

### Deploying from Source

Before importing a new tool from source, ensure that:

1. The tool code is hosted on GitHub and is public or at least accessible using the GitHub credentials provided [during the Rossoctl installation](./install.md).
2. The tool code is organized within a sub-directory of the Git repository (not in the root directory) that contains a `Dockerfile`.

## Tool Examples

See the [Rossoctl agent examples repo](https://github.com/rossoctl/examples/tree/main/mcp) for a variety of MCP tool examples.

## Steps to Import a New Tool

### Step 1: Access the Import New Tool Section

- Log in to the Rossoctl UI.
- Navigate to the "Import New Tool" section.

### Step 2: Configure Environment Variables

- Manually add environment variables required by your tool.
- Alternatively, import environment variables from a `.env` file hosted on GitHub.

### Step 3: Select Deployment Method

#### Deploy from an existing Docker image

- Select "deploy from existing image" as the deployment method, and provide the URI of the image in a container registry

#### Deploy from source code

1. Select "Build from source" as the deployment method
2. In "Git Repository URL", enter the root of your GitHub repository where your project lives.
3. In "Git Branch or Tag" - If your project exists in a different branch than Main, such as a PR branch, specify the branch or tag
4. Under "Specify Source Subfolder" type the name of the subfolder of your Git repo where the code can be found.

### Step 4: Configure Build Options (Source Builds Only)

When building from source, you can configure additional build options:

#### Build Strategy

Rossoctl uses [Shipwright](https://shipwright.io) to build container images. The build strategy is automatically selected based on your registry:

| Registry Type | Strategy | Description |
|--------------|----------|-------------|
| Internal (Kind cluster) | `buildah-insecure-push` | For registries without TLS |
| External (quay.io, ghcr.io, docker.io) | `buildah` | For registries with TLS |

You can override the strategy in the "Build Configuration" section.

#### Registry Configuration

- **Registry URL**: Where to push the built image (e.g., `registry.cr-system.svc.cluster.local:5000` for internal, `quay.io/myorg` for external)
- **Registry Secret**: Name of the Kubernetes Secret containing registry credentials (required for external registries)
- **Image Tag**: Version tag for the image (default: `v0.0.1`)

#### Advanced Build Options

Expand "Advanced Build Options" to configure:
- **Dockerfile path** - Default is `Dockerfile` in the context directory
- **Build timeout** - Default is 15 minutes
- **Build arguments** - Optional build-time variables (KEY=VALUE format)

### Step 5: Build and Deploy

Press the "Build & Deploy Tool" button.

Once the build succeeds, Rossoctl automatically:
1. Creates a Deployment and Service for the tool with the built image
2. Rossoctl creates an HTTPRoute for gateway access if "Enable external access to the tool endpoint" is checked
3. Redirects you to the Tool detail page

For image deployments, the Deployment and Service are created immediately.

## Using Tools with Agents

Once deployed, tools can be used by agents through direct connection or via the MCP Gateway. Agents invoke tools using the MCP protocol.

### Configuring MCP_URL / MCP_URLS

Agents connect to tools using environment variables:
- `MCP_URL` (singular) - For agents that use a single tool or connect via the MCP Gateway
- `MCP_URLS` (plural) - For agents that connect directly to multiple tools (comma-separated list)

The example agents in the [agent-examples repository](https://github.com/rossoctl/examples) include `.env.openai` or `.env.ollama` files with default values that assume the tool is deployed in the **same namespace** as the agent.

## Related Documentation

- [Importing a New Agent](./new-agent.md)
- [Components Overview](../concepts/components.md)
- [Demo: Weather Agent and Tool](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/weather-agent/demo-ui.md)

### Deployment Issues

See the [Troubleshooting](/docs/users-guides/troubleshooting) section.
