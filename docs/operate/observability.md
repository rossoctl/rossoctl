---
title: Observability
description: Traces, the network diagram, and the metrics for each agent.
sidebar_position: 5
---

A log is not sufficient to diagnose an agent. One request from a user produces many model calls, tool
calls and messages to other agents. Rossoctl therefore gives you three views. A trace shows what happened
in one request. A network diagram shows which workloads communicate. The metrics show the volume and the
cost.

## What to install

| Option | What it adds | What you get |
| --- | --- | --- |
| `--with-otel` | The OpenTelemetry collector | Trace collection |
| `--with-mlflow` | MLflow. It enables the collector and the ambient mesh also. | A trace store, and an experiment for each agent |
| `--with-kiali` | Kiali and Prometheus. It enables the ambient mesh also. | The network diagram and the metrics |

The `--with-all` option installs each one. MLflow and Kiali both need the Istio ambient mesh, which uses
more memory and CPU. See [Machine size](index.md#machine-size).

## Traces

A trace shows one request from the start to the end. It gives the tools that the agent called, the order
of the calls, the duration of each call, and the request that went to the model.

### Where the traces go

The operator configures this path for you. It finds an MLflow instance in the cluster, creates an
experiment for each agent, and configures the workload to send the traces there. You do not add code to
your agent.

To read the traces, use the **Observability** page of the console, or open MLflow directly. To get the
address, run `./.github/scripts/local-setup/show-services.sh`.

### To add your own spans

The transport is present, but only your agent knows its internal steps. Use the OpenTelemetry library for
your language. Your spans then join the same trace.

### Traces without a cluster

The CLI runs a local collector that sends the traces to MLflow. This method is useful when you develop an
agent on your computer:

```bash
rossoctl otel collect
```

The command writes a configuration file to `~/.config/rossoctl/otel` and starts the OpenTelemetry
collector with that file. The collector receives OTLP on port 4317 for gRPC and on port 4318 for HTTP. The
command needs `docker` or `podman` on your path.

MLflow must listen before a trace can arrive:

```bash
mlflow server --host 0.0.0.0 --port 5001 --allowed-hosts '*'
```

Both options are necessary. Without `--host`, MLflow listens on the loopback address, which a container
cannot reach. Without `--allowed-hosts`, MLflow rejects a request that has the container host name.

If nothing listens on the port, `rossoctl otel collect` reports the condition and starts the collector.
The collector repeats the transmission, so you can start MLflow after the collector.

To test the path from your computer to MLflow, and without an agent:

```bash
rossoctl otel send-mock-trace --serviceName my-agent
```

The `--serviceName` option sets the `service.name` attribute. MLflow groups the traces by that attribute,
so it is the name that your test span has in the interface. Each command uses new identifiers, so each
command produces a separate trace.

The container runs in the background. To stop it, use `podman stop` or `docker stop` with the name that
the command printed at the start.

To collect the traces of Claude Code:

```bash
rossoctl otel collect
rossoctl authbridge exec --with-claude-otel --config ./authbridge.yaml -- claude
```

## The network diagram

Kiali shows which workloads communicate, with the request rate and the error rate for each connection. It
is the fastest way to answer this question: does my agent reach that tool?

Open Kiali from the **Observability** page of the console. Kiali needs the Istio ambient mesh. The
`--with-kiali` option enables the mesh.

The diagram also shows a connection that must not exist. An example is an agent that reaches a service
that no person expected.

## The metrics and the cost

The `--with-kiali` option installs Prometheus, which collects the standard metrics of each workload.

For the token cost, RossoCortex is the source, because each model call passes through it. On your
computer, `abctl observe` shows the cost as it happens; to read those numbers, see
[Read the numbers](../get-started/reading-the-numbers.md). In a cluster, the budget plugins record and
limit the cost. See [Cost control](../concepts/experiments/cost-control.md).

## Confirm that the traces operate

1. Confirm that the collector runs: `kubectl get pods -n rossoctl-system | grep otel`.
2. Confirm that MLflow runs and is reachable.
3. Send a message to an agent from the **Chat** page of the console.
4. Look for a new record in the experiment of that agent, in MLflow.

If no trace arrives, examine these three causes. The collector does not run. MLflow listens on the
loopback address. The agent has no destination address. For the third cause, examine the environment of
the pod:

```bash
kubectl exec -n <namespace> <pod> -- env | grep OTEL_
```

## Related pages

- [Troubleshooting](troubleshooting.md)
- [Cost control](../concepts/experiments/cost-control.md)
- [CLI reference](../reference/cli.md) lists each `rossoctl otel` option.
