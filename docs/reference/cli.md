---
title: CLI reference
sidebar_label: CLI
description: Every rossoctl command.
sidebar_position: 2
---

`rossoctl` talks to the Rossoctl API, and also runs a local Cortex pipeline without a cluster.

To install it, see [Install the CLI](../get-started/cli.md).

```bash
rossoctl --help
rossoctl version
rossoctl install        # print instructions for installing the platform
```

## Global flags

| Flag | Effect |
| --- | --- |
| `--server URL` | Use this API server instead of the current context's. |
| `--context NAME` | Use a named context — its server, token, and namespace. May appear before or after the subcommand. |
| `--json` | Raw JSON instead of formatted output. Available on most read commands. |

## Contexts

Servers, namespaces, and tokens are stored as named contexts in `~/.config/rossoctl/config.yaml`, the
way `kubectl` does it.

```bash
rossoctl config get-contexts
rossoctl config create-context --name dev \
    --server http://my-host:8080/api/v1/ --namespace team1 --bearer-token <token>
rossoctl config use-context dev
rossoctl config set-context --namespace team1
rossoctl config set-context --namespace team1 --server http://other:8080/api/v1/
rossoctl config set-context --name prod      # rename the current context
```

`create-context` makes the new context current. `set-context --namespace` warns if the server does not
recognise the namespace.

:::note An empty context list is normal
`get-contexts` never creates anything, so it prints an empty table until another command seeds the
config. Seeding creates two contexts: one for the default API server, which becomes current, and a local
`cortex` one.
:::

## Authentication

```bash
rossoctl login                                   # OAuth device flow against the server's Keycloak
rossoctl login --token <token>                   # set a token on the current context
rossoctl login --server http://host:8080/api/v1/ --token <token>
rossoctl login --cortex                          # switch to the local cortex context
```

`login --server` targets the context for that host, creating it if absent, and makes it current.

The `cortex` context is answered inside the command's own process from the records
`authbridge exec` wrote. It needs no server and no token. `cortex serve` and `authbridge exec` both create
it if missing — `cortex serve` also makes it current, `authbridge exec` deliberately does not, since it
hosts an unrelated command and must not repoint later invocations.

### Inspecting your token

```bash
rossoctl auth status                # name, username, email, issuer, expiry, audiences, roles, scopes
rossoctl auth status --json         # the decoded claims
rossoctl auth status --context prod
```

The token is decoded locally. Nothing is sent.

```bash
rossoctl auth token                 # print the raw bearer token and nothing else
```

:::warning
`auth token` writes a credential to stdout. A terminal keeps it in scrollback and CI keeps it in the
build log. It exits non-zero when the context holds no token, so a shell substitution fails rather than
expanding to an empty string.
:::

```bash
curl -H "Authorization: Bearer $(rossoctl auth token)" \
  "http://my-host:8080/api/v1/agents?namespace=team1"
```

### Server configuration

```bash
rossoctl auth-config                # GET <server>/auth/config
rossoctl auth-config --json
rossoctl status                     # current session and platform status, as the console's admin page
rossoctl status --json
```

## Agents

```bash
rossoctl agents list                          # the context's namespace, or --namespace
rossoctl agents --namespace team2 list
rossoctl agents list --all-namespaces         # -A: discover via /namespaces and list across all
rossoctl agents list --no-headers             # omit the header row, for piping
rossoctl agents get orders                    # detail view, laid out like the console page
rossoctl agents get orders --json
rossoctl agents delete orders
```

With `--no-headers`, the "no agents found" notice goes to stderr, so stdout is empty when there is
nothing to list and a pipeline sees no rows:

```bash
rossoctl agents list --no-headers | awk '{print $1}' | xargs -n1 rossoctl agents delete
```

### Waiting for readiness

```bash
rossoctl agents wait orders
rossoctl agents wait orders --timeout 5m      # default 60s; --timeout 0 waits indefinitely
rossoctl agents wait orders -v                # progress on stderr
```

Polls every 2 seconds and exits `0` as soon as the agent is ready, so it can gate what follows:

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
  && rossoctl agents wait orders --timeout 5m \
  && ./run-integration-tests.sh
```

It ends early and non-zero when readiness will never arrive — a failed build, a rollout past its
deadline, or a name the server does not know. Reporting that immediately beats spending the timeout to
report the wrong cause.

### Importing

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest

rossoctl agents import --deployment-type sandbox from-image \
    --name orders --containerImage ghcr.io/x/y:latest \
    --imagePullSecret regcred \
    --envVarsURL https://example.com/orders.env
```

| Flag | Meaning |
| --- | --- |
| `--containerImage` | Image URI. |
| `--imagePullSecret` | Secret for a private registry. |
| `--envVar KEY=VALUE` | One variable. Repeatable. Values are literal, commas included. |
| `--envVarsURL URL` | Newline-separated `key=value` fetched from a URL. |
| `--deployment-type` | `deployment` (default), `statefulset`, or `sandbox`. |
| `--context NAME:PATH` | Mount an [agent context](../workloads/agent-context.md). |
| `--additionalParameterJSON` | Request fields the CLI has no flag for. |

`--envVar` wins over `--envVarsURL` for the same variable, whichever order the flags appear in:

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
    --envVar LOG_LEVEL=debug --envVar 'TAGS=a,b,c'
```

`--additionalParameterJSON` takes a JSON object, or the name of a file containing one — a value starting
with `{` is the document itself, anything else is a filename. It is repeatable; the objects are merged,
a later one winning a shared key, and the result is overlaid onto the request body. Merging is by
top-level key, so a repeated key is replaced whole rather than combined. Keys naming a field the other
flags set will override them.

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
    --additionalParameterJSON ./base.json \
    --additionalParameterJSON '{"containerImage":"ghcr.io/x/y:pinned"}'
```

### Cortex configuration

```bash
rossoctl agents authbridge get orders          # mode, plus inbound and outbound pipelines in order
rossoctl agents authbridge get orders --json
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml --wait
```

`--policy-file` is required, and its bytes are sent verbatim as `text/plain`, so comments and key order
survive and the server validates rather than the CLI.

`--wait` reads the configuration before writing, then polls every 2 seconds until what Cortex reports
differs from that baseline, giving up after 2 minutes. The comparison is against the baseline, not the
file — the file is YAML written to a ConfigMap, while the read returns the live, redacted JSON a sidecar
serves. Because a *change* is the signal, re-applying the configuration already in effect cannot be
confirmed: it times out and exits non-zero, saying so.

## Tools

Tools mirror agents, against the `/tools` endpoint. `--namespace`, `--context`, `--all-namespaces`,
`--json`, and `--no-headers` behave the same.

```bash
rossoctl tools list
rossoctl tools list --all-namespaces
rossoctl tools get weather-mcp
rossoctl tools wait weather-mcp --timeout 10m
rossoctl tools delete weather-mcp
rossoctl tools import from-image --name weather-mcp --containerImage ghcr.io/x/y:latest
```

`--ports` sets service ports as `name:port:targetPort[:protocol]`. The default is `http:9090:9090:TCP`,
and a bare number means `http:<port>:<port>:TCP`:

```bash
rossoctl tools import from-image --name weather-mcp --containerImage ghcr.io/x/y:latest \
    --ports grpc:9000:9001:TCP,8080
```

A tool built from source reports `Building` until the build finishes, often longer than the 60-second
default — allow for it. A failed build reports `Build Failed` and ends the wait immediately.

:::note
Against the local `cortex` context, `tools wait` runs to its timeout: that server does not implement the
tool detail endpoint it polls, and `tools get` fails there for the same reason. Use `tools list` to check
a local tool. `agents wait` works normally.
:::

## Namespaces

```bash
rossoctl namespaces list
```

## Agent context

```bash
rossoctl context storage-classes
rossoctl context create research --shared --size 10Gi --storage-class ibm-scale-csi
rossoctl context list
rossoctl context get research
rossoctl context delete research

rossoctl agents import --deployment-type sandbox \
    --context research:/workspace \
    from-image --name researcher --containerImage IMAGE
```

See [Agent context](../workloads/agent-context.md).

## Cortex on your machine

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
rossoctl authbridge exec --config https://example.com/authbridge.yaml -- ./script.sh --verbose
```

`--config` is required and takes a local YAML file or a URL serving YAML. A remote config is fetched to a
temporary file, removed on exit. Everything after `--` is passed to the command untouched, and
`rossoctl` exits with the command's exit status.

The command's environment is pointed at whatever started: `HTTP_PROXY` for the forward proxy, plus
`HTTPS_PROXY` and the CA trust variables (`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`)
when the TLS bridge runs. Variables already set in your environment are left alone. Everything shuts down
when the command exits, or on `SIGINT` or `SIGTERM`.

| Flag | Effect |
| --- | --- |
| `--config FILE\|URL` | Required. The pipeline configuration. |
| `--with-claude-otel` | Also export the variables that make Claude Code send traces to the local collector. |
| `--logfile PATH` | Cortex's own log. Default `/tmp/authbridge.log`; pass `""` to log to stderr. |

Cortex's log goes to a file rather than stderr so it does not interleave with the hosted command's
output. The path is printed at startup.

## Tracing

```bash
rossoctl otel collect
rossoctl otel collect --traces_endpoint http://host.containers.internal:5002/v1/traces
rossoctl otel send-mock-trace
rossoctl otel send-mock-trace --serviceName my-agent
rossoctl otel send-mock-trace --url http://localhost:14318/v1/traces
```

`otel collect` generates a collector configuration under `~/.config/rossoctl/otel` and starts the
OpenTelemetry contrib collector with it mounted, receiving OTLP on `4317` (gRPC) and `4318` (HTTP). It
needs `docker` or `podman` on your path, and runs detached — stop it with `podman stop` or `docker stop`
using the name printed at startup.

The default `--traces_endpoint` reaches the host from inside the container, where `localhost` would mean
the collector itself.

The generated configuration path, and the address a client should use to reach the receiver
(`127.0.0.1:4318` — the dialable form, not the `0.0.0.0` the receiver binds inside the container), are
recorded in `~/.config/rossoctl/otel-config.yaml`.

`send-mock-trace` posts one span, to check the path from here to your trace backend without an
instrumented workload. `--serviceName` sets the `service.name` resource attribute, which is what a
backend groups by — so it is the name the span is listed under. Random trace and span IDs each run, so
every invocation is a distinct trace.

See [Observability](../operate/observability.md).
