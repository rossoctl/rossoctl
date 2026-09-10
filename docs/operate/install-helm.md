---
title: Install with Helm
description: Install from OCI charts or from the repository, without the scripts.
sidebar_position: 4
---

Use this method for a cluster that the scripts do not support, or when you must control each chart.

:::info Beta
An installation from the charts operates. The project tests it less than it tests the Kind script and the
OpenShift script. Expect more manual steps.
:::

Rossoctl has three charts. Install them in this order.

| Chart | Contents |
| --- | --- |
| `rossoctl-deps` | SPIRE, cert-manager, Keycloak and the other dependencies |
| `mcp-gateway` | The MCP Gateway |
| `rossoctl` | The operator, the webhook, the backend and the console |

## Method A: from the OCI charts

Get the most recent release tag:

```bash
LATEST_TAG=$(git ls-remote --tags --sort="v:refname" \
  https://github.com/rossoctl/rossoctl.git \
  | tail -n1 | sed 's|.*refs/tags/v||; s/\^{}//')
```

Prepare the secrets. Get
[`.secrets_template.yaml`](https://github.com/rossoctl/rossoctl/blob/main/charts/rossoctl/.secrets_template.yaml),
save it as `.secrets.yaml`, and add your values.

Install the dependencies:

```bash
helm install rossoctl-deps \
  oci://ghcr.io/rossoctl/rossoctl/rossoctl-deps \
  --create-namespace -n rossoctl-system \
  --version "$LATEST_TAG" \
  --set spire.trustDomain="${DOMAIN}"
```

Install the MCP Gateway:

```bash
LATEST_GATEWAY_TAG=$(skopeo list-tags docker://ghcr.io/rossoctl/charts/mcp-gateway | jq -r '.Tags[-1]')

helm install mcp-gateway oci://ghcr.io/rossoctl/charts/mcp-gateway \
  --create-namespace -n mcp-system \
  --version "$LATEST_GATEWAY_TAG"
```

Install Rossoctl:

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

:::note The last three settings are for OpenShift
The `useServiceAccountCA=false` settings and the explicit `spiffePrefix` value correct the certificate
authority behaviour of OpenShift. Keep them on OpenShift. On a different cluster, try the command without
them first.
:::

## Method B: from the repository

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl

cp charts/rossoctl/.secrets_template.yaml charts/rossoctl/.secrets.yaml
# Add your values to .secrets.yaml

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

## The feature flags

Set a flag during the installation, or later with the `--reuse-values` option:

```bash
helm upgrade rossoctl ./charts/rossoctl/ \
  -n rossoctl-system --reuse-values \
  --set featureFlags.skills=true \
  --set featureFlags.externalSkills=true
```

For the function of each flag, see [Skills](../concepts/experiments/skills.md) and
[Agent context](../concepts/experiments/agent-context.md).

## Confirm the installation

```bash
kubectl get deployments -n rossoctl-system
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

## Related pages

- [Install options](../reference/install-options.md)
- [Troubleshooting](troubleshooting.md)
