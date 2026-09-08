---
title: Skills
description: Store reusable capabilities in the cluster and link them to agents.
sidebar_position: 6
---

A skill is a reusable capability an agent can draw on — instructions, scripts, and configuration held
in the cluster, versioned and governed, rather than pasted into a prompt.

Skills are stored as Kubernetes ConfigMaps labelled `rossoctl.io/type=skill` and managed through the
platform API. A skill can contain several files; `SKILL.md` is mandatory.

:::info Beta — behind a feature flag
Skills are off by default. Enable them at install time or with a Helm upgrade, as below.
:::

## Enable skills

Two flags control the feature:

| Flag | Controls |
| --- | --- |
| `featureFlags.skills` | Import, list, delete skills, and link them to agents. |
| `featureFlags.externalSkills` | External skill registry references. Requires `skills` too. |

### At install time

```bash
scripts/kind/setup-rossoctl.sh --with-skills
```

`--with-skills` sets both flags, enables the backend and console, deploys an in-cluster
**skillberry-store**, and turns on autosync against it — so skills work with no external registry and
no allowed-hosts configuration. The store's own interface is at
`http://skillberry-store.<domain>:8080`.

Combine it with anything else:

```bash
scripts/kind/setup-rossoctl.sh --with-skills --with-builds --skip-cluster
```

### On a running cluster

```bash
helm upgrade rossoctl ./charts/rossoctl/ \
  -n rossoctl-system \
  --reuse-values \
  --set featureFlags.skills=true \
  --set featureFlags.externalSkills=true
```

This rolls the backend and console pods. Confirm the routes registered:

```bash
kubectl logs -n rossoctl-system -l app.kubernetes.io/name=rossoctl-backend \
  | grep "skills routes registered"
```

Add `--set components.skillberryStore.enabled=true` to deploy the in-cluster store as well. Omit it if
you only use an external registry.

### Confirm it worked

Open the console. A **Skills** entry appears in the navigation, listing each skill with its category,
description, and usage count.

## Manage skills

The console handles the common cases. The API covers the rest — all endpoints need a bearer token.
Get one with `rossoctl auth token`.

### List

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills?namespace=rossoctl-system"

# Search
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills?namespace=rossoctl-system&q=code-review"
```

### Get one, with its files

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://rossoctl-backend/api/skills/rossoctl-system/code-review"
```

### Create

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

`SKILL.md` must be present.

### Delete

```bash
curl -X DELETE "http://rossoctl-backend/api/skills/rossoctl-system/code-review" \
  -H "Authorization: Bearer $TOKEN"
```

## Permissions

| Role | Can |
| --- | --- |
| `ROLE_VIEWER` | Read skills. |
| `ROLE_OPERATOR` | Create and delete skills. |

## Link skills to an agent

Set the `rossoctl.io/skills` annotation on the workload to a JSON array of skill names:

```yaml
metadata:
  annotations:
    rossoctl.io/skills: '["code-review","order-lookup"]'
```

The console sets this for you. When the `skillDiscovery` feature gate is on, the operator resolves the
annotation into `status.linkedSkills` on the `AgentRuntime`.

## The skillberry store

The in-cluster store curates its own skill repository: plugins that create, evaluate, optimise,
deduplicate, security-scan, and document skills, running when a skill is added or updated. These are
the store's capabilities, not something agents call at runtime.

Most of them call a model, and read that configuration from environment variables **on the store
process at startup**. The chart only sets its own `SBS_*` variables, so LLM-backed plugins stay off
until you inject configuration through `skillberryStore.extraEnv`.

Put the API keys in a Secret, not in a values file:

```bash
kubectl create secret generic skillberry-store-secrets -n rossoctl-system \
  --from-literal=openai-api-key="<your-key>"
```

Then reference it:

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

Apply it:

```bash
scripts/kind/setup-rossoctl.sh --with-skills --rossoctl-values ./skillberry-env.yaml
```

Variable names depend on the provider you choose. See the
[skillberry-store plugin documentation](https://github.com/skillberry-ai/skillberry-store/blob/main/docs/plugins-installation.md).

Confirm what landed:

```bash
kubectl set env deploy/skillberry-store -n rossoctl-system --list
```

## If Skills does not appear

The feature flag was not set. Enable it without a full redeploy:

```bash
helm upgrade rossoctl charts/rossoctl -n rossoctl-system \
  --reuse-values \
  --set featureFlags.skills=true
```

Then re-check the backend log for `skills routes registered`.
