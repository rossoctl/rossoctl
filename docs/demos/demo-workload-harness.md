---
description: Stress-test Rossoctl and evaluate traffic load.
sidebar_label: Run a Workload Harness
---

# Rossoctl Workload Harness

Workload harnesses drive test and evaluation traffic to Rossoctl agents. The current implementation is the **Exgentic A2A Runner** — a standalone Python runner that integrates Exgentic benchmarks with Rossoctl agents using the A2A (Agent-to-Agent) protocol.

The harness exists to robustly exercise agents and validate that the Rossoctl platform is reliable, scalable, and observable.

## Features

- **Exgentic MCP Integration**: Communicates with Exgentic MCP server for benchmark tasks
- **Parallel session processing**: Configurable concurrency for efficient benchmark execution and stress testing
- **A2A protocol support**: Communicates with remote agents using the A2A protocol via JSON-RPC over HTTP
- **OpenTelemetry instrumentation**: Comprehensive traces, metrics, and logs
- **Strict failure handling**: Any error or timeout marks the session as failed
- **Configurable via environment variables**: Easy deployment and configuration
- **Composable AuthBridge plugin pipeline**: Per-agent selection of inbound/outbound plugins (`jwt-validation`, `token-exchange`, `a2a-parser`, `ibac`, …) with `enforce` / `observe` / `off` policies — see [AuthBridge Plugin Pipeline](#authbridge-plugin-pipeline).

## Getting Started

The minimal end-to-end path: stand up a Rossoctl cluster, build the agent + MCP images, then deploy and evaluate. Each block here is self-contained — copy the commands you need.

Follow the [quickstart](../overview/5-quickstart.md) or [install](../getting-started/install.md) instructions to install.


```bash
# 1. Stand up the Rossoctl cluster (see above; one-time)

# 2. Install the runner
git clone git@github.com:rossoctl/workload-harness.git
cd workload-harness/exgentic_a2a_runner
uv sync --python 3.12
source .venv/bin/activate
cp example.env .env   # edit as needed (OPENAI_API_KEY, IBAC tunables, etc.)

# 3a. Plain run — no AuthBridge sidecar
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling

# 3b. Run with auth + token exchange only
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset auth-only

# 3c. Run with IBAC enforcing intent-based access control
export IBAC_JUDGE_ENDPOINT=http://host.docker.internal:11434
export IBAC_JUDGE_MODEL=llama3.2:3b
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset ibac-only

# 3d. Canary IBAC in observe mode (telemetry only, no blocking)
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset ibac-only --plugin ibac:observe
```

The deploy + evaluate steps can also be run separately — see [Usage](#usage). For full plugin pipeline mechanics, see [AuthBridge Plugin Pipeline](#authbridge-plugin-pipeline).

## Architecture

The runner follows this execution model for each benchmark session:

1. **Create Session**: `(session_id, task) = mcp_server.create_session()`
2. **Invoke Agent**: `agent.invoke_agent("{task}")` . Pass session_id as meta_data.
3. **Evaluate Session**: `success = mcp_server.evaluate_session(session_id)`
4. **Close Session**: `mcp_server.close_session(session_id)`
5. **Record Statistics**: Track completion time, success rate, compute costs, tokens.

## Benchmarks

The runner currently drives three benchmarks via the Exgentic MCP server. Each is a separate MCP image (`./build.sh <name>` from `agent-examples/mcp/exgentic_benchmarks`) and is selected at deploy time with `--benchmark <name>`.

| Benchmark | What it tests | Tool surface | Notes |
|-----------|---------------|--------------|-------|
| `gsm8k` | Grade-school math word problems — single-turn arithmetic reasoning. | Minimal — primarily LLM reasoning, light tool use. | Cheap and fast; good smoke test. The deploy script sets `EXGENTIC_SET_BENCHMARK_RUNNER=direct` for this benchmark. |
| `tau2` | Multi-turn customer-support conversations against a simulated user. Measures whether the agent can complete realistic task flows over several turns. | Domain tools (retail, airline, telecom) plus a user-simulator LLM. | Deploy passes `EXGENTIC_SET_BENCHMARK_USER_SIMULATOR_MODEL` so the simulator runs on the same model as the agent. The IBAC plugin also lands its canonical attack-shape tests against tau-style multi-turn traffic. |
| `appworld` | Long-horizon, tool-heavy tasks across a simulated app ecosystem (calendar, email, contacts, etc.). Stresses tool selection and planning. | Very wide — hundreds of tools across the simulated apps. | OpenAI models can't handle this tool surface without shortlisting; use `gemini-2.5-pro` or another model with strong tool selection. |

### Picking a model

The model name passed via `--model` (or `LLM_MODEL` / `EXGENTIC_SET_AGENT_MODEL`) is consumed by [LiteLLM](https://docs.litellm.ai/) on the agent side, so it follows LiteLLM's `<provider>/<model>` routing convention. The default is `Azure/gpt-4.1`.

**OpenAI-compatible backends** (vLLM, Ollama, llama.cpp, LM Studio, custom proxies, etc.) — prefix the model name with `openai/` to force LiteLLM down its OpenAI-compatible route, and point `OPENAI_API_BASE` at your endpoint:

```bash
# Custom Azure deployment fronted by an OpenAI-compatible proxy
./deploy-agent.sh --benchmark tau2 --agent tool_calling \
    --model openai/Azure/gpt-4o-mini

# Local model served via vLLM/Ollama
./deploy-agent.sh --benchmark gsm8k --agent tool_calling \
    --model openai/llama3.1-70b-instruct
```

For `appworld`, use a model with strong tool-selection — e.g. `gemini-2.5-pro` — rather than an OpenAI-route model.

## Installation

> **⏱️ Estimated Setup Time:** ~15 minutes (excluding container image pulls)

### Prerequisites

- Python 3.11 or 3.12 (Python 3.13+ is **not supported** due to dependency compatibility)
  - **Note:** The `uv` package manager will automatically use Python 3.12 when you run `uv sync --python 3.12`, regardless of your system Python version
- [uv](https://docs.astral.sh/uv/) package manager
- kubectl v0.6.0 (tested on v0.6.0-rc.2) 
- Rossoctl cluster running with:
  - Rossoctl backend in `rossoctl-system` namespace
  - Keycloak in `keycloak` namespace
  - `team1` namespace for deployments

> **AuthBridge sidecar:** the deploy scripts can attach an AuthBridge
> sidecar with a composable plugin pipeline (auth, token exchange,
> intent-based access control, …) to each agent. See
> [AuthBridge Plugin Pipeline](#authbridge-plugin-pipeline) for the
> full surface; the sidecar is only injected when you pass a plugin
> selector.

### Install from source

#### Deploy a rossoctl cluster

```bash
git clone git@github.com:rossoctl/rossoctl.git
cd rossoctl

env CONTAINER_ENGINE=podman  scripts/kind/setup-rossoctl.sh --with-all --preload-images

```


#### Deploy agent and MCP server per benchmark

```bash
git clone git@github.com:yoavkatz/workload-harness.git
cd workload-harness
git checkout feature/exgentic-a2a-runner
cd exgentic_a2a_runner
uv sync --python 3.12
source .venv/bin/activate

# Deploy and configure MCP server using Rossoctl Tool API
# This script now combines deployment and configuration in one step
./deploy-benchmark.sh --benchmark tau2

# Deploy and configure agent using Rossoctl Agent API
# This script now combines deployment and configuration in one step
./deploy-agent.sh --benchmark tau2 --agent tool_calling
```

**Note:** All deployment scripts now use named parameters:

**Benchmark Deployment:**
```bash
# Basic deployment with defaults (model: Azure/gpt-4.1, keycloak: admin/admin)
./deploy-benchmark.sh --benchmark tau2

# Deploy with custom model
./deploy-benchmark.sh --benchmark tau2 --model Azure/gpt-4o-mini

# Deploy with custom Keycloak credentials
./deploy-benchmark.sh --benchmark tau2 --model Azure/gpt-4o-mini --keycloak-user admin --keycloak-pass admin

# Show help
./deploy-benchmark.sh --help
```

**Agent Deployment:**
```bash
# Basic deployment with defaults (model: Azure/gpt-4.1, keycloak: admin/admin)
./deploy-agent.sh --benchmark tau2 --agent tool_calling

# Deploy with custom model
./deploy-agent.sh --benchmark tau2 --agent tool_calling --model Azure/gpt-4o-mini

# Deploy with custom Keycloak credentials
./deploy-agent.sh --benchmark tau2 --agent tool_calling --model Azure/gpt-4o-mini --keycloak-user admin --keycloak-pass admin

# Show help
./deploy-agent.sh --help
```

**Agent Naming:** Underscores in agent names are automatically converted to hyphens for Kubernetes compatibility (e.g., `tool_calling` becomes `tool-calling`).

**Important:** Both deployment scripts now combine deployment and configuration steps:

**`deploy-benchmark.sh`** will:
1. Deploy the MCP server to the Rossoctl cluster
2. Automatically configure secrets before deployment:
   - Updates `openai-secret` with OPENAI_API_KEY (if set in environment)
   - Creates/updates `hf-secret` with HF_TOKEN (uses dummy token if not set)
3. Configure environment variables (OPENAI_API_BASE, EXGENTIC_SET_BENCHMARK_RUNNER for gsm8k)
4. Set memory limits and model settings
5. Wait for the deployment to be ready

**`deploy-agent.sh`** will:
1. Deploy the agent to the Rossoctl cluster
2. Automatically configure environment variables (OPENAI_API_BASE, OPENAI_API_KEY, LLM_MODEL)
3. Set model settings (LLM_MODEL, EXGENTIC_SET_AGENT_MODEL)
4. Wait for the deployment to be ready

**Environment Variables for Deployment:**
- `OPENAI_API_KEY`: OpenAI API key (optional, updates openai-secret if set)
- `HF_TOKEN`: HuggingFace token (optional, creates hf-secret with dummy token if not set)
- `OPENAI_API_BASE`: OpenAI API base URL (optional, added to deployment env vars)

For benchmark fit and model-name conventions (including the `openai/` prefix for OpenAI-compatible backends), see [Benchmarks](#benchmarks).

## MCP Gateway Support

The runner can optionally route MCP traffic through an [MCP Gateway](https://github.com/kuadrant/mcp-gateway) instead of connecting directly to the benchmark MCP server. When enabled, the gateway acts as a single entry point that multiplexes access to registered MCP servers and namespaces their tools with a configurable prefix.

### How It Works

1. **Benchmark deployment** (`deploy-benchmark.sh --use-mcp-gateway`) creates an `HTTPRoute` and an `MCPServerRegistration` CR that registers the MCP server with the gateway.
2. **Agent deployment** (`deploy-agent.sh --use-mcp-gateway`) points the agent's `MCP_URL` at the gateway service (`mcp-gateway-istio.gateway-system.svc.cluster.local:8080`) instead of the benchmark's MCP service directly.
3. **Evaluation** (`evaluate-benchmark.sh`) port-forwards the gateway service and sets `EXGENTIC_MCP_TOOL_PREFIX` so the runner prepends the gateway-assigned prefix to every tool call (e.g. `list_tasks` becomes `exgentic_list_tasks`).

### Deploying with the MCP Gateway

Pass `--use-mcp-gateway` to any deployment or evaluation script:

```bash
# Individual scripts
./deploy-benchmark.sh --benchmark tau2 --use-mcp-gateway
./deploy-agent.sh --benchmark tau2 --agent tool_calling --use-mcp-gateway

# All-in-one
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --use-mcp-gateway
```

You can also set the flag in your `.env` file so it applies by default:

```bash
USE_MCP_GATEWAY=true
```

### Tool Prefix

The MCP Gateway exposes tools under a namespace prefix (default `exgentic_<benchmark_name>`). The runner reads `EXGENTIC_MCP_TOOL_PREFIX` and prepends it to every MCP tool call. When using the gateway via `evaluate-benchmark.sh`, this variable is set automatically. 

## AuthBridge Plugin Pipeline

The deploy scripts can attach an **AuthBridge sidecar** to each
deployed agent. AuthBridge is a forward proxy whose behavior is
defined by a composable pipeline of named plugins — `jwt-validation`,
`token-exchange`, `token-broker`, `a2a-parser`, `mcp-parser`,
`inference-parser`, `ibac` — each independently togglable and each
running under an `on_error` policy of `enforce`, `observe`, or `off`.

### Architectural implications

- **The sidecar is opt-in per deploy.** With no plugin selectors, the
  operator does not inject a sidecar at all and the agent runs as
  before. Pass any selector (`--plugin-preset`, `--plugin`,
  `--no-plugin`, `--plugin-config-file`) and the sidecar is injected
  with the resolved pipeline.
- **The pipeline mediates every request the agent sends and receives.**
  Inbound plugins run on traffic to the agent (auth validation, A2A
  parsing); outbound plugins run on traffic the agent makes to tools
  and LLMs (token exchange, MCP/inference parsing, IBAC judging).
  Adding a plugin adds a hop on that path — measure latency
  accordingly.
- **Plugins share a `Session` object.** Inbound plugins populate fields
  (e.g. `a2a-parser` extracts the user's intent into `Session.Intents`)
  that outbound plugins read (e.g. `ibac` compares each outbound action
  against that intent). Hard runtime dependencies are encoded in the
  framework — IBAC fails closed if `a2a-parser` didn't run.
- **The operator's base config enables every plugin by default.** To
  disable a plugin, the deploy overlay must explicitly emit
  `on_error: off` for it. The script handles this — any plugin not in
  your resolved selection is turned off in the overlay, not omitted.
- **Selector resolution is last-write-wins.** A preset seeds the set;
  subsequent `--plugin` / `--no-plugin` flags apply in order. This
  makes "preset minus one plugin" or "preset, but canary IBAC" easy
  to express on the command line.
- **Configuration is delivered via overlay, hot-reloaded.** No operator
  changes are required to flip the pipeline shape — the script writes
  a merged ConfigMap and AuthBridge picks it up.

### Flags

These flags are accepted by `deploy-agent.sh` and forwarded by
`deploy-and-evaluate.sh`:

| Flag | Description |
|------|-------------|
| `--plugin-preset NAME` | Named bundle. Available: `auth-only`, `ibac-only`, `full`. |
| `--plugin NAME[:POLICY]` | Enable plugin with policy ∈ {`enforce`(default), `observe`, `off`}. Repeatable. |
| `--no-plugin NAME` | Shorthand for `--plugin NAME:off`. Repeatable. |
| `--plugin-config-file PATH` | Flat-map YAML overlay merged after selectors. |

### Presets

| Preset | Inbound | Outbound |
|--------|---------|----------|
| `auth-only` | `jwt-validation` | `token-exchange` |
| `ibac-only` | `a2a-parser` | `inference-parser`, `mcp-parser`, `ibac` |
| `full` | `a2a-parser`, `jwt-validation` | `token-exchange`, `inference-parser`, `mcp-parser`, `ibac` |

### Running with IBAC

IBAC (Intent-Based Access Control) is an outbound plugin that compares
each agent action against the user's most-recent declared intent and
asks an LLM judge to deny requests that don't align — catching
prompt-injection-driven exfiltration that traditional auth gates miss.

**Prerequisites:**

- An OpenAI-compatible chat-completion endpoint for the judge (ollama,
  OpenAI, vLLM, Azure, etc.).
- The cluster's AuthBridge sidecar image must include the `ibac`
  plugin. IBAC landed in `rossoctl-extensions` on 2026-05-17 (PR #421);
  use sidecar image **`v0.6.0-alpha.7`** or newer.

  > **Caveat — not in the latest stable Rossoctl release.** As of this
  > writing, the IBAC plugin and the additive plugin-pipeline merge
  > behavior the deploy scripts depend on are only available in
  > `v0.6.0-alpha.7`, which has not yet been published in a stable
  > Rossoctl release. Installing from the official `v0.6.0` chart
  > release pulls an older alpha that will fail with errors like
  > `jwt-validation config: issuer is required` during pipeline
  > apply. Until a release containing alpha.7 is cut, install Rossoctl
  > from `main`:
  >
  > ```bash
  > git clone git@github.com:rossoctl/rossoctl.git
  > cd rossoctl  # use main, not a release tag
  > env CONTAINER_ENGINE=podman scripts/kind/setup-rossoctl.sh --with-all --preload-images
  > ```
  >
  > To verify the sidecar image actually deployed:
  >
  > ```bash
  > kubectl -n rossoctl-system get cm rossoctl-platform-config \
  >   -o jsonpath='{.data.authbridge}'
  > ```
  >
  > Expect `ghcr.io/rossoctl/rossoctl-extensions/authbridge:v0.6.0-alpha.7`
  > or newer.

**Configure the judge** in your `.env` (consumed by the IBAC plugin
fragment via envsubst when `ibac` is in the active set):

```bash
# Judge LLM base URL — OpenAI-compatible (POST /v1/chat/completions)
IBAC_JUDGE_ENDPOINT=http://host.docker.internal:11434
# Judge model id served by that endpoint
IBAC_JUDGE_MODEL=llama3.2:3b
# Per-judge-call timeout in milliseconds
IBAC_TIMEOUT_MS=15000
# Hostname of the agent's own LLM endpoint (auto-derived from
# OPENAI_API_BASE if unset). Added to the IBAC bypass list so the
# agent's own reasoning calls aren't recursively judged.
# IBAC_AGENT_LLM_HOST=host.docker.internal
```

**Deploy with IBAC enforcing** -- *UNTESTED* --(full pipeline — auth + parsers + IBAC):

```bash
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset full
```


**IBAC without inbound auth** — for environments where an upstream
gateway already terminates auth but you still want intent-based
blocking on outbound calls:

```bash
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset ibac-only
```

When IBAC blocks a request, the agent sees a `403 ibac.blocked` from
the proxy and the `ibac.evaluate` span on that outbound call carries
`verdict=deny`, `reason=blocked`, and the (truncated) intent and
action description.

### Other compositions

```bash
# Auth + token exchange only (no IBAC, no parsers).
./deploy-agent.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset auth-only

# Token-broker instead of token-exchange.
./deploy-agent.sh --benchmark tau2 --agent tool_calling \
    --plugin-preset full \
    --no-plugin token-exchange \
    --plugin token-broker

# Custom set without a preset.
./deploy-agent.sh --benchmark tau2 --agent tool_calling \
    --plugin jwt-validation --plugin token-exchange --plugin ibac

# No AuthBridge sidecar at all (omit all plugin flags).
./deploy-agent.sh --benchmark tau2 --agent tool_calling
```

### `--plugin-config-file` format

A flat YAML map keyed by plugin name; values are deep-merged into each
plugin's `config:` block on top of the fragment defaults:

```yaml
ibac:
  judge_model: "llama3.2:8b"
  timeout_ms: 30000
token-exchange:
  default_policy: exchange
jwt-validation:
  bypass_paths:
    - /healthz
    - /metrics
```

Unknown plugin names in the file are ignored with a WARN to stderr.

### Sidecar image compatibility

Every plugin you select must be compiled into the running sidecar
binary. The merge validates the YAML shape, but the sidecar will fail
at Configure with `unknown plugin "<name>"` after reload if a plugin
isn't registered:

```text
reloader: reload failed  error="build: outbound: unknown plugin \"<name>\""
```

The image tag is pinned in `rossoctl/charts/rossoctl/values.yaml`. To
verify what's running:

```bash
kubectl -n team1 get pod -l app.kubernetes.io/name=<agent-name> \
  -o jsonpath='{range .items[0].spec.containers[?(@.name=="authbridge")]}{.image}{"\n"}{end}'
```

> **Compatibility note.** Newer chart versions tie sidecar image
> versions to operator versions (per-plugin config support,
> jwt-validation field shape). When bumping the sidecar image past
> `v0.5.0-rc.3`, confirm your rossoctl-operator is recent enough —
> older operators may emit ConfigMaps the newer sidecar can't parse.

### Troubleshooting

- **`unknown plugin "<name>"`** at reload: the sidecar binary doesn't
  have that plugin compiled in. Bump the image tag.
- **Mutex error: `token-exchange` and `token-broker`**: both claim
  `ClaimAuthorizationHeader`; the script rejects this before any
  kubectl call. Disable one with `--no-plugin`.
- **`Reads ... no earlier plugin writes it`**: parser ordering issue;
  shouldn't happen with the canonical-position table, but possible if a
  malformed `--plugin-config-file` introduces an unknown plugin. See
  [`framework-architecture.md` §6](https://github.com/rossoctl/rossoctl-extensions/blob/main/authbridge/docs/framework-architecture.md)
  for the underlying rules.
- **`ibac.no_intent`** in IBAC telemetry: the inbound chain is
  misconfigured — `a2a-parser` didn't run, so `Session.Intents` is
  empty and IBAC fails closed. Confirm `a2a-parser` is in the active
  inbound set (it is for the `ibac-only` and `full` presets).
- **Unknown plugin / preset name**: script-side error; valid names are
  listed in the spec §3.1, valid presets in §3.2.

## Configuration

### Before Running Evaluations

**Required:** Create and configure your environment file:

```bash
cp example.env .env
```

Then edit the .env file as needed.

### Main Configuration

| Environment Variable | Default | Description |
| --- | --- | --- |
| `MAX_TASKS` | `(none)` | Maximum number of sessions to process. Useful for testing with a subset. |
| `MAX_PARALLEL_SESSIONS` | `1` | Number of sessions to run concurrently. Set higher for parallel execution. |
| `ABORT_ON_FAILURE` | `false` | Stop processing after the first failed session. |

### Debug Configuration

| Environment Variable | Default | Description |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Log level for the runner. Set to `DEBUG` for verbose logging with detailed debug information. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_PROMPT` | `0` | Log prompt payloads for debugging (1 to enable). |
| `LOG_RESPONSE` | `0` | Log response payloads for debugging (1 to enable). |

### Tracing Configuration (OpenTelemetry)

| Environment Variable | Default | Description |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `(none)` | OTLP collector endpoint (for this runner, use gRPC such as `http://localhost:4317`). If not set, no traces are exported. |
| `OTEL_SERVICE_NAME` | `exgentic-a2a-runner` | Service name in traces. |
| `OTEL_RESOURCE_ATTRIBUTES` | `(none)` | Additional resource attributes (format: `key1=val1,key2=val2`). |
| `OTEL_INSTRUMENT_REQUESTS` | `true` | Auto-instrument HTTP requests. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | OTLP protocol. The current exporter implementation. |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true` | Use insecure OTLP connection. |

### MCP Gateway Configuration

| Environment Variable | Default | Description |
| --- | --- | --- |
| `USE_MCP_GATEWAY` | `false` | Route MCP traffic through the MCP Gateway instead of connecting directly to the MCP server. |
| `EXGENTIC_MCP_TOOL_PREFIX` | `(empty)` | Prefix prepended to MCP tool names. Set to match the gateway's `MCPServerRegistration.spec.toolPrefix` (e.g. `exgentic_`). |

### Advanced Configuration

| Environment Variable | Default | Description |
| --- | --- | --- |
| `EXGENTIC_MCP_TIMEOUT_SECONDS` | `60` | Timeout for MCP operations. |
| `A2A_TIMEOUT_SECONDS` | `300` | Timeout for A2A requests. |
| `A2A_AUTH_TOKEN` | `(none)` | Bearer token for A2A authentication. |
| `A2A_VERIFY_TLS` | `true` | Verify TLS certificates for HTTPS. |
| `A2A_ENDPOINT_PATH` | `/` | Endpoint path for A2A requests. |

## Usage

### All-in-One: Deploy and Evaluate

The `deploy-and-evaluate.sh` script provides a convenient way to deploy both the benchmark and agent, then run the evaluation in a single command:

```bash
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling
```

This script will:
1. Deploy the benchmark MCP server
2. Deploy the agent
3. Run the evaluation

MLflow tracing via the OTEL Collector is **enabled by default**. Pass `--disable-mlflow` to skip it.

**Options:**
```bash
# Basic usage with defaults (MLflow tracing enabled)
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling

# Route MCP traffic through the MCP Gateway
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --use-mcp-gateway

# With custom model
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --model Azure/gpt-4o-mini

# With custom Keycloak credentials
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --model Azure/gpt-4o-mini --keycloak-user admin --keycloak-pass admin

# Dry run mode - print commands without executing them 
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --dry

# Show help
./deploy-and-evaluate.sh --help
```

#### Dry Run Mode

The `--dry` flag enables dry-run mode, which prints all commands that would be executed without actually running them. This is useful for:
- Verifying command syntax before execution
- Debugging deployment issues
- Understanding what the script will do
- Documentation and training purposes

```bash
# See what commands would be executed
./deploy-and-evaluate.sh --benchmark tau2 --agent tool_calling --dry

# Dry run with all options
./deploy-and-evaluate.sh --benchmark gsm8k --agent tool_calling \
  --model Azure/gpt-4o-mini --mlflow --use-mcp-gateway --dry
```

**Example output:**
```text
========================================
Deploy and Evaluate Exgentic Benchmark
========================================
Benchmark: tau2
Agent: tool_calling
Model: Azure/gpt-4.1
Keycloak User: admin
MLflow tracing: false
MCP Gateway: false
Dry run: true

========================================
Step 1/3: Deploying Benchmark
========================================
[DRY RUN] Would execute:
./deploy-benchmark.sh --benchmark "tau2" --model "Azure/gpt-4.1" --keycloak-user "admin" --keycloak-pass "admin"

========================================
Step 2/3: Deploying Agent
========================================
[DRY RUN] Would execute:
./deploy-agent.sh --benchmark "tau2" --agent "tool_calling" --model "Azure/gpt-4.1" --keycloak-user "admin" --keycloak-pass "admin"

========================================
Step 3/3: Running Evaluation
========================================
[DRY RUN] Would execute:
./evaluate-benchmark.sh --benchmark "tau2" --agent "tool_calling" --experiment "default"

========================================
✓ Dry run completed - no commands executed
========================================
```

### Running Benchmarks

The `evaluate-benchmark.sh` script automatically:
- Uses HTTP routes to reach services (no port-forwarding for MCP/agent)
- Port-forwards the OTEL Collector (traces → MLflow) on dev laptops — skipped in-cluster
- Waits for services to be ready via HTTP health checks
- Tests connectivity to services
- Runs the benchmark evaluation
- Propagates the current OpenTelemetry trace context into outbound A2A HTTP requests so the agent can continue the same distributed trace when it supports W3C trace headers
- Cleans up port forwards on exit

```bash
./evaluate-benchmark.sh --benchmark tau2 --agent tool_calling
./evaluate-benchmark.sh --benchmark gsm8k --agent tool_calling 
```

## Output

### Console Summary

At the end of each run, a summary is printed:

```text
============================================================
RUN SUMMARY
============================================================
Sessions Attempted:   100
Sessions Succeeded:   95
Sessions Failed:      5
Evaluation Success:   92.6%
Total Wall Time:      1234.56s
Average Latency:      12345.67ms
P50 Latency:          10000.00ms
P95 Latency:          20000.00ms
============================================================
```

### OpenTelemetry Data

The runner emits comprehensive telemetry:

#### Traces

Each session creates a span (`exgentic_a2a.session`) with:

**Attributes:**
- `exgentic.session_id`: Session identifier
- `exgentic.mcp_server_url`: MCP server URL
- `exgentic.evaluation_result`: Whether evaluation was successful
- `a2a.base_url`: A2A endpoint URL
- `a2a.timeout_seconds`: Timeout value
- `prompt.chars`: Prompt size in characters
- `response.chars`: Response size in characters
- `session.status`: `success` or `failed`
- `a2a.duration_ms`: End-to-end A2A operation latency in milliseconds

**Child spans:**
- `exgentic_a2a.prompt.build`: Prompt construction
- `exgentic_a2a.a2a.send_prompt`: End-to-end A2A `send_prompt` call
- `exgentic_a2a.mcp.evaluate_session`: Session evaluation
- `exgentic_a2a.mcp.close_session`: Session cleanup

**Auto-instrumented HTTP spans:**
- Outbound `requests` spans for agent-card discovery, `message/send`, and `tasks/get` calls

**Events:**
- `prompt_built`: When prompt is constructed
- `session_failed`: When session fails (includes error details)

#### Metrics

**Counters:**
- `exgentic_a2a_sessions_total{status=success|failed}`: Total sessions processed
- `exgentic_a2a_errors_total{error_type=...}`: Total errors by type

**Histograms:**
- `exgentic_a2a_session_latency_ms`: End-to-end session latency
- `exgentic_a2a_evaluation_latency_ms`: Evaluation operation latency
- `exgentic_a2a_session_creation_latency_ms`: Session creation latency
- `exgentic_a2a_a2a_latency_ms`: A2A request latency
- `exgentic_a2a_prompt_size_chars`: Prompt size distribution
- `exgentic_a2a_response_size_chars`: Response size distribution

**Gauge:**
- `exgentic_a2a_inflight_sessions`: Current sessions in flight (0 or 1)

## Execution Flow

```text
┌─────────────────────────────────────────────────────────┐
│                  For Each Session                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Create Session                                      │
│     └─> MCP: create_session() → (session_id, task)    │
│                                                         │
│  2. Build Prompt                                        │
│     └─> Include session_id in instructions             │
│                                                         │
│  3. Invoke Agent                                        │
│     └─> A2A: send_prompt(prompt) → response           │
│                                                         │
│  4. Evaluate Session                                    │
│     └─> MCP: evaluate_session(session_id) → success   │
│                                                         │
│  5. Close Session                                       │
│     └─> MCP: close_session(session_id)                │
│                                                         │
│  6. Record Statistics                                   │
│     └─> Track time, success, evaluation result         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## OpenTelemetry and Observability

### Using MLflow in the kind Cluster

The Rossoctl cluster exposes an MLflow service in the `rossoctl-system` namespace. An OTEL Collector forwards traces to MLflow's `/v1/traces` endpoint with OAuth2 authentication.

#### 1. Send runner telemetry to MLflow

MLflow tracing is **enabled by default**. The script automatically port-forwards the OTEL Collector on a developer laptop and configures the required environment variables. To disable it, pass `--disable-mlflow`:

```bash
# Default — MLflow tracing enabled
env MAX_TASKS=1 MAX_PARALLEL_SESSIONS=1 ./evaluate-benchmark.sh --benchmark gsm8k --agent tool_calling

# Disable MLflow tracing
env MAX_TASKS=1 MAX_PARALLEL_SESSIONS=1 ./evaluate-benchmark.sh --benchmark gsm8k --agent tool_calling --disable-mlflow
```

#### 2. Open the MLflow UI

Open http://mlflow.localtest.me:8080 in your browser to view traces and experiments.

### Analyzing Traces with analyze-run.sh

The `analyze-run.sh` script provides comprehensive trace analysis by downloading Agent.Session traces from MLflow and generating detailed performance reports.

#### Features

- **Automatic MLflow connectivity**: Connects to MLflow REST API with OAuth2 authentication and optional auto port-forwarding
- **Trace filtering**: Downloads Agent.Session root spans and all child spans
- **Experiment filtering**: Filter or compare traces by experiment name
- **Performance metrics**: Calculates timing statistics (avg, p50, p95, min, max) for:
  - Session creation time
  - Agent call time (end-to-end agent execution)
  - Evaluation time
  - LLM call time and token usage
  - Tool call time
- **Grouping**: Groups traces by agent, benchmark, model, and parallel session count
- **Detailed reports**: Generates both summary statistics and individual trace details

#### Usage

```bash
# Basic usage (assumes MLflow is accessible at http://mlflow.localtest.me:8080)
./analyze-run.sh

# With custom MLflow URL and limit
./analyze-run.sh --url http://mlflow.localtest.me:8080 --limit 200

# Auto port-forward from kind cluster if MLflow is not accessible locally
./analyze-run.sh --forward --limit 50

# Filter by experiment name
./analyze-run.sh --experiment baseline

# Compare two experiments
./analyze-run.sh --compare baseline,test1
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --url URL` | MLflow REST API base URL | `http://mlflow.localtest.me:8080` |
| `-l, --limit NUM` | Maximum number of traces to download | `100` |
| `-e, --experiment NAME` | Filter traces by experiment name attribute | (none) |
| `-c, --compare EXP1,EXP2` | Compare two experiments (comma-separated) | (none) |
| `--experiment-id ID` | MLflow experiment ID to query | `0` |
| `-f, --forward` | Auto port-forward MLflow from kind cluster if not accessible | `false` |
| `-h, --help` | Show help message | - |

#### How It Works

1. **Connectivity Test**: Attempts to connect to MLflow REST API health endpoint
2. **Auto Port-Forward** (if `--forward` is used): Sets up port-forwarding from kind cluster if MLflow is not accessible
3. **OAuth2 Authentication**: Obtains a bearer token from the cluster's `mlflow-oauth-secret`
4. **Trace Download**: Queries MLflow's trace API for the specified experiment, with pagination
5. **Format Transformation**: Converts MLflow trace format to the analysis input format via `download_mlflow_traces.py`
6. **Analysis**: Pipes trace data to `analyze_traces.py` for detailed analysis

#### Report Output

The script generates two main sections:

**1. Summary Statistics by Configuration**

Groups traces by (agent, benchmark, model, parallel sessions) and shows:
- Count of traces
- Average, P50, P95, Min, Max for:
  - Session creation time
  - Agent call time
  - Evaluation time
  - LLM call time (with token counts)
  - Tool call time
- Time distribution percentages (LLM%, Tool%, Other%)

**2. Individual Trace Details**

Lists each trace with:
- Trace ID
- Agent, Benchmark, Model, Parallel sessions
- Session creation time
- Agent call time (with LLM% and Tool% breakdown)
- Evaluation time
- LLM tokens (input/output)
- Tool call count and time

#### Example Output

```text
=== MLflow Trace Analysis ===
MLflow URL: http://mlflow.localtest.me:8080
Experiment ID: 0
Limit: 100

✓ Connected to MLflow
✓ OAuth token obtained

Found 45 Agent.Session traces
Downloading traces...
Downloaded 45 traces

=== Trace Analysis Report ===

Summary Statistics by Configuration:
┌─────────────┬───────────┬─────────┬──────────┬───────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Agent       │ Benchmark │ Model   │ Parallel │ Count │ Avg Create  │ Avg Agent   │ Avg Eval    │ Avg LLM     │ Avg Tool    │
│             │           │         │          │       │ (ms)        │ Call (ms)   │ (ms)        │ (ms)        │ (ms)        │
├─────────────┼───────────┼─────────┼──────────┼───────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ tool-calling│ gsm8k     │ gpt-4o  │ 1        │ 45    │ 125.3       │ 8234.5      │ 45.2        │ 6543.2      │ 1234.5      │
│             │           │         │          │       │             │             │             │ (79.5%)     │ (15.0%)     │
└─────────────┴───────────┴─────────┴──────────┴───────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

#### Prerequisites

- **jq**: JSON processor for parsing API responses
  ```bash
  # macOS
  brew install jq
  
  # Ubuntu/Debian
  apt-get install jq
  ```
- **Python 3**: For running the download and analysis scripts
- **MLflow**: Running and accessible (either locally or in kind cluster)
- **kubectl**: For port-forwarding and OAuth token retrieval

#### Troubleshooting

**Connection refused:**
- Ensure MLflow is running: `kubectl get pods -n rossoctl-system -l app=mlflow`
- Use `--forward` flag to auto port-forward from kind cluster
- Manually port-forward: `kubectl port-forward -n rossoctl-system svc/mlflow 8080:5000`

**No traces found:**
- Verify traces exist in MLflow UI: http://mlflow.localtest.me:8080
- Check that Agent.Session spans are being created by the runner
- MLflow tracing is enabled by default; pass `--disable-mlflow` only if you want to skip it

**OAuth errors:**
- Ensure the `mlflow-oauth-secret` exists in the `rossoctl-system` namespace
- Verify the MLflow pod is running (token acquisition executes inside the pod)

### What Gets Traced

When OTEL is enabled, you'll see:

- **Session spans**: Complete session lifecycle with timing
- **MCP operations**: create_session, evaluate_session, close_session
- **A2A requests**: Agent invocations with request/response sizes
- **HTTP calls**: Auto-instrumented outbound requests
- **Errors**: Failed operations with exception details

## In-Cluster Execution (Kubernetes Job)

The runner can execute entirely inside the cluster as a Kubernetes Job — no local machine needed after the image is built. This is the recommended path for CI and automated evaluation runs.

### Overview

`k8s/job.yaml` is the launch template. It references secrets for credentials and passes benchmark/agent flags as container `args`. The job container uses cluster-internal DNS to reach the Rossoctl API, Keycloak, MCP server, and agent — no port-forwarding is required. MLflow tracing switches automatically to HTTP/protobuf when `KUBERNETES_SERVICE_HOST` is set.

### Step 1 — Set up required secrets

Run this **from your local machine** (not inside the cluster) before submitting the job. `update-secrets.sh` creates/patches the API-key secrets via kubectl:

```bash
export OPENAI_API_KEY=sk-...
export HF_TOKEN=hf_...          # optional; skip if not needed
./update-secrets.sh --namespace team1
```

The `rossoctl-test-user` secret (key: `password`) must already exist in `team1` — it is created by the Rossoctl cluster setup and holds the Keycloak password.

> **Note:** The job container itself does not have kubectl RBAC, so `update-secrets.sh` will print harmless warnings if it tries to run inside the cluster. The secrets just need to be present before the job starts.

### Step 2 — Configure the job

Edit `k8s/job.yaml` to set:

| Field | Where | Example |
|-------|-------|---------|
| Benchmark | `args: ["--benchmark", "…"]` | `gsm8k`, `tau2`, `appworld` |
| Agent | `args: ["--agent", "…"]` | `tool_calling` |
| Model | `args: ["--model", "…"]` | `openai/Azure/gpt-4.1` |
| LLM API base | `env: OPENAI_API_BASE` | your LiteLLM proxy URL |

To disable MLflow tracing, add `"--disable-mlflow"` to `args`.

### Step 3 — Submit and watch the job

```bash
# Delete any previous run with the same name first
kubectl delete job exgentic-runner -n team1 --ignore-not-found

# Submit
kubectl apply -f k8s/job.yaml

# Stream logs (the runner prints a summary table at the end)
kubectl logs -f job/exgentic-runner -n team1
```

To watch job status separately:

```bash
kubectl get job exgentic-runner -n team1 -w
```

### Step 4 — View results

**Console output** — the log stream ends with a run summary:

```
============================================================
RUN SUMMARY
============================================================
Max Parallel Sessions: 1
Sessions Attempted:   10
Sessions Succeeded:   9
Sessions With Error:  1
Evaluation Success:   90.0%
Total Wall Time:      312.4s

TIMING BREAKDOWN (average per session)
  Session Creation:   0.05s
  Agent Processing:   31.2s
  Evaluation:         0.02s

AGENT PROCESSING LATENCY
  Average:            31.20s
  P50:                28.00s
  P95:                58.00s
============================================================
```

**MLflow UI** — if MLflow tracing was enabled (the default), open `http://mlflow.localtest.me:8080` to view traces grouped by experiment.

### Iterating with a locally-built image

To test a local image change without pushing to a registry, sync it into the kind cluster first:

```bash
cd exgentic_a2a_runner
docker build -t ghcr.io/rossoctl/workload-harness/exgentic-a2a-runner:dev .
export REMOTE_IMAGE_NAME=ghcr.io/rossoctl/workload-harness/exgentic-a2a-runner:dev
export KIND_CLUSTER_NAME=rossoctl
source ./sync-image-to-cluster.sh
```

Update `k8s/job.yaml` → `image:` to match your local tag, set `imagePullPolicy: IfNotPresent`, and submit as above.


## E2E Test Script

`e2e-test.sh` runs `deploy-and-evaluate.sh` for every benchmark (or a chosen subset) and prints a consolidated results table.

### Basic usage

```bash
# Run all three benchmarks sequentially (gsm8k → tau2 → appworld), 1 task each
./e2e-test.sh --agent tool_calling

# Run only a subset
./e2e-test.sh --agent tool_calling --benchmarks gsm8k,tau2

# Run with more tasks per benchmark
./e2e-test.sh --agent tool_calling --tasks 10

# Run all benchmarks in parallel (each benchmark gets its own port-forward slots)
./e2e-test.sh --agent tool_calling --parallel-jobs

# Run all benchmarks as Kubernetes Jobs (in-cluster mode)
./e2e-test.sh --agent tool_calling --in-cluster

# Dry run — prints all commands without executing them
./e2e-test.sh --agent tool_calling --dry
```

Any flag not recognised by `e2e-test.sh` is forwarded verbatim to `deploy-and-evaluate.sh` (e.g. `--model`, `--experiment`, `--disable-mlflow`, `--plugin-preset`).

### Results table

After all benchmarks finish, the script prints and writes `e2e-results.md`:

```text
| Benchmark | Status | Tasks | Parallel Sessions | Eval Success Rate | Avg Latency (s) | Failures |
|-----------|--------|-------|-------------------|-------------------|-----------------|----------|
| gsm8k     | PASS   | 1     | --                | 100.0%            | 4.2s            | 0        |
| tau2      | PASS   | 1     | --                | 100.0%            | 12.8s           | 0        |
| appworld  | PASS   | 1     | --                | 100.0%            | 9.1s            | 0        |
```

- **Status** is `PASS`, `FAIL`, or `SKIP` (skipped benchmarks appear when a sequential run aborts early). When a step fails, the status includes the step name, e.g. `FAIL(deploy-benchmark)`.
- **Parallel jobs mode** (`--parallel-jobs`): all benchmarks run concurrently; each gets unique OTEL-collector and Prometheus ports so local port-forwards don't collide.
- **In-cluster mode** (`--in-cluster`): one Kubernetes Job is created per benchmark from `k8s/job.yaml`; `e2e-test.sh` streams the logs and checks the job's success status.

## IBAC Comparison Script

`run-ibac-comparison.sh` runs the **same benchmark twice for an
apples-to-apples comparison** — once with an AuthBridge plugin preset and
once as a baseline with no plugins — then compares the two runs with
[`analyze-run.sh --compare`](#analyzing-traces-with-analyze-runsh). Use it
to measure the cost and effect of a plugin pipeline (e.g. IBAC) against an
otherwise identical run.

For each invocation it:

1. Deletes existing deployments, then runs `deploy-and-evaluate.sh` with the
   selected `--plugin-preset` (the *plugin* run).
2. Deletes deployments again, then runs `deploy-and-evaluate.sh` with no
   preset (the *baseline* run).
3. Calls `analyze-run.sh --compare <plugin>,<baseline>` to report the delta.

Both runs share a short random experiment id so their names are unique
across repeated invocations yet paired to each other. Experiment names are
derived from the parameters, e.g.
`gsm8k-10-parallel-1-<id>-ibac` (plugin) and `gsm8k-10-parallel-1-<id>`
(baseline).

The judge is configured from `OPENAI_API_BASE` / `OPENAI_API_KEY` (both
required); these are wired through to the runner and the analysis step.

### Usage

```bash
# Defaults: gsm8k, tool_calling, 10 tasks, 1 session, ibac-only preset
./run-ibac-comparison.sh

# Compare the full pipeline (auth + parsers + IBAC) against baseline
./run-ibac-comparison.sh --plugin-preset full

# Larger run with explicit model and concurrency
./run-ibac-comparison.sh --model gcp/gemini-3-flash-preview \
    --benchmark gsm8k --max-tasks 50 --max-parallel-sessions 4

# Show help
./run-ibac-comparison.sh --help
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--model MODEL` | Model name | `gcp/gemini-3-flash-preview` |
| `--benchmark NAME` | Benchmark name | `gsm8k` |
| `--agent NAME` | Agent name | `tool_calling` |
| `--max-tasks N` | Maximum number of tasks to evaluate | `10` |
| `--max-parallel-sessions N` | Concurrent evaluation sessions | `1` |
| `--plugin-preset PRESET` | Preset for the plugin run: `auth-only`, `ibac-only`, `full` | `ibac-only` |
| `-h, --help` | Show help and exit | - |

For preset contents and pipeline mechanics, see
[AuthBridge Plugin Pipeline](#authbridge-plugin-pipeline).

## Current Limitations

- No retry mechanism for failed operations
- No streaming response support
- Tested only with local kind Rossoctl installation with Podman (not tested with Docker)

## Next Steps

After successful test run:
1. Increase `MAX_TASKS` in `.env` for longer runs
2. Adjust `MAX_PARALLEL_SESSIONS` for different concurrency levels
3. Enable OTLP exporter for telemetry collection
4. Deploy different benchmarks (gsm8k, tau2, appworld)
5. Test with various models via configure script
6. Analyze results and agent performance in Rossoctl UI
