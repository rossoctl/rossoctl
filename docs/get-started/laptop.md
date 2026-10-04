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

<!-- This install command is duplicated in the Cortex repository README:
     rossoctl/cortex -> README.md ("Quick start").
     Change both, or they drift - the --ref wording already did once. -->

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/cortex/main/scripts/install.sh \
  | sh -s -- --claude-code
```

The script asks for your permission before it changes the settings of Claude Code. It then runs
RossoCortex as a background service. The service restarts after a failure and after you sign in again.

:::note
The address of the script is on the `main` branch, but the script then runs the copy from the most
recent release, so the command does not run unreleased code. To pin or override that, use `--ref`:
`--ref=vX.Y.Z` selects a release and `--ref=main` installs the unreleased tip. See
[Installing an unreleased build](https://github.com/rossoctl/cortex/blob/main/CONTRIBUTING.md#installing-an-unreleased-build).
:::

If the install fails, read [Troubleshooting](../operate/troubleshooting.md#on-a-laptop) first. It
covers a certificate that your agent does not trust, a port that another program holds, and a service
that does not start. If your condition is not there, go to [Give feedback](#give-feedback) — a pasted
error is exactly what the form asks for.

## Step 2: watch the traffic

Open two terminals. In the first terminal, run the viewer:

```bash
agentop observe
```

In the second terminal, run your agent:

```bash
claude
```

Use Claude Code in the normal way. There is no environment variable to set. The calls of the agent
appear in `agentop`.

In `agentop observe`, press `Enter` on a session to see its events. Press `Enter` on an event to see
its full content. Press `/` to filter the events by a text match. Press `q` to quit. To learn what
the filter matches, read [Read the numbers](reading-the-numbers.md#watch-a-session).

RossoCortex reads this traffic. It does not change the traffic until you enable a plugin that changes
it.

## Step 3: read the numbers

Each session shows a token count and a cost. To learn what each number means, and how to act on it,
read [Read the numbers](reading-the-numbers.md).

## Manage the service

```bash
agentop service status
agentop service stop
agentop service start
agentop service restart
agentop service uninstall
```

`agentop service` controls the supervisor of your operating system, which is `launchd` on macOS and
`systemd` on Linux. A stop persists across a login, and a start undoes it. An uninstall removes the
service and keeps your data: your configuration and your certificate authority stay in `~/.cortex`.
To set the service up again after an uninstall, run `agentop service install`.

To read what each command does to the supervisor, and to stop the service so that you can run your
own Cortex process, read
[You must stop the service to run Cortex yourself](../operate/troubleshooting.md#you-must-stop-the-service-to-run-cortex-yourself).

## Stop and remove

To stop the traffic for one session, quit `agentop observe` with `q` and stop your agent. RossoCortex
continues to run as a background service.

To stop the service, run `agentop service stop`. To remove it, run `agentop service uninstall`. Both
are in [Manage the service](#manage-the-service). The service holds no traffic after a stop. It
reads traffic again after you start it.

## Other agents

Any agent operates with RossoCortex. For the agents below, `agentop configure` does the work for you
— it reads the proxy address from your own config, so the value always matches the service that is
running:

| Agent | Command | What it changes |
| --- | --- | --- |
| Claude Code | `agentop configure claude-code enable` | The proxy and CA variables in `~/.claude/settings.json`. |
| IBM Bob | `agentop configure bob enable` | The `http.proxy` key in Bob's `settings.json`, for the editor. |
| `bob` shell | `agentop configure bobshell enable` | A `bob` shell function in your rc file. Independent of the row above. |
| OpenCode | `agentop configure opencode enable` | The proxy and CA variables for OpenCode's background service, which carries all of its traffic. |
| Codex | `agentop exec -- codex` | Nothing persistent yet — run it through `agentop exec`. |

Each one takes `disable` to undo it and `status` to report what is set. Run
`agentop configure <agent> --help` for the detail.

For an agent that is not listed, configure it with two values:

- The proxy address: `localhost:47600`
- The certificate authority file: `~/.cortex/ca/ca.crt`

Most programs read the `HTTP_PROXY` and `HTTPS_PROXY` variables. For the certificate, a program reads
`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE`.

:::note[`SSL_CERT_FILE` does nothing on macOS]
Go reads the system keychain on macOS and ignores `SSL_CERT_FILE`. Use `NODE_EXTRA_CA_CERTS` for Node
programs, and add the CA to the keychain for anything else. See
[Troubleshooting](../operate/troubleshooting.md#on-a-laptop).
:::

The Rossoctl CLI can set these variables for you, and remove them when the command ends:

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
```

See [Install the cluster CLI](cli.md).

## Next

- To understand the numbers that `agentop observe` shows, read [Read the numbers](reading-the-numbers.md).
- To reduce the token cost of your agent, read
  [Cost control](../concepts/experiments/cost-control.md).
- To make large tool output smaller, read
  [Context compaction](../concepts/experiments/context-compaction.md).
- To understand the program that you installed, read [RossoCortex](../concepts/core/cortex.md).
- To get deployment, discovery and the web console, read [Quickstart on Kubernetes](kubernetes.md).

## Give feedback

:::info[Tell us when it breaks]

Cortex on a laptop is new. Report an install that failed, a figure that looked wrong, or a step that
was not clear.

Read [Troubleshooting](../operate/troubleshooting.md#on-a-laptop) first. It covers the most frequent
conditions, and it answers a set of figures that look wrong and are correct.

- Open the **Laptop feedback** form on
  [rossoctl/cortex](https://github.com/rossoctl/cortex/issues/new/choose)
- Or write a message in [Slack](https://ibm.biz/rossoctl-slack)

A half-finished install, with the error in the report, is more useful than a complete report that you
do not send.

:::
