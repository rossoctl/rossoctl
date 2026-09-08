---
title: Troubleshooting
description: Failures people actually hit, and how to recover.
sidebar_position: 6
---

Grouped by when it happens. If you cannot find your problem, ask in
[Slack](https://ibm.biz/rossoctl-slack) or open an issue on
[rossoctl/rossoctl](https://github.com/rossoctl/rossoctl/issues).

## During installation

### "exceeded its progress deadline"

Usually a slow image pull rather than a real failure. Find what is stuck and re-run the installer:

```bash
kubectl get deployments --all-namespaces
```

Use `--preload-images` on the next run to side-load third-party images and avoid Docker Hub rate limits.

### Podman instead of Docker

The installer expects `docker` on your path.

```bash
sudo ln -s /opt/podman/bin/podman /usr/local/bin/docker
brew install docker-credential-helper
```

If Keycloak reports insufficient memory, give the machine more:

```bash
podman machine stop
podman machine set --memory=12288 --cpus=8
podman machine start
```

For a clean start:

```bash
podman machine rm -f
podman machine init --rootful --memory 18432 --cpus 6
podman machine start
```

To reset the cluster but keep the Podman VM:

```bash
kind delete cluster --name rossoctl
```

### Build pods stay `Pending` with `Insufficient cpu`

Not enough CPU on the node. Platform pods alone can request close to 4 cores.

Either give the runtime 6 CPUs and recreate the cluster, or deploy agents from prebuilt images instead
of building from source. See [sizing](index.md#sizing).

### Blank console page on macOS

If **Content & Privacy Restrictions** are on — System Settings → Screen Time → Content & Privacy
Restrictions — the console can load as a blank page.

Turn them off, then restart the console:

```bash
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

### SPIRE DaemonSets show 0 ready

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

Nothing that depends on workload identity will work until these are ready. Check the pods for scheduling
failures or image pull errors, and confirm the node has capacity.

## Deploying agents and tools

### `Init:ErrImagePull` or `Init:ImagePullBackOff`

Almost always an expired GitHub token:

```
failed to authorize: failed to fetch oauth token: unexpected status from GET request to
https://ghcr.io/token?scope=repository%3Arossoctl%2F...: 403 Forbidden
```

Check your [personal access token](https://github.com/settings/personal-access-tokens/). It needs
`repo`, `write:packages`, and `read:packages`.

A 403 from `ghcr.io` while installing Helm charts is usually stale cached credentials:

```bash
docker logout ghcr.io
docker login ghcr.io -u <your-github-username>
```

### Changing a value in `.secrets.yaml`

The installer copies secrets into namespaces, so editing the file is not enough. Delete the derived
Secret everywhere it landed, then re-run the installer:

```bash
kubectl get secret --all-namespaces
kubectl -n team1 delete secret github-token-secret
scripts/kind/setup-rossoctl.sh
```

## At runtime

### Agent chat fails with a 503

The console shows:

```
An unexpected error occurred during A2A chat streaming: HTTP Error 503:
Network communication error: peer closed connection without sending complete message body
```

and the agent log shows a `ConnectionResetError` or a `ProtocolError`.

The agent cannot reach its model. If it is configured for Ollama, `ollama serve` is almost certainly not
running:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

If you are not using Ollama, check the agent's model configuration:

```bash
kubectl exec -n team1 <agent-pod> -- env | grep LLM_
```

### A service stops responding through the gateway

Happens to Keycloak and the console. Restart the data plane:

```bash
kubectl rollout restart daemonset -n istio-system ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
```

### Mesh-wide 503 after host suspend

**Symptom.** Every `*.localtest.me:8080` route returns `503` with `upstream connect error ... connection
termination`, while all pods are `Running`, the gateway is `1/1`, and `HTTPRoute` and `Gateway` report
`Accepted`.

**Cause.** You suspended the host for longer than the SPIRE credential lifetime. The Istio ambient data
plane — ztunnel and waypoints — keeps serving expired mTLS certificates and never re-fetches.

**Diagnose:**

```bash
kubectl logs -n istio-system -l app=ztunnel --tail=100 \
  | grep -iE "certificate expired|CertificateExpired"

kubectl logs -n spire-system -l app.kubernetes.io/name=agent --tail=100 \
  | grep -iE "reattest|service account token has expired"
```

**Recover:**

```bash
scripts/k8s/mesh-recover.sh --fix
```

Without `--fix` the script detects and prints the commands without acting.

**Catch it earlier.** Run the script in detect mode periodically — it exits `4` when the
soonest-expiring ztunnel SVID is within `CERT_WARN_SECONDS` (default 6 hours) of expiry. This needs
`kubectl` exec access and `jq`. On Kind you can also enable the `meshSelfHeal` feature flag, which
installs a CronJob to do the restart automatically.

**Expect this on dev clusters.** Suspending longer than the SVID lifetime requires a data-plane restart
or a cluster recreate. The root cause is upstream:
[istio/ztunnel#1679](https://github.com/istio/ztunnel/issues/1679).

### Keycloak connection errors to Postgres

Appears after the cluster has run for a day or more. The root cause is not fully understood — see
[rossoctl#115](https://github.com/rossoctl/rossoctl/issues/115) for the investigation.

There is no reliable way to restart Postgres and Keycloak in place. The only dependable fix is to
reinstall Keycloak:

```bash
helm uninstall keycloak -n keycloak
scripts/kind/setup-rossoctl.sh

kubectl rollout restart daemonset -n istio-system ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

Deployed agents may need restarting afterwards to pick up their Keycloak client again.

### The operator cannot authenticate to Keycloak after a credential rotation

The operator caches admin credentials. Restart it:

```bash
kubectl rollout restart deployment/rossoctl-controller-manager -n rossoctl-system
```

Confirm:

```bash
POD=$(kubectl get pod -n rossoctl-system -l control-plane=controller-manager \
  -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n rossoctl-system "$POD" -c manager | grep -i "keycloak\|auth" | tail -5
```

### SPIFFE authentication fails with an audience or issuer mismatch

The JWT SVID's `aud` must exactly equal `keycloak.publicUrl/realms/<realm>`, and it must be the
**external** URL — Keycloak's issuer is configured with the public URL and the check is a string
comparison. An in-cluster service address reaches the same server and still fails.

Check `keycloak.publicUrl` in your Helm values. See
[Authentication modes](../security/authentication-modes.md#the-audience-must-be-the-public-url).

### Skills do not appear in the console

The feature flag is not set. Enable it without redeploying:

```bash
helm upgrade rossoctl charts/rossoctl -n rossoctl-system \
  --reuse-values --set featureFlags.skills=true
```

Then confirm the backend registered its routes:

```bash
kubectl logs -n rossoctl-system -l app.kubernetes.io/name=rossoctl-backend \
  | grep "skills routes registered"
```

## Useful commands

```bash
# What is broken, everywhere
kubectl get pods --all-namespaces | grep -vE "Running|Completed"

# All service URLs and credentials
./.github/scripts/local-setup/show-services.sh

# A specific agent's Cortex configuration
rossoctl agents authbridge get <agent>

# An agent's environment, as the pod actually sees it
kubectl exec -n <namespace> <pod> -- env | sort

# Cortex sidecar logs
kubectl logs -n <namespace> <pod> -c authbridge-proxy

# Operator logs
kubectl logs -n rossoctl-system -l control-plane=controller-manager -c manager --tail=100
```
