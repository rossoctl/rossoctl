---
title: Install with Helm
description: Install from OCI charts or from the repository, without the setup scripts.
sidebar_position: 4
---

Use this when you are installing onto a cluster the setup scripts do not cover, or you need to control
each chart yourself.

:::info Beta
Chart-level installs work but are less exercised than the Kind and OpenShift scripts. Expect to do more
by hand.
:::

Rossoctl is three charts, installed in this order:

| Chart | Contains |
| --- | --- |
| `rossoctl-deps` | SPIRE, cert-manager, Keycloak, and the other dependencies |
| `mcp-gateway` | The MCP Gateway |
| `rossoctl` | The operator, webhook, backend, and console |

## Option A: from OCI charts

Find the latest release tag:

```bash
LATEST_TAG=$(git ls-remote --tags --sort="v:refname" \
  https://github.com/rossoctl/rossoctl.git \
  | tail -n1 | sed 's|.*refs/tags/v||; s/\^{}//')
```

Prepare secrets. Download
[`.secrets_template.yaml`](https://github.com/rossoctl/rossoctl/blob/main/charts/rossoctl/.secrets_template.yaml),
save it as `.secrets.yaml`, and fill in the required values.

Dependencies:

```bash
helm install rossoctl-deps \
  oci://ghcr.io/rossoctl/rossoctl/rossoctl-deps \
  --create-namespace -n rossoctl-system \
  --version "$LATEST_TAG" \
  --set spire.trustDomain="${DOMAIN}"
```

MCP Gateway:

```bash
LATEST_GATEWAY_TAG=$(skopeo list-tags docker://ghcr.io/rossoctl/charts/mcp-gateway | jq -r '.Tags[-1]')

helm install mcp-gateway oci://ghcr.io/rossoctl/charts/mcp-gateway \
  --create-namespace -n mcp-system \
  --version "$LATEST_GATEWAY_TAG"
```

Rossoctl:

```bash
helm upgrade --install rossoctl \
  oci://ghcr.io/rossoctl/rossoctl/rossoctl \
  --create-namespace -n rossoctl-system \
  --version "$LATEST_TAG" \
  -f .secrets.yaml \
  --set agentOAuthSecret.spiffePrefix="spiffe://${DOMAIN}/sa" \
  --set uiOAuthSecret.useServiceAccountCA=false \
  --set agentOAuthSecret.useServiceAccountCA=false
```

:::note The last three flags are an OpenShift CA workaround
`useServiceAccountCA=false` and the explicit `spiffePrefix` work around OpenShift's service-account CA
handling. Keep them on OpenShift. On other clusters, try without them first.
:::

## Option B: from the repository

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl

cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# edit .secrets.yaml

helm dependency update ./charts/rossoctl-deps/
helm dependency update ./charts/rossoctl/
```

```bash
helm install rossoctl-deps ./charts/rossoctl-deps/ \
  -n rossoctl-system --create-namespace \
  --set spire.trustDomain="${DOMAIN}" --wait

helm install mcp-gateway oci://ghcr.io/rossoctl/charts/mcp-gateway \
  --create-namespace -n mcp-system --version 0.4.0

LATEST_TAG=$(git ls-remote --tags --sort="v:refname" \
  https://github.com/rossoctl/rossoctl.git | tail -n1 | sed 's|.*refs/tags/||; s/\^{}//')

helm upgrade --install rossoctl ./charts/rossoctl/ \
  -n rossoctl-system --create-namespace \
  -f ./charts/rossoctl/.secrets.yaml \
  --set ui.tag="${LATEST_TAG}" \
  --set agentOAuthSecret.spiffePrefix="spiffe://${DOMAIN}/sa" \
  --set uiOAuthSecret.useServiceAccountCA=false \
  --set agentOAuthSecret.useServiceAccountCA=false
```

## Feature flags

Set them at install, or afterwards with `--reuse-values`:

```bash
helm upgrade rossoctl ./charts/rossoctl/ \
  -n rossoctl-system --reuse-values \
  --set featureFlags.skills=true \
  --set featureFlags.externalSkills=true
```

See [Skills](../workloads/skills.md) and [Agent context](../workloads/agent-context.md) for what each enables.

## Verify

```bash
kubectl get deployments -n rossoctl-system
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

## Related

- [Install options](../reference/install-options.md).
- [Troubleshooting](troubleshooting.md).
