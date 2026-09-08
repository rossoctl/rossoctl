---
title: Deploy an agent
description: Every option for getting an agent onto the platform — image, source, environment, builds.
sidebar_position: 3
---

There are three ways to deploy an agent: the console, the CLI, or custom resources. All three end up
in the same place — a Deployment with an `AgentRuntime` enrolling it.

For a first walkthrough, use [Deploy your first agent](../get-started/first-agent.md).

## From a container image

The fastest path, and the only one that works without `--with-builds`.

### Console

**Agents → Import new agent → Deploy from existing image.** Give it the image URI, set the
environment, and deploy.

### CLI

```bash
rossoctl agents import from-image \
  --name orders \
  --containerImage ghcr.io/acme/orders:v1.2.0 \
  --envVar LOG_LEVEL=debug

rossoctl agents wait orders --timeout 5m
```

Useful flags:

| Flag | What it does |
| --- | --- |
| `--imagePullSecret NAME` | Secret for a private registry. |
| `--envVar KEY=VALUE` | One variable. Repeatable. Values are literal, commas included. |
| `--envVarsURL URL` | Newline-separated `key=value` fetched from a URL. |
| `--deployment-type` | `deployment` (default), `statefulset`, or `sandbox`. |
| `--context NAME:PATH` | Mount an [agent context](agent-context.md). |
| `--additionalParameterJSON` | Send request fields the CLI has no flag for. A JSON object, or a file containing one. |

Where both name the same variable, `--envVar` wins over `--envVarsURL` regardless of flag order.

## From source

Rossoctl builds your image with [Shipwright](https://shipwright.io) and deploys the result.

**Requirements:**

- `--with-builds` at install time, and 6 CPUs available on the node.
- The code on GitHub, public or reachable with the token given at install time.
- The agent in a **subdirectory** containing a `Dockerfile` — not the repository root.

In the console, choose **Build from source** and fill in:

| Field | Value |
| --- | --- |
| Git repository URL | The repository root, not the subdirectory. |
| Git branch or tag | Defaults to the default branch. Set this for a PR branch. |
| Source subfolder | The directory holding your `Dockerfile`. |

You are taken to a build progress page showing the phase (Pending → Running → Succeeded or Failed),
duration, and the configuration that will be applied. On success Rossoctl creates the Deployment and
Service with the built image, adds an `HTTPRoute` if you enabled external access, and opens the agent
detail page.

### Build strategy

Chosen automatically from the target registry:

| Registry | Strategy | Why |
| --- | --- | --- |
| In-cluster (Kind) | `buildah-insecure-push` | The internal registry has no TLS. |
| External — quay.io, ghcr.io, docker.io | `buildah` | TLS available. |

Override it under **Build Configuration** if you need to.

### Advanced build options

| Option | Default |
| --- | --- |
| Dockerfile path | `Dockerfile` in the context directory |
| Build timeout | 15 minutes |
| Build arguments | none — `KEY=value` pairs |

## Environment variables

You can add variables by hand, or import a `.env` file hosted on GitHub. A plain value is what you
would expect:

```ini
MCP_URL=http://weather-tool:8080/mcp
```

### Referencing Secrets and ConfigMaps

Do not put secrets in a `.env` file. Instead, give a JSON value and Rossoctl turns it into a
Kubernetes `valueFrom` reference in the generated manifest.

Full form:

```ini
OPENAI_API_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
```

Shorthand — a top-level `secretKeyRef` is wrapped in `valueFrom` for you:

```ini
OPENAI_API_KEY='{"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}'
```

ConfigMaps work the same way:

```ini
WEATHER_CONFIG='{"configMapKeyRef": {"name": "weather-config", "key": "settings"}}'
```

Keep the single quotes. Without them the `.env` parser splits the JSON.

Create the Secret first, in the namespace where the agent will run:

```bash
kubectl create secret generic openai-secret \
  --from-literal=apikey='<YOUR_API_KEY>' \
  -n team1
```

## Deployment types

| Type | Use it for |
| --- | --- |
| `deployment` | Stateless agents. The default. |
| `statefulset` | Agents with attached durable storage. |
| `sandbox` | Stronger isolation. Alpha — see the [caveats](../concepts/control-plane.md#deployment-types). |

## With custom resources

If you deploy with GitOps, write the Deployment yourself and enrol it:

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

The operator handles the rest. See [Custom resources](../reference/custom-resources.md).

## Configure Cortex for one agent

Inspect the inbound and outbound plugin pipelines, in execution order, with each plugin's error policy
and configuration:

```bash
rossoctl agents authbridge get orders
```

Replace them:

```bash
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml
```

The file is sent verbatim, so comments and key order survive and the server validates it. Add `--wait`
to poll until the change takes effect.

:::note
`--wait` compares against the configuration that was in effect before the write, so re-applying an
identical configuration cannot be confirmed — it times out and exits non-zero.
:::

## Test it

Open the agent, go to **Details**, and choose **Chat**.

## Delete it

```bash
rossoctl agents delete orders
```

This does not delete an attached [agent context](agent-context.md). Delete that separately.

## Related

- [Bring your own agent](bring-your-own-agent.md) — the contract your code must meet.
- [Deploy a tool](deploy-a-tool.md).
- [Troubleshooting](../operate/troubleshooting.md).
