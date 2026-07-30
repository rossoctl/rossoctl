---
description: Use an LLM and tool to discuss the weather.
sidebar_label: Run the Weather Agent
---

### Weather Agent Demo

This document provides detailed steps for running the **Weather Agent** proof-of-concept (PoC) demo.

In this demo, we will use the Rossoctl UI to import and deploy both the **Weather Service Agent** and the **Weather Tool**.
During deployment, we'll configure the **A2A protocol** for managing agent calls and **MCP** for enabling communication between the agent and the weather tool.

Once deployed, we will query the agent using a natural language prompt. The agent will then invoke the tool and return the weather data as a response.

This demo illustrates how Rossoctl manages the lifecycle of all required components: agents, tools, protocols, and runtime infrastructure.

Here's a breakdown of the sections:
- In [**Import New Agent**](#import-new-agent), you'll build and deploy the [`weather_service`](https://github.com/rossoctl/examples/tree/main/a2a/weather_service) agent.
- In [**Import New Tool**](#import-new-tool), you'll build and deploy the [`weather_tool`](https://github.com/rossoctl/examples/tree/main/mcp/weather_tool) tool.
- In [**Chat with the Weather Agent**](#chat-with-the-weather-agent), you'll interact with the agent and confirm it responds correctly with current weather information.

> **Prerequisites:**
> Ensure you've completed the Rossoctl platform setup as described in the [Installation](../getting-started/install.md) section.

---

#### Import New Agent

To deploy the Image Agent:

1. Navigate to [Import New Agent](http://rossoctl-ui.localtest.me:8080/Import_New_Agent#import-new-agent) in the Rossoctl UI.
2. Under **Select Agent**, choose `Weather Service Agent`
3. Expand **Environment Variables**
  - Choose `Import from File/URL
  - Edit the URL to read `https://raw.githubusercontent.com/rossoctl/examples/refs/heads/main/a2a/weather_service/.env.ollama`
    - If using OpenAI LLMs, skip this step
  - Click `Fetch and Parse`
  - Click `Import`
4. Click **Build & Deploy Agent** to deploy.

**Note:** The `ollama` environmental variable set specifies `gpt-oss:latest` as the default model. To download the model, run `ollama pull gpt-oss:latest`. Please ensure an Ollama server is running in a separate terminal via `ollama serve`.

---

#### Import New Tool

To deploy the Image Tool using Shipwright:

1. Navigate to [Import New Tool](http://rossoctl-ui.localtest.me:8080/Import_New_Tool#import-new-tool) in the UI.
2. Under **Select Tool*, choose `Weather Tool`
3. Click **Build & Deploy Tool** to deploy.

You will be redirected to a **Build Progress** page where you can monitor the Shipwright build. Once the build succeeds, the Deployment and Service for the tool will be created automatically.

---

#### Chat with the Weather Agent

Once the deployment is complete, you can run the demo:

1. Select the **Chat** tab.
2. Scroll to the bottom of the page. In the input field labeled *Type your message...*, enter:

   ```console
   What is the weather in New York?
   ```


If you encounter any errors, check the [Troubleshooting section](../users-guides/troubleshooting.md).

#### Cleanup

- Select `Delete Agent`, and delete the weather agent.
- Select `Delete Tool`, and delete the weather tool.
