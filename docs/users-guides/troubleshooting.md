---
sidebar_position: 1
description: What can go wrong?
---

# Troubleshooting

## Issues during Rossoctl installation

### Installation reports "exceeded its progress deadline"

Sometimes it can take a long time to pull container images. Try re-running the installer. Use `kubectl get deployments --all-namespaces` to identify failing deployments.

### Using Podman instead of Docker

The install script expects `docker` to be in your runtime path.

A few problem fixes might include:

- create `/usr/local/bin/docker` link to podman:

  ```console
   sudo ln -s /opt/podman/bin/podman /usr/local/bin/docker
   ```

- install `docker-credential-helper`:

   ```console
   brew install docker-credential-helper
   ```

- fix an issue with `insufficient memory to start keycloak`:

   ```console
   podman machine stop
   podman machine set --memory=12288 --cpus=8
   podman machine start
   ```

- clean, fresh Podman start:

   ```console
   podman machine rm -f
   podman machine init
   podman machine set --memory=12288 --cpus=8
   podman machine start
   ```

- clean the cluster, keep the Podman VM as is:

  ```console
  kind delete cluster --name agent-platform
  ```

### Blank UI page on macOS after installation

On macOS, if **Privacy and Content Restrictions** are enabled (under System Settings → Screen Time → Content & Privacy Restrictions), then after the Rossoctl installation completes, opening the UI may display a blank loading page.

To fix, disable these restrictions, then restart the UI deployment:

```shell
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

## Issues deploying components

### Pull Image errors while deploying components

If you see `Init:ErrImagePull` or `Init:ImagePullBackOff` errors while deploying components,
most likely your Github token expired. 

Error text:

```console
 failed to authorize: failed to fetch oauth token: unexpected status from GET request to https://ghcr.io/token?scope=repository%3Arossoctl%2Frossoctl-client-registration%3Apull&service=ghcr.io: 403 Forbidden
```

Check your [personal access token (classic)](https://github.com/settings/personal-access-tokens/).
Make sure to grant scopes `all:repo`, `write:packages`, and `read:packages`.

You may also get "ghcr.io: 403 Forbidden" errors installing Helm charts during Rossoctl installation. You may have cached credentials that are no longer valid. Clear them and log back in with your token:

```console
docker logout ghcr.io
docker login ghcr.io -u <your-github-username>
```

## Issues during runtime

### Service stops responding through gateway

It may happen with Keycloak or even the UI.

Restart the following:

```shell
kubectl rollout restart daemonset -n istio-system  ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
```

### Need to edit ENV values

If you need to update the values in `charts/rossoctl/.secrets.yaml` file, e.g., `githubToken`,
delete the secret in all your auto-created namespaces, then re-run the installer:

```shell
kubectl get secret --all-namespaces
kubectl -n my-namespace delete github-token-secret
scripts/kind/setup-rossoctl.sh
```

### Agent log shows communication errors

Rossoctl UI shows Connection errors:

```console
An unexpected error occurred during A2A chat streaming: HTTP Error 503: Network communication error: peer closed connection without sending complete message body (incomplete chunked read)
```

Agent log shows errors:

```console
rossoctl$ kubectl -n teams logs -f weather-service-7f984f478d-4jzv9
.
.
ERROR:    Exception in ASGI application
  + Exception Group Traceback (most recent call last):
  |   File "/app/.venv/lib/python3.11/site-packages/uvicorn/protocols/http/h11_impl.py", line 403, in run_asgi
  |     result = await app(  # type: ignore[func-returns-value]
  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  | ..
  +-+---------------- 1 ----------------
    | urllib3.exceptions.ProtocolError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
```

If your agent or tool is configured to use a local [Ollama](https://ollama.com/) model, this is most likely because the *ollama* service is not installed or running. If you're not using Ollama, this points to a different backend connectivity issue — check your agent's model provider configuration and logs instead.

Start *ollama* service in the terminal and keep it running:

```console
ollama serve
```

Then try the prompt again.

### Keycloak shows connection errors

Keycloak logs show [connection errors](https://github.com/rossoctl/rossoctl/issues/115) to Postgres, typically after the cluster has been running for an extended period (a day or more). The root cause isn't fully understood — see the linked issue for the investigation history.

At this time there is no reliable sequence of bringing down and up again
postgres and keycloak. The only reliable approach found so far is either to destroy and re-install
the cluster or delete and re-install keycloak as follows:

```shell
# Delete and re-apply keycloak resources
helm uninstall keycloak -n keycloak
scripts/kind/setup-rossoctl.sh

# Restart related services
kubectl rollout restart daemonset -n istio-system ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

Deployed agents may need to be restarted to update the Keycloak client.

```shell
kubectl rollout restart -n <agent-namespace> deployment <agent-deployment e.g. weather-service>
```

### Cert-Manager Webhook Errors

When running the rossoctl helm chart upgrade, you may encounter an error stating `failed calling webhook "webhook.cert-manager.io" because the x509 certificate has expired.` This occurs when the internal certificates used by cert-manager to communicate with the Kubernetes API server are no longer valid, preventing the validation of resources like Certificates and Issuers.

To resolve this, you must force cert-manager to regenerate its internal CA and certificates by following these steps:

Delete the expired webhook secret:

```shell
kubectl delete secret cert-manager-webhook-ca -n cert-manager
```

Restart the cert-manager deployments to trigger the issuance of new certificates:

```shell
kubectl rollout restart deployment cert-manager -n cert-manager
kubectl rollout restart deployment cert-manager-webhook -n cert-manager
kubectl rollout restart deployment cert-manager-cainjector -n cert-manager
```

Verify the pods are healthy before retrying your Helm command:

```shell
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=60s
```

Once the pods are back in a Running state with valid certificates, your `helm upgrade --install` 
command should complete successfully.

### SPIRE Daemonset Issues

If daemonsets show `Current=0` or `Ready=0`:

```bash
kubectl describe daemonsets -n zero-trust-workload-identity-manager spire-agent
kubectl describe daemonsets -n zero-trust-workload-identity-manager spire-spiffe-csi-driver
```

If you see SCC (Security Context Constraint) errors:

```bash
oc adm policy add-scc-to-user privileged -z spire-agent -n zero-trust-workload-identity-manager
kubectl rollout restart daemonsets -n zero-trust-workload-identity-manager spire-agent

oc adm policy add-scc-to-user privileged -z spire-spiffe-csi-driver -n zero-trust-workload-identity-manager
kubectl rollout restart daemonsets -n zero-trust-workload-identity-manager spire-spiffe-csi-driver
```

### OpenShift Upgrade (4.18 → 4.19)

<details>
<summary>Red Hat OpenShift Container Platform (AWS)</summary>

```bash
# Update channel
oc patch clusterversion version --type merge -p '{"spec":{"channel":"fast-4.19"}}'

# Acknowledge changes
oc -n openshift-config patch cm admin-acks --patch '{"data":{"ack-4.18-kube-1.32-api-removals-in-4.19":"true"}}' --type=merge
oc -n openshift-config patch cm admin-acks --patch '{"data":{"ack-4.18-boot-image-opt-out-in-4.19":"true"}}' --type=merge

# Upgrade
oc adm upgrade --to-latest=true --allow-not-recommended=true

# Monitor
oc get clusterversion
```

</details>

## 🔍 Troubleshooting & Validation

### Common Issues and Solutions

#### 1. SPIRE Agent Not Receiving SVID

**Symptoms:**

```bash
kubectl exec -n team deployment/slack-researcher --container authbridge-proxy -- ls /opt/
# Missing: svid.pem
```

**Diagnosis:**

```bash
# Check SPIRE agent logs
kubectl logs -n spire daemonset/spire-agent

# Check workload registration
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server entry show

# Verify node attestation
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server agent list
```

**Solutions:**

- Ensure agent namespace has correct labels: `shared-gateway-access=true`
- Verify SPIRE server can reach Kubernetes API
- Check workload selector configuration

#### 2. Token Exchange Failing

**Symptoms:**
```json
{
  "error": "invalid_client",
  "error_description": "Client authentication failed"
}
```

**Diagnosis:**

```bash
# Check client registration in Keycloak
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://keycloak.localtest.me:8080/admin/realms/rossoctl/clients" | \
  jq '.[] | select(.clientId | contains("spiffe"))'
```

**Solutions:**

- Verify client is registered with correct SPIFFE ID
- Ensure JWT SVID audience matches Keycloak expectations
- Check token exchange permissions in Keycloak client configuration

#### 3. MCP Gateway Authentication Issues

**Symptoms:**
```json
{
  "error": "authentication_failed",
  "message": "Invalid or missing authorization header"
}
```

**Diagnosis:**

```bash
# Check gateway logs
kubectl logs -n gateway-system deployment/mcp-gateway-controller

# Test direct tool access (bypassing gateway)
curl -H "Authorization: Bearer $TOKEN" \
  http://slack-tool.team.svc.cluster.local:8000/mcp

# Check HTTPRoute configuration
kubectl get httproute slack-tool-route -o yaml
```

**Solutions:**

- Verify HTTPRoute has correct authentication filters
- Ensure tool is properly registered with gateway
- Check token format and expiration

### Debugging Commands

#### SPIRE Debugging

```bash
# List all SPIRE entries
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server entry show

# Check SPIRE server health
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server healthcheck

# Validate specific workload SVID
SPIFFE_ID="spiffe://localtest.me/ns/team/sa/slack-researcher"
kubectl exec -n spire deployment/spire-server -- \
  /opt/spire/bin/spire-server entry show -spiffeID $SPIFFE_ID
```

#### Keycloak Debugging

```bash
# Get admin token
ADMIN_TOKEN=$(curl -sX POST \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" \
  "http://keycloak.localtest.me:8080/realms/rossoctl/protocol/openid-connect/token" | \
  jq -r .access_token)

# List all clients
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://keycloak.localtest.me:8080/admin/realms/rossoctl/clients" | jq .

# Check specific client configuration
CLIENT_ID="spiffe://localtest.me/ns/team/sa/slack-researcher"
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://keycloak.localtest.me:8080/admin/realms/rossoctl/clients?clientId=${CLIENT_ID}" | jq .

# Validate user token
USER_TOKEN="eyJ0eXAiOiJKV1Q..."
curl -H "Authorization: Bearer $USER_TOKEN" \
  "http://keycloak.localtest.me:8080/realms/rossoctl/protocol/openid-connect/userinfo"
```

#### Token Validation

```bash
# Decode JWT without verification (for debugging)
decode_jwt() {
  echo $1 | cut -d'.' -f2 | base64 -d | jq .
}

# Usage
TOKEN="eyJ0eXAiOiJKV1Q..."
decode_jwt $TOKEN

# Validate token expiration
check_token_expiry() {
  local token=$1
  local exp=$(echo $token | cut -d'.' -f2 | base64 -d | jq -r .exp)
  local now=$(date +%s)

  if [ $exp -gt $now ]; then
    echo "Token valid for $((exp - now)) seconds"
  else
    echo "Token expired $((now - exp)) seconds ago"
  fi
}

check_token_expiry $TOKEN
```
