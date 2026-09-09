---
title: Install the cluster CLI
sidebar_label: Install the cluster CLI
description: Install rossoctl, the CLI for a cluster, and run the first commands.
sidebar_position: 7
---

The `rossoctl` command does the tasks that the console does, for a cluster. It also runs a local
RossoCortex proxy around any command.

`rossoctl` is not `abctl`. `abctl` is the viewer for RossoCortex on your computer, and
[Quickstart on a laptop](laptop.md) installs it. The two programs are separate.

For each command and each option, see the [CLI reference](../reference/cli.md).

## Step 1: install the program

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/rossoctl-cli/main/downloadRossoctl | sh
export PATH="$PATH:$HOME/.config/rossoctl"
```

Add the `export` line to the profile of your shell to make the change permanent. You can also move the
program to a directory that is already on your path:

```bash
sudo mv "$HOME/.config/rossoctl/rossoctl" /usr/local/bin/
```

Confirm the installation:

```bash
rossoctl version
```

## Step 2: sign in

For a Kind cluster that you installed from this repository:

```bash
rossoctl login
rossoctl agents list
```

For a shared server, give the address one time:

```bash
rossoctl --server https://<your-host>/api/v1 login
rossoctl agents list
```

The command stores each server, namespace and token as a named context in
`~/.config/rossoctl/config.toml`. The arrangement is the same arrangement that `kubectl` uses:

```bash
rossoctl config get-contexts
rossoctl config use-context dev
rossoctl config set-context --namespace team1
```

To examine the permissions in your token:

```bash
rossoctl auth status
```

## Step 3: deploy an agent

```bash
rossoctl agents import from-image \
  --name orders \
  --containerImage ghcr.io/x/y:latest \
  --envVar LOG_LEVEL=debug

rossoctl agents wait orders --timeout 5m
rossoctl agents get orders
```

The `agents wait` command exits when the agent is ready, so you can put it in a sequence of commands. It
also exits with an error when the agent cannot become ready. The causes are a failed build, a rollout
that passed its time limit, or a name that the server does not have.

The `rossoctl tools` commands operate on tools in the same way.

## Run a command behind RossoCortex

You can put a local RossoCortex proxy around any command, with no cluster. This method is the method
that [Quickstart on a laptop](laptop.md) uses, with explicit configuration:

```bash
rossoctl authbridge exec \
  --config ./authbridge.yaml \
  -- claude "explain this repo"
```

The `--config` option accepts a local YAML file or an address that serves YAML. The command passes each
argument after `--` to your program without a change, and exits with the exit status of your program.

The command sets `HTTP_PROXY`. It sets `HTTPS_PROXY` and the certificate variables also when the TLS
bridge runs. It does not change a variable that you already set. It stops each part when your program
exits.

The log of RossoCortex goes to the file that `--logfile` names. The default file is
`/tmp/authbridge.log`. A separate file keeps the log out of the output of your program.

## Next

- [CLI reference](../reference/cli.md) lists each command.
- [Deploy an agent](../workloads/deploy-an-agent.md) lists each deployment option.
