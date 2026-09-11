---
title: Deploy your first agent
description: Deploy the sample weather agent and send a message to it.
sidebar_position: 6
---

This procedure deploys an agent from a container image, and then sends a message to the agent. Complete
[Quickstart on Kubernetes](kubernetes.md) and [Configure a model](configure-a-model.md) first.

If you installed with the `--with-examples` option, the weather agent and tool are present. Go to
[Step 2](#step-2-send-a-message-to-the-agent).

## Step 1: deploy the agent

1. Open the console at `http://rossoctl-ui.localtest.me:8080` and select **Agents**.
2. Select **Import new agent**.
3. Select **Deploy from existing image**. Enter this image address:

   ```
   ghcr.io/rossoctl/examples/weather-service:latest
   ```

4. Set the environment variables. Select the **ollama** preset or the **openai** preset, or import a
   `.env` file from GitHub. The sample agent also needs the address of its tool:

   ```
   MCP_URL=http://weather-tool:8080/mcp
   ```

5. To reach the agent from outside the cluster, select **Enable external access to the agent
   endpoint**.
6. Select **Deploy**.

Rossoctl creates a Deployment and a Service. It adds an `AgentRuntime` resource, which puts the
workload in the platform. If you enabled external access, it also creates an `HTTPRoute`.

## Step 2: send a message to the agent

1. Select the agent in the **Agents** list.
2. Select the **Details** tab.
3. Select **Chat**.
4. Ask a question that needs the tool. For example: `What is the weather in Dublin?`

If the agent answers, the agent and the tool communicate through the platform.

## What Rossoctl did

The operator found the `AgentRuntime` resource and did four things:

1. It added the label `rossoctl.io/type: agent` to the workload.
2. It injected the RossoCortex sidecars, which are the proxy, the identity helper and the client
   registration.
3. It registered the workload as an OAuth client in Keycloak.
4. It created an `AgentCard` resource, read the card of the agent from
   `/.well-known/agent-card.json`, and validated the signature of the card.

Each request to the agent, and each request from the agent, now passes through RossoCortex. See
[RossoCortex](../concepts/core/cortex.md).

## To build the agent from source instead

If your agent is in a Git repository and not in a registry, Rossoctl can build it. You need the
`--with-builds` option at installation time, and 6 available CPUs.

The repository must be on GitHub and must be reachable with the token that you gave to the installer.
The agent must be in a **subdirectory** that contains a `Dockerfile`. The agent must not be in the root
directory of the repository.

For the build options, the build strategies and the registries, see
[Deploy an agent](../workloads/deploy-an-agent.md).

## If the procedure fails

| What you see | The usual cause |
| --- | --- |
| `Init:ErrImagePull` or `Init:ImagePullBackOff` | Your GitHub token is expired. It needs the `repo`, `write:packages` and `read:packages` permissions. |
| The chat returns the status 503, and the log of the agent shows a reset connection | The model is not reachable. Confirm that `ollama serve` is active. |
| The agent stays in the `Pending` state | The node has insufficient CPU. See [Before you start](kubernetes.md#before-you-start). |
| The build pod stays in `Pending` with `Insufficient cpu` | The same cause. Deploy from an image, or give the runtime 6 CPUs. |

For more information, see [Troubleshooting](../operate/troubleshooting.md).

## Next

- [Connect your first tool](first-tool.md).
- [Bring your own agent](../workloads/bring-your-own-agent.md) gives the requirements for your own code.
