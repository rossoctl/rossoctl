---
title: Tool call validation
description: Deny a tool call that has invented arguments.
sidebar_position: 6
---

This feature checks that a proposed tool call is correct before the call runs. It compares the call
with the conversation and with the specification of the tool. It detects an invented argument and an
incorrect choice of tool. The name of the plugin is `sparc`.

:::warning Alpha
This feature is an experiment. The configuration will change.
:::

## The problem that it solves

A model can produce a value that looks correct but does not exist. You can ask an agent about a transaction and give no identifier. The model then often produces an
identifier that has the correct form and no meaning. A model can also call a tool that transfers money when you asked for a
report.

These calls are not attacks, and their form is correct. The type of each argument is correct, and the
authentication is correct. The controls in [Security](../../security/index.md) have no reason to stop
them.

The plugin checks two conditions:

- **The source of each argument.** Each argument must come from the conversation or from the
  specification of the tool.
- **The choice of tool.** The tool must match the request.

## What happens after a denial

The tool call does not run. The plugin returns its explanation to the agent. The agent can then ask the
user for the value that is absent.

This result is the useful part. A denied call becomes a question instead of an error.

## How it operates

The plugin runs on the outbound chain. It needs the MCP parser and the inference parser before it in
the chain.

The logic is the `SPARCReflectionComponent` from the
[agent-lifecycle-toolkit](https://pypi.org/project/agent-lifecycle-toolkit/), which is a Python
package. The RossoCortex plugins use Go. The plugin therefore calls a separate service over HTTP. This
arrangement is the same arrangement that
[intent-based access](intent-based-access.md) uses for its model.

All of the policy is in the plugin. The service returns a result only.

You must therefore install two parts: the plugin, which you enable in the chain, and the service that
the plugin calls.

## Configuration

The
[plugin catalogue](https://github.com/rossoctl/cortex/blob/main/authbridge/docs/plugin-catalog.md#sparc)
lists each setting. Decide the behaviour for a failure before you enable the plugin. If the service is
not reachable, you must choose between a denial of correct work and a permission for an incorrect tool
call.

## How this feature and intent-based access differ

The two features answer different questions. Use them together.

| Feature | Question | Denies when |
| --- | --- | --- |
| **Tool call validation** | Does each argument have a source? | The model invented a value, or selected the wrong tool. |
| **Intent-based access** | Does this action match the request of the user? | Something changed the purpose of the agent. |

An invented transaction identifier is a validation problem. The agent is on task, and the value has no
source. A request that sends data to an external server is an intent problem. The form of the request
can be correct, and no user asked for it.

## Try it

The [tool validation demonstration](https://github.com/rossoctl/cortex/blob/main/authbridge/demos/finance-sparc)
uses a finance agent and a transaction that has no source.
