---
title: Quickstart on a laptop
sidebar_label: Quickstart — laptop
description: Run RossoCortex as one program and see the traffic of your agent.
sidebar_position: 2
---

RossoCortex is the data plane of Rossoctl. It runs as one program on macOS or Linux. It is a proxy on the request path of your agent. It shows each model call, each tool call and each
agent message as it happens. You do not need Kubernetes.

The traffic stays on your computer. RossoCortex does not send it to Rossoctl or to any other service.

This procedure needs approximately 5 minutes.

## Before you start

You need:

- macOS or Linux, on amd64 or arm64.
- An agent. The installer configures [Claude Code](https://claude.com/claude-code) for you. Any agent
  operates. See [Other agents](#other-agents).

## Step 1: install the program

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/cortex/main/authbridge/install.sh \
  | sh -s -- --claude-code
```

The script asks for your permission before it changes the settings of Claude Code. It then runs
RossoCortex as a background service. The service restarts after a failure and after you sign in again.

:::note
The address of the script is on the `main` branch. The script then runs the copy from the most recent
release. The command therefore does not run unreleased code. To select a different version, use the
`--ref` option.
:::

## Step 2: watch the traffic

Open two terminals. In the first terminal, run the viewer:

```bash
abctl observe
```

In the second terminal, run your agent:

```bash
claude
```

Use Claude Code in the normal way. There is no environment variable to set. The calls of the agent
appear in `abctl`.

In `abctl observe`, press `Enter` on a session to see its events. Press `Enter` on an event to see
its full content. Press `/` to filter the events by a substring match on the method. Press `q` to
quit.

RossoCortex reads this traffic. It does not change the traffic until you enable a plugin that changes
it.

## Step 3: read the numbers

Each session shows a token count and a cost. To learn what each number means, and how to act on it,
read [Read the numbers](reading-the-numbers.md).

## Manage the service

```bash
abctl service status
abctl service stop
abctl service start
```

## Stop and remove

To stop the traffic for one session, quit `abctl observe` with `q` and stop your agent. RossoCortex
continues to run as a background service.

To stop the service, and to remove it, read [Manage the service](#manage-the-service). The service
holds no traffic after a stop. It reads traffic again after you start it.

## Other agents

Any agent operates with RossoCortex. Configure the agent with two values:

- The proxy address: `localhost:47600`
- The certificate authority file: `~/.cortex/ca/ca.crt`

Most programs read the `HTTP_PROXY` and `HTTPS_PROXY` variables. For the certificate, a program reads
`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE`.

The Rossoctl CLI can set these variables for you, and remove them when the command ends:

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
```

See [Install the cluster CLI](cli.md).

## Next

- To understand the numbers that `abctl observe` shows, read [Read the numbers](reading-the-numbers.md).
- To reduce the token cost of your agent, read
  [Cost control](../concepts/experiments/cost-control.md).
- To make large tool output smaller, read
  [Context compaction](../concepts/experiments/context-compaction.md).
- To understand the program that you installed, read [RossoCortex](../concepts/core/cortex.md).
- To get deployment, discovery and the web console, read [Quickstart on Kubernetes](kubernetes.md).
