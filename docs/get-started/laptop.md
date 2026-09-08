---
title: "Quickstart: your laptop"
sidebar_label: Quickstart — laptop
description: Run Cortex as a single binary and watch what your coding agent sends.
sidebar_position: 2
---

Cortex is the Rossoctl data plane. It runs as one binary on macOS or Linux, sits in your agent's
request path, and shows you the model calls, tool calls, and agent-to-agent messages as they
happen. No Kubernetes.

This takes about five minutes.

## What you need

- macOS or Linux, amd64 or arm64.
- A coding agent. The installer sets up [Claude Code](https://claude.com/claude-code) for you;
  any agent works, see [Other agents](#other-agents).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/rossoctl/cortex/main/authbridge/install.sh \
  | sh -s -- --claude-code
```

The script asks before it changes your Claude Code settings, then runs Cortex as a background
service that survives crashes and logins.

:::note
The URL points at `main`, but the script re-runs the copy from the newest release, so
`curl | sh` does not execute unreleased code. Pass `--ref` to override that.
:::

## Watch the traffic

Open two terminals.

```bash
abctl
```

```bash
claude
```

Use Claude as usual — there are no environment variables to set. Its calls stream into `abctl`.

Cortex only reads this traffic. Nothing is rewritten unless you turn on a plugin that does so.

## Manage the service

```bash
abctl service status
abctl service stop
abctl service start
```

## Other agents

Any agent works. Point it at the proxy and trust the local CA:

- Proxy: `localhost:47600`
- CA certificate: `~/.cortex/ca/ca.crt`

Most tools read `HTTP_PROXY` and `HTTPS_PROXY`, plus one of `NODE_EXTRA_CA_CERTS`,
`REQUESTS_CA_BUNDLE`, or `SSL_CERT_FILE` for the CA.

If you would rather not set those yourself, the Rossoctl CLI does it for you and cleans up on exit:

```bash
rossoctl authbridge exec --config ./authbridge.yaml -- claude "explain this repo"
```

See [Install the CLI](cli.md).

## Next

- [Reduce token cost](../guardrails/token-cost.md) — strip tool definitions your agent never calls,
  and cap spend per session.
- [Context compaction](../guardrails/context-compaction.md) — shrink large tool output before it
  reaches the model.
- [RossoCortex](../concepts/cortex.md) — how the pipeline you just installed works.
- [Quickstart: Kubernetes](kubernetes.md) — when you want deployment, discovery, and the UI.
