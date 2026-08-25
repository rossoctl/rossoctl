---
description: How to deploy your code onto Rossoctl.
sidebar_label: Import a New Agent
sidebar_position: 30
---

# Importing a New Agent into the Platform from a Code Base

## Pre-requisites

You may either deploy from source code or from a container image. When deploying from source code, Rossoctl retrieves the code from GitHub. Rossoctl builds your agent by deploying into a container based up on the `Dockerfile` you provide.

Rossoctl UI allows importing custom environment variables from URLs and files.

### Deploying from Source

Before importing a new agent from source, ensure that:

1. The agent code is hosted on GitHub and is public or at least accessible using the GitHub credentials provided [during the Rossoctl installation](./install.md).
2. The agent code is organized within a sub-directory of the Git repository (not in the root directory) that contains a `Dockerfile`.

## Agent Examples

See the [Rossoctl agent examples repo](https://github.com/rossoctl/examples) for a variety of agent examples.

## Steps to Import a New Agent

To import a new agent into the platform, follow these steps:

### Step 1: Access the Import New Agent Section

- Log in to the Rossoctl UI.
* Navigate to the "Import New Agent" section.

### Step 2: Configure Environment Variables

- Manually add environment variables required by your agent.
* Alternatively, import environment variables from a `.env` file hosted on GitHub.

### Using Secrets / ConfigMaps from .env files

The Rossoctl UI supports importing environment variables from a `.env` file. To safely reference Kubernetes Secrets or ConfigMaps from a `.env` file (instead of embedding secret plaintext), the `.env` value may contain a JSON object which will be interpreted as a structured environment entry and mapped to Kubernetes `valueFrom` entries in the agent's manifest.

Examples (in your `.env` file):

Plain value:

```ini
MCP_URL=http://weather-tool:8080/mcp
```

Secret reference (valueFrom provided explicitly):

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

Secret shorthand (top-level secretKeyRef will be wrapped into valueFrom):

```ini
OPENAI_API_KEY='{"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}'
```

ConfigMap reference example:

```ini
WEATHER_CONFIG='{"configMapKeyRef": {"name": "weather-config", "key": "settings"}}'
```

**Quick Secret creation example**

Below is a minimal example showing how to create a Kubernetes Secret with an API key and then reference it from your `.env` file.

Create the Secret (replace `<NAMESPACE>` and `<YOUR_API_KEY>`):

```bash
kubectl create secret generic openai-secret \
	--from-literal=apikey='<YOUR_API_KEY>' \
	-n <NAMESPACE>
```

Then in your `.env` file reference the Secret using JSON (note the single quotes around the JSON to keep it as one value in the `.env`):

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

When Rossoctl imports this `.env` entry it will add an env var to the generated Component manifest that uses `valueFrom.secretKeyRef` to pull the `apikey` from the `openai-secret` in the target namespace.


### Step 3: Select Deployment Method

#### Deploy from an existing Docker image

- Select "deploy from existing image" as the deployment method, and provide the URI of the image in a container registry

#### Deploy from source code

1. Select "Build from source" as the deployment method
2. In "Git Repository URL", enter the root of your GitHub repository where your agent project lives.
3. In "Git Branch or Tag" - If your agent project exists in a different branch than Main, such as a PR branch, specify the branch or tag
4. Under "Specify Source Subfolder" type the name of the subfolder of your Git repo where the agent code can be found.

## Step 4: Configure Build Options (Source Builds Only)

When building from source, you can configure additional build options:

### Build Strategy

Rossoctl uses [Shipwright](https://shipwright.io) to build container images. The build strategy is automatically selected based on your registry:

| Registry Type | Strategy | Description |
|--------------|----------|-------------|
| Internal (Kind cluster) | `buildah-insecure-push` | For registries without TLS |
| External (quay.io, ghcr.io, docker.io) | `buildah` | For registries with TLS |

You can override the strategy in the "Build Configuration" section.

### Advanced Build Options

Expand "Advanced Build Options" to configure:
- **Dockerfile path** - Default is `Dockerfile` in the context directory
- **Build timeout** - Default is 15 minutes
- **Build arguments** - Optional build-time variables (KEY=value format)

## Step 5: Build New Agent

Press the "Build New Agent" button. You will be redirected to a **Build Progress** page that shows:
- Build phase (Pending → Running → Succeeded/Failed)
- Build duration
- Source configuration details
- Agent configuration that will be applied

Once the build succeeds, Rossoctl automatically:
1. Creates a Deployment + Service with the built image
2. Creates an HTTPRoute for external access (if enabled, via "Enable external access to the agent endpoint" in the UI)
3. Redirects you to the Agent detail page

## Testing agents

1. Once the deployment is complete, click the "Details" tab
2. Click "Chat" to chat with the agent

### Deployment Issues

See the [Troubleshooting](../users-guides/troubleshooting.md) section.
