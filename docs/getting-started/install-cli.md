---
title: Install the CLI
description: Test agents and administer with a command line
sidebar_label: Install the CLI
sidebar_position: 60
---

## Install

The `downloadRossoctl` script downloads the release archive for your platform,
extracts it, and installs the binary at
`$HOME/.config/rossoctl/rossoctl`:

```sh
curl -fsSL https://raw.githubusercontent.com/rossoctl/rossoctl-cli/main/downloadRossoctl | sh
PATH=$PATH:$HOME/.config/rossoctl
# add the above to your shell profile to make it permanent
# alternately, `sudo mv $HOME/.config/rossoctl/rossoctl /usr/local/bin`
```

## Quick usage, for shared Rossoctl API servers

If you have been invited to use a cloud-hosted Rossoctl, use the `--server` option when logging in. This will bring up a web page. Choose w3id for shared cluster login.

```sh
rossoctl --server https://rossoctl-ui.apps.yorktown3.ibm.com/api/v1 login
rossoctl agents list
```

## Quick usage, for existing Kind cluster Rossoctl API server

```sh
rossoctl login
rossoctl agents list
```

## Local Cortex

The CLI allows you to work with agents running locally, using AuthBridge, without deploying to a Kubernetes cluster.

### Running a command behind an AuthBridge pipeline

Rossoctl can be used to test how an agent runs under an AuthBridge configuration on your laptop. It provides an in-process implementation of AuthBridge.

```sh
rossoctl authbridge exec \
   --config https://raw.githubusercontent.com/rossoctl/rossoctl-cli/refs/heads/main/examples/context-guru-tls-bridge.yaml \
   -- claude
```

The command's environment is pointed at whatever was started: `HTTP_PROXY` for the
forward proxy, plus `HTTPS_PROXY` and the CA trust variables
(`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`) when the TLS
bridge runs. Variables already set in your environment are left alone. Everything
is shut down when the command exits or on SIGINT/SIGTERM.

The _rossoctl_ CLI also supports arguments for testing an AuthBridge container image.

`--with-claude-otel` additionally exports the variables that make Claude Code send
traces to the local collector.

```sh
rossoctl otel collect
rossoctl authbridge exec \
  --with-claude-otel \
   --config https://raw.githubusercontent.com/rossoctl/rossoctl-cli/refs/heads/main/examples/context-guru-tls-bridge.yaml \
   -- claude
```

AuthBridge's own log output goes to `--logfile` (default `/tmp/authbridge.log`)
rather than stderr, so it does not interleave with the hosted command's output.
The path is printed at startup; pass `--logfile ""` to log to stderr instead.

---

## Further information

See the [rossoctl-cli](https://github.com/rossoctl/rossoctl-cli) repo for more information about the capabilities of the CLI.
