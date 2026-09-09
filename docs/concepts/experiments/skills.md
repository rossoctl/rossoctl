---
title: Skills
description: Store reusable instructions in the cluster and give them to an agent.
sidebar_position: 2
---

A skill is a reusable capability that an agent can use. It contains instructions, scripts and
configuration. The cluster holds the skill, so you control and version it. You do not copy the
instructions into a prompt.

Rossoctl stores each skill as a Kubernetes ConfigMap with the label `rossoctl.io/type=skill`. A skill
can contain several files. The file `SKILL.md` is mandatory.

:::info Beta, and off by default
You must enable a feature flag before you can use skills. The skill registry, skillberry-store, is an
external project.
:::

## Enable skills

Two flags control the feature.

| Flag | What it controls |
| --- | --- |
| `featureFlags.skills` | Import, list and delete skills, and give a skill to an agent. |
| `featureFlags.externalSkills` | References to an external skill registry. Needs `skills` also. |

### During the installation

```bash
scripts/kind/setup-rossoctl.sh --with-skills
```

The `--with-skills` option sets both flags. It also enables the backend and the console, installs a
skillberry-store in the cluster, and enables synchronization with that store. Skills therefore operate
without an external registry and without extra configuration. The interface of the store is at
`http://skillberry-store.<domain>:8080`.

You can combine the option with any other option:

```bash
scripts/kind/setup-rossoctl.sh --with-skills --with-builds --skip-cluster
```

### On a cluster that already runs

```bash
helm upgrade rossoctl ./charts/rossoctl/ \
  -n rossoctl-system \
  --reuse-values \
  --set featureFlags.skills=true \
  --set featureFlags.externalSkills=true
```

This command restarts the backend and the console. Confirm that the backend registered the routes:

```bash
kubectl logs -n rossoctl-system -l app.kubernetes.io/name=rossoctl-backend \
  | grep "skills routes registered"
```

To install the store in the cluster also, add
`--set components.skillberryStore.enabled=true`. Omit that option if you use an external registry
only.

### Confirm the result

Open the console. A **Skills** entry appears in the navigation. It lists each skill with its category,
its description and its number of uses.

## Manage skills

The console is sufficient for common tasks. For other tasks, use the REST interface. Each request
needs a bearer token. Get a token with `rossoctl auth token`.

### List the skills

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills?namespace=rossoctl-system"
```

To search, add a `q` parameter:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills?namespace=rossoctl-system&q=code-review"
```

### Read one skill and its files

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills/rossoctl-system/code-review"
```

### Create a skill

```bash
curl -X POST "http://rossoctl-backend/api/skills" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "code-review",
    "namespace": "rossoctl-system",
    "description": "Automated code review skill",
    "category": "development",
    "files": {
      "SKILL.md": "# Code review\n\nHow to review a change...",
      "scripts/review.py": "..."
    }
  }'
```

The `files` object must contain `SKILL.md`.

### Delete a skill

```bash
curl -X DELETE "http://rossoctl-backend/api/skills/rossoctl-system/code-review" \
  -H "Authorization: Bearer $TOKEN"
```

## Permissions

| Role | Permitted actions |
| --- | --- |
| `ROLE_VIEWER` | Read a skill. |
| `ROLE_OPERATOR` | Create and delete a skill. |

## Give a skill to an agent

Add the `rossoctl.io/skills` annotation to the workload. The value is a JSON array of skill names:

```yaml
metadata:
  annotations:
    rossoctl.io/skills: '["code-review","order-lookup"]'
```

The console sets this annotation for you. When the `skillDiscovery` feature gate is on, the operator
resolves the names and writes them to the status of the `AgentRuntime` resource.

## The skillberry store

The store in the cluster manages its own set of skills. It has plugins that create, evaluate, improve,
deduplicate, scan and document a skill. A plugin runs when you add or change a skill. These plugins
belong to the store. An agent does not call them.

Most of the plugins call a model. Each plugin reads the model configuration from an environment
variable **on the store process at start-up**. The Helm chart sets only its own `SBS_*` variables.
Therefore the plugins that need a model stay inactive until you supply the configuration through
`skillberryStore.extraEnv`.

Put each API key in a Secret. Do not put a key in a values file:

```bash
kubectl create secret generic skillberry-store-secrets -n rossoctl-system \
  --from-literal=openai-api-key="<your-key>"
```

Then name the Secret in a values file:

```yaml
# skillberry-env.yaml
skillberryStore:
  extraEnv:
    - name: LLM_PROVIDER
      value: "openai"
    - name: LLM_MODEL
      value: "gpt-4o-mini"
    - name: OPENAI_API_KEY
      valueFrom:
        secretKeyRef:
          name: skillberry-store-secrets
          key: openai-api-key
```

Apply the file:

```bash
scripts/kind/setup-rossoctl.sh --with-skills --rossoctl-values ./skillberry-env.yaml
```

The names of the variables depend on the provider that you select. See the
[plugin documentation of skillberry-store](https://github.com/skillberry-ai/skillberry-store/blob/main/docs/plugins-installation.md).

Confirm which variables the container received:

```bash
kubectl set env deploy/skillberry-store -n rossoctl-system --list
```

## If the Skills entry does not appear

The feature flag is not set. Enable it without a new installation:

```bash
helm upgrade rossoctl charts/rossoctl -n rossoctl-system \
  --reuse-values --set featureFlags.skills=true
```

Then examine the log of the backend again for `skills routes registered`.
