---
title: Install the CLI
description: Install rossoctl and run your first commands.
sidebar_position: 7
---

`rossoctl` does what the console does, from a terminal — list and deploy agents and tools, inspect
tokens, and run a local Cortex pipeline around any command.

For every command and flag, see the [CLI reference](../reference/cli.md).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/rossoctl-cli/main/downloadRossoctl | sh
export PATH="$PATH:$HOME/.config/rossoctl"
```

Add the `export` line to your shell profile to make it permanent, or move the binary onto your
existing path:

```bash
sudo mv "$HOME/.config/rossoctl/rossoctl" /usr/local/bin/
```

Check it:

```bash
rossoctl version
```

## Log in

Against a Kind cluster installed from this repository:

```bash
rossoctl login
rossoctl agents list
```

Against a shared API server, give it the server URL once:

```bash
rossoctl --server https://<your-host>/api/v1 login
rossoctl agents list
```

`rossoctl` stores servers, namespaces, and tokens as named contexts in
`~/.config/rossoctl/config.yaml`, the way `kubectl` does:

```bash
rossoctl config get-contexts
rossoctl config use-context dev
rossoctl config set-context --namespace team1
```

Check what your token actually grants:

```bash
rossoctl auth status
```

## Deploy an agent

```bash
rossoctl agents import from-image \
  --name orders \
  --containerImage ghcr.io/x/y:latest \
  --envVar LOG_LEVEL=debug

rossoctl agents wait orders --timeout 5m
rossoctl agents get orders
```

`agents wait` exits as soon as the agent is ready, so you can chain it. It also exits early and
non-zero when readiness will never come — a failed build, a rollout past its deadline, or a name
the server does not know.

Tools mirror the same commands against `rossoctl tools`.

## Run a command behind Cortex

You can put a local Cortex pipeline around any command, without a cluster. This is the same thing
[Quickstart: your laptop](laptop.md) does, with explicit configuration:

```bash
rossoctl authbridge exec \
  --config ./authbridge.yaml \
  -- claude "explain this repo"
```

`--config` takes a local YAML file or a URL serving YAML. Everything after `--` is passed to the
command untouched, and `rossoctl` exits with that command's exit status.

It sets `HTTP_PROXY`, and `HTTPS_PROXY` plus the CA trust variables when the TLS bridge runs.
Variables you already set are left alone, and everything is shut down when the command exits.

Cortex's own log goes to `--logfile` (default `/tmp/authbridge.log`) so it does not interleave with
your command's output.

## Next

- [CLI reference](../reference/cli.md) — every command.
- [Deploy an agent](../workloads/deploy-an-agent.md) — all the deployment options.
