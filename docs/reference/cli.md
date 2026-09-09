---
title: CLI reference
sidebar_label: CLI
description: Each rossoctl command and each option.
sidebar_position: 2
---

The `rossoctl` command uses the Rossoctl interface. It also runs a local RossoCortex proxy, with no
cluster.

To install the program, see [Install the CLI](../get-started/cli.md).

```bash
rossoctl --help
rossoctl version
rossoctl install        # Prints the instructions to install the platform
```

## The global options

| Option | Function |
| --- | --- |
| `--server URL` | Uses this server and not the server of the current context. |
| `--context NAME` | Uses a named context, with its server, its token and its namespace. The option can be before or after the subcommand. |
| `--json` | Returns JSON. Most read commands accept this option. |

## Contexts

The command stores each server, namespace and token as a named context in
`~/.config/rossoctl/config.toml`. The arrangement is the arrangement that `kubectl` uses. The command
stores each credential separately, in `~/.local/state/dam/auth.toml`.

```bash
rossoctl config get-contexts
rossoctl config create-context --name dev \
    --server http://my-host:8080/api/v1/ --namespace team1 --bearer-token <token>
rossoctl config use-context dev
rossoctl config set-context --namespace team1
rossoctl config set-context --namespace team1 --server http://other:8080/api/v1/
rossoctl config set-context --name prod      # Renames the current context
```

The `create-context` command makes the new context current. The `set-context --namespace` command gives a
warning if the server does not have that namespace.

:::note An empty list is correct
The `get-contexts` command creates nothing. It therefore prints an empty table until a different command
creates the configuration. That command creates two contexts. The first context is for the default server
and becomes current. The second context is a local context with the name `cortex`.
:::

## Authentication

```bash
rossoctl login                                   # An OAuth device flow against Keycloak
rossoctl login --token <token>                   # Sets a token on the current context
rossoctl login --server http://host:8080/api/v1/ --token <token>
rossoctl login --cortex                          # Selects the local cortex context
```

The `login --server` command selects the context for that host. It creates the context if the context is
absent, and then makes it current.

The `cortex` context needs no server and no token. The command answers each request inside its own
process, from the records that `authbridge exec` wrote. The `cortex serve` command and the
`authbridge exec` command both create the context if it is absent. The `cortex serve` command also makes
it current. The `authbridge exec` command does not, because that command runs a different program and must
not change the context for a later command.

### Examine your token

```bash
rossoctl auth status                # The name, the user name, the address, the issuer, the expiry time, the audiences, the roles and the scopes
rossoctl auth status --json         # The claims as JSON
rossoctl auth status --context prod
```

The command reads the token on your computer. It sends nothing.

```bash
rossoctl auth token                 # Prints the token and nothing else
```

:::warning
The `auth token` command writes a credential to the standard output. A terminal keeps that output in its
history, and a build pipeline keeps it in the build log.

The command exits with an error when the context has no token. A shell substitution therefore fails, and
does not produce an empty value.
:::

```bash
curl -H "Authorization: Bearer $(rossoctl auth token)" \
  "http://my-host:8080/api/v1/agents?namespace=team1"
```

### Examine the server

```bash
rossoctl auth-config                # Reads <server>/auth/config
rossoctl auth-config --json
rossoctl status                     # The current session and the state of the platform
rossoctl status --json
```

## Agents

```bash
rossoctl agents list                          # The namespace of the context, or --namespace
rossoctl agents --namespace team2 list
rossoctl agents list --all-namespaces         # -A: reads /namespaces, then lists each one
rossoctl agents list --no-headers             # Omits the header row
rossoctl agents get orders                    # One agent, in a single column
rossoctl agents get orders --json
rossoctl agents delete orders
```

With the `--no-headers` option, the message "no agents found" goes to the standard error. The standard
output is therefore empty when there is no agent, and a pipeline receives no row:

```bash
rossoctl agents list --no-headers | awk '{print $1}' | xargs -n1 rossoctl agents delete
```

### Wait for an agent

```bash
rossoctl agents wait orders
rossoctl agents wait orders --timeout 5m      # The default is 60s. Use 0 to wait without a limit.
rossoctl agents wait orders -v                # Reports the progress on the standard error
```

The command reads the state every 2 seconds. It exits with the code 0 when the agent is ready. You can
therefore put it in a sequence:

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
  && rossoctl agents wait orders --timeout 5m \
  && ./run-integration-tests.sh
```

The command exits with an error when the agent cannot become ready. The three causes are a failed build, a
rollout that passed its time limit, and a name that the server does not have. An immediate error is more
useful than an error after the time limit.

### Import an agent

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest

rossoctl agents import --deployment-type sandbox from-image \
    --name orders --containerImage ghcr.io/x/y:latest \
    --imagePullSecret regcred \
    --envVarsURL https://example.com/orders.env
```

| Option | Function |
| --- | --- |
| `--containerImage` | The address of the image. |
| `--imagePullSecret` | The Secret for a private registry. |
| `--envVar KEY=VALUE` | Sets one variable. You can repeat the option. The value is literal, and can contain a comma. |
| `--envVarsURL URL` | Reads `key=value` lines from an address. |
| `--deployment-type` | Selects `deployment`, `statefulset` or `sandbox`. |
| `--context NAME:PATH` | Attaches an [agent context](../concepts/experiments/agent-context.md). |
| `--additionalParameterJSON` | Sends a field that has no option. |

If `--envVar` and `--envVarsURL` set the same variable, `--envVar` wins. The order of the options does not
change this result:

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
    --envVar LOG_LEVEL=debug --envVar 'TAGS=a,b,c'
```

The `--additionalParameterJSON` option accepts a JSON object, or the name of a file that contains one. A
value that starts with `{` is the object. Each other value is a file name.

You can repeat the option. The command combines the objects. A later object replaces a key that it shares
with an earlier object. The command then adds the result to the request. The combination uses the
top-level keys, so a repeated key replaces the complete value. A key that names a field that an option
also sets replaces the value of that option.

```bash
rossoctl agents import from-image --name orders --containerImage ghcr.io/x/y:latest \
    --additionalParameterJSON ./base.json \
    --additionalParameterJSON '{"containerImage":"ghcr.io/x/y:pinned"}'
```

### The RossoCortex configuration of an agent

```bash
rossoctl agents authbridge get orders          # The mode, and the two chains in execution order
rossoctl agents authbridge get orders --json
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml
rossoctl agents authbridge set orders --policy-file ./authbridge.yaml --wait
```

The `--policy-file` option is necessary. The command sends the file as `text/plain` and without a change.
Your comments and your key order therefore remain, and the server validates the file.

The `--wait` option reads the configuration before the write. It then reads the configuration every 2
seconds until the result differs from that first value. It stops after 2 minutes.

The comparison uses the first value and not the file. The file is YAML for a ConfigMap. The read returns
the JSON that the sidecar gives, and the sidecar removes each secret from that JSON. The signal is
therefore a change. The command cannot confirm a configuration that is already active. In that case it
reaches its time limit and exits with an error.

## Tools

The `tools` commands operate on the `/tools` endpoint. The `--namespace`, `--context`,
`--all-namespaces`, `--json` and `--no-headers` options operate in the same way.

```bash
rossoctl tools list
rossoctl tools list --all-namespaces
rossoctl tools get weather-mcp
rossoctl tools wait weather-mcp --timeout 10m
rossoctl tools delete weather-mcp
rossoctl tools import from-image --name weather-mcp --containerImage ghcr.io/x/y:latest
```

The `--ports` option sets the service ports. The format is `name:port:targetPort[:protocol]`. The default
is `http:9090:9090:TCP`. A number alone means `http:<port>:<port>:TCP`:

```bash
rossoctl tools import from-image --name weather-mcp --containerImage ghcr.io/x/y:latest \
    --ports grpc:9000:9001:TCP,8080
```

A tool that Rossoctl builds from source reports `Building` until the build ends. A build often needs more
time than the default limit of 60 seconds. Give a longer limit. If the build fails, the command reports
`Build Failed` and exits at once.

:::note
Against the local `cortex` context, the `tools wait` command reaches its time limit. That server does not
have the endpoint that the command reads, and the `tools get` command fails for the same reason. Use
`tools list` for a local tool. The `agents wait` command operates correctly.
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

See [Agent context](../concepts/experiments/agent-context.md).

## RossoCortex on your computer

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
rossoctl authbridge exec --config https://example.com/authbridge.yaml -- ./script.sh --verbose
```

The `--config` option is necessary. It accepts a local YAML file or an address that serves YAML. For an
address, the command writes the content to a temporary file and deletes that file when it exits.

The command gives each argument after `--` to your program without a change. It exits with the exit status
of your program.

The command sets `HTTP_PROXY` for the proxy. It sets `HTTPS_PROXY` and the certificate variables also when
the TLS bridge runs. The certificate variables are `NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE` and
`SSL_CERT_FILE`. The command does not change a variable that you already set. It stops each part when your
program exits, and also on a `SIGINT` signal or a `SIGTERM` signal.

| Option | Function |
| --- | --- |
| `--config FILE\|URL` | Necessary. The configuration of the chain. |
| `--with-claude-otel` | Also sets the variables that make Claude Code send traces to the local collector. |
| `--logfile PATH` | The log of RossoCortex. The default is `/tmp/authbridge.log`. Use `""` for the standard error. |

The log goes to a file and not to the standard error, so it does not mix with the output of your program.
The command prints the path at the start.

## Traces

```bash
rossoctl otel collect
rossoctl otel collect --traces_endpoint http://host.containers.internal:5002/v1/traces
rossoctl otel send-mock-trace
rossoctl otel send-mock-trace --serviceName my-agent
rossoctl otel send-mock-trace --url http://localhost:14318/v1/traces
```

The `otel collect` command writes a configuration file to `~/.config/rossoctl/otel`. It then starts the
OpenTelemetry collector with that file. The collector receives OTLP on port 4317 for gRPC and on port 4318
for HTTP. The command needs `docker` or `podman` on your path. The container runs in the background. To
stop it, use `podman stop` or `docker stop` with the name that the command printed.

The default `--traces_endpoint` value reaches your computer from inside the container. Inside the
container, the name `localhost` means the collector.

The command records two values in `~/.config/rossoctl/otel-config.yaml`. The first value is the path of
the configuration file. The second value is the address that a client uses to reach the collector, which
is `127.0.0.1:4318`. That address is the address to send to, and not the `0.0.0.0` address that the
collector listens on inside the container.

The `send-mock-trace` command sends one span. Use it to test the path from your computer to your trace
store, without an agent. The `--serviceName` option sets the `service.name` attribute. A trace store groups
the traces by that attribute, so it is the name that your span has in the interface. Each command uses new
identifiers, so each command produces a separate trace.

See [Observability](../operate/observability.md).
