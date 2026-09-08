---
title: Observability
description: Traces, network topology, and per-agent metrics.
sidebar_position: 5
---

Agents are hard to debug from logs alone: a single user request fans out into model calls, tool calls,
and messages to other agents. Rossoctl gives you three views — traces for what happened in one request,
network topology for how workloads talk, and metrics for cost and volume.

## What to install

| Flag | Adds | Gives you |
| --- | --- | --- |
| `--with-otel` | OpenTelemetry collector | Trace collection |
| `--with-mlflow` | MLflow, plus OTel and ambient mesh | A trace backend and per-agent experiments |
| `--with-kiali` | Kiali and Prometheus, plus ambient mesh | Network topology and metrics |

`--with-all` installs all three. Note that MLflow and Kiali both pull in the Istio ambient mesh, which
adds to your resource footprint — see [sizing](index.md#sizing).

## Traces

A trace shows one request end to end: which tools were called, in what order, how long each took, and
what the model was asked.

### Where they go

The operator wires this up for you. It discovers MLflow instances in the cluster, creates a per-agent
experiment, and configures the workload to export traces there. You do not add tracing code to your
agent.

Open traces from the console's **Observability** page, or go to MLflow directly. Run
`./.github/scripts/local-setup/show-services.sh` for the URL.

### Your own spans

The transport is handled, but only your agent knows its own internal steps. Instrument with the
OpenTelemetry SDK for your language and the spans join the same trace.

### Traces without a cluster

`rossoctl` runs a local collector that forwards to MLflow, which is useful when developing an agent on
your machine:

```bash
rossoctl otel collect
```

This generates a collector configuration under `~/.config/rossoctl/otel` and starts the
OpenTelemetry contrib collector, receiving OTLP on `4317` (gRPC) and `4318` (HTTP). It needs `docker` or
`podman` on your path.

MLflow has to be listening for spans to arrive:

```bash
mlflow server --host 0.0.0.0 --port 5001 --allowed-hosts '*'
```

Both flags matter. MLflow otherwise binds loopback, which a container cannot reach, and rejects requests
whose `Host` header is `host.containers.internal`.

If nothing is on the endpoint's port, `rossoctl otel collect` says so and starts anyway — the exporter
retries, so you can start MLflow afterwards.

Check the path from your machine to MLflow without an instrumented workload:

```bash
rossoctl otel send-mock-trace --serviceName my-agent
```

`--serviceName` sets the `service.name` attribute, which is what MLflow groups by — so it is the name
your test span appears under. Each run uses fresh trace and span IDs, so every invocation is a distinct
trace.

The container runs detached. Stop it with `podman stop` or `docker stop`, using the name printed at
startup.

Trace Claude Code itself:

```bash
rossoctl otel collect
rossoctl authbridge exec --with-claude-otel --config ./authbridge.yaml -- claude
```

## Network topology

Kiali shows which workloads are talking to which, with request rates and error rates on each edge. It is
the fastest way to answer "is my agent even reaching that tool?"

Open it from the console's **Observability** page. Kiali needs the Istio ambient mesh, which
`--with-kiali` enables automatically.

The topology view is also how you spot traffic that should not exist — an agent reaching a service
nobody expected.

## Metrics and cost

Prometheus arrives with `--with-kiali` and collects standard workload metrics.

For token cost specifically, Cortex sees every model call and is where cost data comes from. On your
machine, `abctl` shows it live. In a cluster, the budget plugins track and enforce limits — see
[Reduce token cost](../guardrails/token-cost.md).

## Checking that traces work

1. Confirm the collector is running: `kubectl get pods -n rossoctl-system | grep otel`.
2. Confirm MLflow is up and reachable.
3. Send a request to an agent, through the console's **Chat**.
4. Look for a new run under that agent's experiment in MLflow.

If the trace never appears, the usual causes are the collector not running, MLflow bound to loopback, or
the agent's export endpoint not configured — check the agent pod's environment for `OTEL_*` variables.

## Related

- [Troubleshooting](troubleshooting.md).
- [Reduce token cost](../guardrails/token-cost.md).
- [CLI reference](../reference/cli.md) — every `rossoctl otel` flag.
