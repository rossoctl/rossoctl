---
title: CLI Weather Agent Demo
description: CLI steps to use an LLM and tool to discuss the weather.
sidebar_label: Use the CLI to run the Weather Agent
sidebar_position: 30
---

This document provides detailed steps for running the **Weather Agent** proof-of-concept demo using the [_rossoctl_ CLI](../getting-started/install-cli.md) on Kubernetes.

In this demo, we will deploy both the **Weather Service Agent** and the **Weather Tool**.
We will use the **A2A protocol** to communicate with the agent using a natural language prompt.
The agent will use **MCP** to communicate with the weather tool.

This demo illustrates how Rossoctl manages the lifecycle of all required components: agents, tools, protocols, and runtime infrastructure.

> **Prerequisites:**
> Ensure you've completed the Rossoctl platform setup as described in the [Installation](../getting-started/install.md) section, and that you have installed the CLI.

Ensure you are logged in to the CLI.

If you are using **Kind Kubernetes**:

```bash
rossoctl login
```

If you are using a **different Rossoctl API server**:

```bash
# Use your server name, e.g. https://rossoctl-ui.apps.server3.res.ibm.com/api/v1
rossoctl --server <server> login
```

---

#### Import New Agent

To deploy the Weather Agent:

If you are using a **Local model (Ollama)**:

```bash
rossoctl agents import from-image \
  --name weather-service \
  --createHttpRoute \
  --containerImage ghcr.io/rossoctl/examples/weather_service:v0.2.0-rc.1 \
  --envVarsURL https://raw.githubusercontent.com/rossoctl/examples/refs/heads/main/a2a/weather_service/.env.ollama
```

If you are using an **OpenAI** account:

```bash
rossoctl agents import from-image \
  --name weather-service \
  --createHttpRoute \
  --containerImage ghcr.io/rossoctl/examples/weather_service:v0.2.0-rc.1 \
  --envVarsURL https://raw.githubusercontent.com/rossoctl/examples/refs/heads/main/a2a/weather_service/.env.openai
```

You will receive a response:

```
Agent 'weather-service' deployed as deployment successfully.
```

**Note:** The `.env.ollama` variable set specifies `llama3.2:3b-instruct-fp16` as the default model. To download the model, run `ollama pull llama3.2:3b-instruct-fp16`, and ensure an Ollama server is running in a separate terminal via `ollama serve`. The `.env.openai` set uses your OpenAI API key from the `openaiApiKey` value you configured in `deployments/envs/.secret_values.yaml` during [installation](../overview/5-quickstart.md); no local model is needed.

---

#### Import New Tool

To deploy the Weather Tool:

```bash
rossoctl tools import from-image --name weather-tool \
  --containerImage ghcr.io/rossoctl/examples/weather_tool:v0.2.0-rc.1
```

Use `rossoctl tools get weather-tool` to check the deployment status of the tool.

---

#### Chat with the Weather Agent

Before you can chat with the weather agent, you must log into Rossoctl again.  The second login acquires permission to talk to the agent you deployed:

```bash
rossoctl login
```

Next, send a natural language message to your agent:

```bash
rossoctl agents chat weather-service \
   --address http://weather-service.team1.localtest.me:8080 \
   --with-authorization \
   --message "What is the weather in New York?"
```

> **Note** that we override `--address` because this Agent's card advertises an internal-only endpoint.  This address will work with the above steps on Kind.  If you are using a different Kubernetes, consult your documentation or consult the `team1` namespace's HttpRoutes.

The response will include some status messages and an "A2A artifact" containing the natural language response:

```
artifact be712aa7-89db-4884-8564-bec3d86e65d4: f2080283-de36-4e08-8065-41e0da08cb78: 
The current weather in New York is mostly sunny with a temperature of 73.5°F (23°C). 
There is a gentle breeze blowing at 4.6 mph from the northeast, and it's currently daytime.
The weather code indicates fair weather with no precipitation.
```

If you encounter any errors, check the [Troubleshooting section](../users-guides/troubleshooting.md).

#### Cleanup

To delete the agent and tool from this demo:

```bash
rossoctl agents delete weather-service
rossoctl tools delete weather-tool
```
