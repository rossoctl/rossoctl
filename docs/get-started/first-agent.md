---
title: Deploy your first agent
description: Deploy the sample weather agent and chat with it.
sidebar_position: 5
---

This walks through deploying an agent from a container image and talking to it. It assumes you have
completed [Quickstart: Kubernetes](kubernetes.md) and [Configure a model](configure-a-model.md).

If you installed with `--with-examples`, the weather agent and tool are already deployed — skip to
[Chat with it](#chat-with-it).

## Deploy from an image

1. Open the console at `http://rossoctl-ui.localtest.me:8080` and go to **Agents**.
2. Choose **Import new agent**.
3. Select **Deploy from existing image** and give it an image URI. For the sample:

   ```
   ghcr.io/rossoctl/examples/weather-service:latest
   ```

4. Set the environment variables. Pick the **ollama** or **openai** preset, or import a `.env` file
   from GitHub. The sample agent also needs `MCP_URL` pointing at its tool:

   ```
   MCP_URL=http://weather-tool:8080/mcp
   ```

5. Tick **Enable external access to the agent endpoint** if you want to reach it from outside the
   cluster.
6. Choose **Deploy**.

Rossoctl creates a Deployment and a Service, adds an `AgentRuntime` resource to enrol the workload,
and — if you enabled external access — an `HTTPRoute`.

## Chat with it

1. Open the agent from the **Agents** list.
2. Go to the **Details** tab.
3. Choose **Chat**.
4. Ask it something the tool can answer, for example `What is the weather in Dublin?`

If the agent answers, you have an agent talking to a tool through the platform.

## What just happened

The operator noticed the `AgentRuntime` resource and did four things:

1. Labelled the workload `rossoctl.io/type: agent`.
2. Injected the Cortex sidecars — the Envoy proxy, the SPIFFE helper, and client registration.
3. Registered the workload as an OAuth client in Keycloak.
4. Created an `AgentCard` resource, fetched the agent's card from
   `/.well-known/agent-card.json`, and verified its signature.

From now on, every request into and out of that agent passes through Cortex. See
[RossoCortex](../concepts/cortex.md).

## Build from source instead

If your agent lives in a Git repository rather than a registry, Rossoctl can build it. You need
`--with-builds` at install time and 6 CPUs available.

The repository must be on GitHub, reachable with the token you gave the installer, and the agent
must sit in a **subdirectory** containing a `Dockerfile` — not at the repository root.

See [Deploy an agent](../workloads/deploy-an-agent.md) for build strategies, registries, and build
arguments.

## If it does not work

| What you see | Usually means |
| --- | --- |
| `Init:ErrImagePull` or `Init:ImagePullBackOff` | Your GitHub token expired. It needs `repo`, `write:packages`, and `read:packages`. |
| Chat returns a 503, agent log shows a connection reset | The model backend is unreachable. Check `ollama serve`. |
| Agent stays `Pending` | Not enough CPU on the node. See the [prerequisites](kubernetes.md#what-you-need). |
| Build pod stuck `Pending` on `Insufficient cpu` | Same. Deploy from an image instead, or give the runtime 6 CPUs. |

More in [Troubleshooting](../operate/troubleshooting.md).

## Next

- [Connect your first MCP tool](first-tool.md).
- [Bring your own agent](../workloads/bring-your-own-agent.md) — what your own code has to expose.
