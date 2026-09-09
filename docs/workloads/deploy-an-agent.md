---
title: Deploy an agent
description: "Each option for a deployment: images, source builds, variables and secrets."
sidebar_position: 3
---

There are three ways to deploy an agent: the console, the CLI, and a custom resource. All three produce
the same result, which is a Deployment and an `AgentRuntime` resource that points to it.

For a first deployment, use [Deploy your first agent](../get-started/first-agent.md).

## Deploy from a container image

This method is the fastest. It is also the only method that operates without the `--with-builds`
option.

### With the console

Select **Agents**, then **Import new agent**, then **Deploy from existing image**. Enter the image
address, set the environment variables, and select **Deploy**.

### With the CLI

```bash
rossoctl agents import from-image \
  --name orders \
  --containerImage ghcr.io/acme/orders:v1.2.0 \
  --envVar LOG_LEVEL=debug

rossoctl agents wait orders --timeout 5m
```

| Option | Function |
| --- | --- |
| `--imagePullSecret NAME` | Names a Secret for a private registry. |
| `--envVar KEY=VALUE` | Sets one variable. You can repeat the option. The value is literal, and can contain a comma. |
| `--envVarsURL URL` | Reads `key=value` lines from an address. |
| `--deployment-type` | Selects `deployment`, which is the default, or `statefulset`, or `sandbox`. |
| `--context NAME:PATH` | Attaches an [agent context](../concepts/experiments/agent-context.md). |
| `--additionalParameterJSON` | Sends a field that has no option. |

If `--envVar` and `--envVarsURL` set the same variable, `--envVar` wins. The order of the options does
not change this result.

## Build from source

Rossoctl builds your image with [Shipwright](https://shipwright.io) and then deploys the result.

Requirements:

- The `--with-builds` option at installation time, and 6 available CPUs.
- The code on GitHub. The repository must be public, or reachable with the token that you gave to the
  installer.
- The agent in a **subdirectory** that contains a `Dockerfile`. The agent must not be in the root
  directory.

In the console, select **Build from source** and complete these fields:

| Field | Value |
| --- | --- |
| Git repository URL | The root of the repository, not the subdirectory. |
| Git branch or tag | The default branch, or the branch that you name. |
| Source subfolder | The directory that contains your `Dockerfile`. |

The console then shows a build progress page. That page gives the phase, which is `Pending`, then
`Running`, then `Succeeded` or `Failed`. It also gives the duration and the configuration. After a
successful build, Rossoctl creates the Deployment and the Service, adds an `HTTPRoute` if you enabled
external access, and opens the page of the agent.

### The build strategy

Rossoctl selects the strategy from the target registry.

| Registry | Strategy | Reason |
| --- | --- | --- |
| In the cluster, on Kind | `buildah-insecure-push` | The internal registry has no TLS. |
| External: quay.io, ghcr.io, docker.io | `buildah` | TLS is available. |

To select a different strategy, use the **Build Configuration** section.

### Other build options

| Option | Default |
| --- | --- |
| Dockerfile path | `Dockerfile`, in the source subfolder |
| Build timeout | 15 minutes |
| Build arguments | None. The format is `KEY=value`. |

## Environment variables

You can add each variable in the form, or import a `.env` file from GitHub. A simple value has this
form:

```ini
MCP_URL=http://weather-tool:8080/mcp
```

### To reference a Secret or a ConfigMap

Do not put a secret in a `.env` file. Give a JSON value instead. Rossoctl converts the JSON value into a
Kubernetes `valueFrom` reference.

This example is the complete form:

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

This example is a short form. Rossoctl adds the `valueFrom` level for you:

```ini
OPENAI_API_KEY='{"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}'
```

A ConfigMap uses the same form:

```ini
WEATHER_CONFIG='{"configMapKeyRef": {"name": "weather-config", "key": "settings"}}'
```

Keep the single quotation marks. Without them, the parser divides the JSON value.

Create the Secret first, in the namespace that will run the agent:

```bash
kubectl create secret generic openai-secret \
  --from-literal=apikey='<YOUR_API_KEY>' \
  -n team1
```

## The deployment types

| Type | Use it for |
| --- | --- |
| `deployment` | An agent that keeps no state. This type is the default. |
| `statefulset` | An agent that has durable storage. |
| `sandbox` | An agent that needs stronger isolation. See [Sandboxes](../concepts/experiments/sandboxes.md). |

## With a custom resource

If you deploy with GitOps, write the Deployment, and then add this resource:

```yaml
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: orders
  namespace: team1
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orders
```

The operator does the remaining work. See
[Custom resources](../reference/custom-resources.md).

## Change the RossoCortex configuration of one agent

To read the current inbound and outbound plugin chains, in execution order:

```bash
rossoctl agents authbridge get orders
```

To replace them:

```bash
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml
```

The command sends the file without a change, so your comments and your key order remain. The server
validates the file. Add `--wait` to wait until the change is active.

:::note
The `--wait` option compares the new configuration with the configuration that was active before the
command. It therefore cannot confirm a configuration that is already active. In that case the command
reaches its time limit and exits with an error.
:::

## Send a message to the agent

Select the agent, select **Details**, then select **Chat**.

## Delete the agent

```bash
rossoctl agents delete orders
```

This command does not delete an
[agent context](../concepts/experiments/agent-context.md). Delete the context separately.

## Related pages

- [Bring your own agent](bring-your-own-agent.md) gives the requirements for your code.
- [Deploy a tool](deploy-a-tool.md)
- [Troubleshooting](../operate/troubleshooting.md)
