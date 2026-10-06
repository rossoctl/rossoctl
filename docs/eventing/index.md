---
title: Eventing
sidebar_label: Overview
description: How an event wakes an agent, and what the eventing path guarantees.
sidebar_position: 1
---

Eventing lets an agent run from a message instead of a held-open HTTP connection. A request
becomes a CloudEvent on a Kafka topic, an agent runner consumes it, and each step of the run
comes back as a further event. The caller never waits on a socket, and the agent does not need
to be running when the request arrives, if a runner picks it up within `ER_MAX_REQUEST_AGE_S`
(an hour by default). EventRunner drops an older request without a reply.

:::warning Alpha

This section covers the event path in
[`examples/eventing`](https://github.com/rossoctl/examples/tree/main/eventing), which exists to
pin down the wire contract for event-driven agents. These pages describe `eventing/` at
[`d9677ddd`](https://github.com/rossoctl/examples/tree/d9677ddd1611afd05fe51fcdc0dee0cd27809e62/eventing).

**Every identity control described here is off by default.** As the shipped manifests start,
requests are accepted anonymously, nothing is signed, and nothing is verified. See
[Turning the controls on](identity.md#turning-the-controls-on).

[The Phase 2 design record](https://github.com/rossoctl/examples/blob/d9677ddd1611afd05fe51fcdc0dee0cd27809e62/eventing/agentdocs/DESIGN_PHASE2.md),
a draft, has the reasoning behind the design. It predates several findings on these pages and does
not discuss some of these limits: where they disagree, these pages describe the code at that
revision.

:::

## The path

```text
HTTP ─▶ EventBridge ─▶ Kafka "requests" ─▶ EventRunner ─▶ Kafka "responses" ─▶ EventBridge ─▶ caller
         (front door)                       (runs the agent)                    (transcript, push)
```

| Component | Role |
| --- | --- |
| **EventBridge** | The HTTP front door. Mints a correlation id, publishes the request, serves the live transcript, and pushes notifications through [ntfy](https://ntfy.sh) when `NTFY_*` is configured. |
| **EventRunner** | Consumes requests, runs the agent, and emits each step as a response event. |
| **Kafka** | The log, and the scale-to-zero wake signal. The Strimzi topic CRs keep 24 hours; a local broker uses its own default. EventBridge's SQLite store holds the transcript, and on the base manifests it is an `emptyDir`, so replacing the pod discards the agents' answers. |

Two properties fall out of that shape:

- **Turns are ordered per conversation and parallel across conversations.** Work for one
  correlation id is serialised — the correlation id is the Kafka partition key — while separate
  conversations run concurrently.
- **Queue depth is the wake signal.** KEDA reads consumer-group lag to bring a runner from zero
  replicas to one, and lag returning to zero is what lets it scale back down. Scale-to-zero is
  Kubernetes-only.

## Identity

Neither an event nor EventBridge's own HTTP API passes through the controls that cover direct HTTP
calls, so this path needs its own. Two questions matter, and they have different answers:

| Question | Mechanism |
| --- | --- |
| Which person asked for this? | Sign-in at the front door, then the identity travels on the event |
| Which agent produced this? | A signature over requests and terminal responses, checked against approved keys |

[Identity in the event path](identity.md) covers both, including what each one does **not**
prove. [GitHub OAuth App](github-oauth-app.md) is the one-time setup that user sign-in needs.

## What this does not cover

Both controls are off by default, and each proves less than it first appears to — notably, only
*starting* work is authenticated, signing covers the final event of a run rather than the stream,
and anything that can write to the responses topic can end a batch. The broker connection is
plaintext and there is no rate limiting either.

[What these controls do not prove](identity.md#what-these-controls-do-not-prove) has each limit with
what it allows.
