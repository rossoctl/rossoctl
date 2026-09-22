---
title: HITL authorization demo
description: Run the human-in-the-loop OAuth2 flow, where an agent obtains user-scoped permissions at runtime through the token broker.
sidebar_position: 7
---

Most agent requests carry the permissions the user already granted at login. Human-in-the-loop
(HITL) authorization covers the other case: the agent needs access to a resource the user has
not yet consented to, so it asks — mid-request — and waits.

This page shows how to run that flow end to end on a Kind cluster.

## How it works

The agent makes one ordinary MCP call. Everything else happens inside that call:

```
 agent  ──►  cortex sidecar  ──►  token broker  ──►  OAuth provider (GitHub)
   │          (token-broker         │                      │
   │           plugin)              │               user consents
   │                                ▼                  in browser
   │                         resource server
   ▼                          (MCP server)
 response
```

1. The agent calls the MCP server. It does not know a broker exists.
2. The sidecar matches the target host against a `broker` route and asks the token broker for a
   token.
3. No token is cached, so the broker discovers the resource server's OAuth provider from
   `GET /.well-known/oauth-protected-resource` ([RFC 9728][rfc9728]).
4. The broker publishes an `oauth_url_ready` event. The UI opens the provider's consent page.
5. The user consents. The provider redirects to the broker's callback, which exchanges the code
   for an access token and caches it per `(session, resource)`.
6. The sidecar attaches the token and completes the original call. The agent gets its response.

The agent is involved only at steps 1 and 6. Repeat calls are served from the cache with no
further consent.

[rfc9728]: https://datatracker.ietf.org/doc/html/rfc9728

## Prerequisites

### 1. A platform install

```bash
scripts/kind/setup-rossoctl.sh --with-ui --with-spire --with-agent-sandbox --with-builds --preload-images
```

Budget about 12–16 GB of memory and 4 vCPUs. `--with-all` is not needed for this demo.

### 2. A GitHub OAuth app

Create one at [github.com/settings/developers](https://github.com/settings/developers) →
**OAuth Apps** → **New OAuth App**:

| Field | Value for a Kind cluster |
| --- | --- |
| Application name | anything, for example `rossoctl-hitl-dev` |
| Homepage URL | `http://rossoctl-ui.localtest.me:8080` |
| Authorization callback URL | `http://token-broker.localtest.me:8080/oauth/callback` |

The callback URL must equal `tokenBroker.oauth.callbackUrl` in the operator chart exactly, or
GitHub rejects the redirect. Generate a client secret — GitHub shows it once.

Store it in the release namespace. The chart never templates credentials, so they stay out of
values and Helm release state:

```bash
kubectl create secret generic github-oauth-credentials -n rossoctl-system \
  --from-literal=client-id=<CLIENT_ID> \
  --from-literal=client-secret=<CLIENT_SECRET>
```

### 3. The token broker

It ships inside the operator image and is off by default:

```bash
helm upgrade rossoctl charts/rossoctl -n rossoctl-system --reuse-values \
  --set operator-chart.tokenBroker.enabled=true
```

Expect `token-broker` to reach `1/1 Running` in `rossoctl-system`. A pod stuck in
`CreateContainerConfigError` means the secret above is missing.

### 4. An OAuth-protected resource server

This is the step most easily missed. The broker cannot mint a token without a resource server
to run discovery against, and the demo server is not part of this repository — it is a fork of
GitHub's MCP server that adds the OAuth endpoints and Kubernetes manifests.

```bash
# In your checkout of the MCP server fork
docker build -f k8s/kind-demo/Dockerfile.mcp-server -t localhost/kagenti/mcp-server:demo .
kind load docker-image localhost/kagenti/mcp-server:demo --name rossoctl

kubectl create namespace rossoctl-demo
kubectl create secret generic github-oauth-credentials -n rossoctl-demo \
  --from-literal=client-id=<CLIENT_ID> --from-literal=client-secret=<CLIENT_SECRET>

# The manifest predates the rename and still says namespace: kagenti-demo.
sed 's/namespace: kagenti-demo/namespace: rossoctl-demo/' k8s/kind-demo/02-mcp-server.yaml \
  | kubectl apply -f -
```

Do **not** run that repository's `k8s/kind-demo/build-and-deploy.sh`. It also deploys its own
token broker and backend into pre-rename namespaces, which collides with the broker the
operator chart installs.

Check discovery works:

```bash
kubectl exec -n rossoctl-system deploy/app-demo-backend -- python3 -c "
import urllib.request
print(urllib.request.urlopen(
  'http://mcp-server-service.rossoctl-demo.svc.cluster.local:8184/.well-known/oauth-protected-resource',
  timeout=8).status)"
```

## Switch the outbound chain to the token broker

`token-exchange` and `token-broker` both claim the `Authorization` header, so they are mutually
exclusive on the outbound chain. Swapping them means editing `authBridge.pipeline`, upgrading
the release without letting Helm undo the change, and restarting every injected workload. Use
the script rather than doing it by hand:

```bash
scripts/migrate-to-token-broker.sh          # switch to token-broker
scripts/migrate-to-token-broker.sh --revert # switch back
```

It checks the prerequisites, reads the pipeline the release is actually running, and exits
without changes if the target plugin is already active. It never writes to the chart.

Confirm the result:

```bash
kubectl get cm authbridge-runtime-config -n team1 -o yaml | grep -A6 'name: token-broker'
```

### Why the chart value, and not `pluginPreset`

`AgentRuntime.spec.pluginPreset` with `plugins: ["token-exchange:off", "token-broker:enforce"]`
looks like the natural way to do this, and admission accepts it — but the sidecar then
crash-loops:

```
initial pipeline build: outbound: configure "token-broker": token-broker config: broker_url is required
```

The operator seeds each plugin's config from a base pipeline that only covers `jwt-validation`
and `token-exchange`, so `token-broker` renders with no config at all. Editing the per-agent
`authbridge-config-<name>` ConfigMap does not help either: the admission webhook regenerates it
on every pod creation.

So `authBridge.pipeline` is the durable path today.

### Route rules

The plugin brokers only for hosts matching a `broker` route; everything else passes through
untouched. The script writes an inline rule for the MCP server. You can also mount rules from a
ConfigMap named `authproxy-routes` (key `routes.yaml`, mounted at `/etc/authproxy/routes.yaml`):

```yaml
- host: "mcp-server-service.rossoctl-demo.svc.cluster.local"
  action: "broker"
```

File routes are evaluated before inline rules, the first match wins, and the port is stripped
before matching.

### Point an agent at the resource server

The agent's `MCP_URL` lives on the Sandbox, not the AgentRuntime:

```bash
kubectl get sandbox <agent> -n team1 -o json \
  | jq '.spec.podTemplate.spec.containers[0].env[] | select(.name=="MCP_URL")'
```

Set it to the in-cluster address:

```
http://mcp-server-service.rossoctl-demo.svc.cluster.local:8184/mcp
```

Use `http`, not `https`. Cortex passes TLS through untouched, so the plugin cannot insert a
token into an encrypted stream — pointing an agent at a hosted HTTPS MCP endpoint skips the
broker entirely.

## Run the demo

Deploy the example app and grant a user access:

```bash
cd rossoctl/examples/app-demo
DOCKER_BUILD_FLAGS=--load make all   # --load is required with podman
make grant-agent-access
```

Give a user the operator role. Note the flag is `--uusername`; current Keycloak rejects the
`--uname` shown in some older instructions:

```bash
KC_ADMIN_USER=$(kubectl get secret keycloak-initial-admin -n keycloak -o jsonpath='{.data.username}' | base64 -d)
KC_ADMIN_PASS=$(kubectl get secret keycloak-initial-admin -n keycloak -o jsonpath='{.data.password}' | base64 -d)
kubectl exec -n keycloak keycloak-0 -- /opt/keycloak/bin/kcadm.sh add-roles \
  -r rossoctl --uusername alice --rolename rossoctl-operator \
  --no-config --server http://localhost:8080 --realm master \
  --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASS"
```

Log out and back in so the role lands in a fresh token, then open
`http://app-demo.localtest.me:8080` in a private window, sign in, pick a namespace, and send a
task to an agent.

### Exercising the broker without the UI

Useful for isolating the broker. JWT signature validation is off unless
`tokenBroker.jwt.jwksUrl` is set, so an unsigned token works for development:

```bash
kubectl port-forward -n rossoctl-system deploy/token-broker 8190:8190 &

SK=$(uuidgen | tr '[:upper:]' '[:lower:]')
JWT=$(echo -n '{"alg":"none","typ":"JWT"}' | base64 | tr -d '=' | tr '/+' '_-').$(echo -n "{\"sub\":\"alice\",\"session_uid\":\"$SK\"}" | base64 | tr -d '=' | tr '/+' '_-').

# 1. create a session (expect 201)
curl -s -X POST http://127.0.0.1:8190/sessions \
  -H "Authorization: Bearer $JWT" -H 'Content-Type: application/json' \
  -d '{"backend_session_redirect_url":"http://app-demo.localtest.me:8080/oauth-complete"}' \
  -w 'HTTP %{http_code}\n'

# 2. long-poll for the OAuth event, in another terminal
curl -s -X POST http://127.0.0.1:8190/sessions/broker-events -H "Authorization: Bearer $JWT"

# 3. request a token; this blocks while the poll above yields oauth_url_ready
curl -s -X POST http://127.0.0.1:8190/sessions/token \
  -H "Authorization: Bearer $JWT" \
  -H "X-Server-Url: http://mcp-server-service.rossoctl-demo.svc.cluster.local:8184"
```

Open the `auth_url` from the event in a browser, consent, and step 3 returns a token.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| No consent window appears | The UI opens consent with `window.open`, which browsers block outside a click handler. Allow pop-ups for `app-demo.localtest.me` and look for a blocked-pop-up icon in the address bar. |
| Consent is skipped entirely, yet a token arrives | Expected when you have already authorized the OAuth app and hold a live `github.com` session. Confirm at [github.com/settings/applications](https://github.com/settings/applications); revoke the app to force the prompt. |
| `504` on `/sessions/broker-events` after about five minutes | By design. The broker's request timeout is `tokenBroker.tokenWaitTimeout` plus ten seconds, so a 504 means nobody completed consent in time, not that the broker is broken. |
| Sidecar crash-loops on `broker_url is required` | `pluginPreset` was used instead of `authBridge.pipeline`. See [above](#why-the-chart-value-and-not-pluginpreset). |
| `502 oauth_upstream`, with `no such host` in the broker log | The resource server is not deployed, or the route names the wrong namespace. |
| `MCP connection failed` in the agent's reply | `MCP_URL` is wrong. It must be the in-cluster `http://` address of the resource server. |
| Token broker pod in `CreateContainerConfigError` | The `github-oauth-credentials` secret is missing from the broker's namespace. |
| GitHub rejects the redirect | The OAuth app's callback URL differs from `tokenBroker.oauth.callbackUrl`. |
| Agents missing from the app | The user lacks `rossoctl-operator`, or did not sign out and back in after the grant. |
| The token cannot read issues or pull requests | `tokenBroker.resourceConfig` pins the scopes it requests and overrides what the resource server advertises. Widen it to include `repo` if the agent needs repository data. |
| The agent reports a `400` about a function schema | Unrelated to authorization. The agent's MCP-to-LLM tool conversion emits a schema the provider rejects; the resource server's own schema is valid. Pin the agent's `crewai-tools` and `openai` versions. |
| `TOKEN_BROKER_URL` points at `rossoctl-demo` | A stale default in the example app's ConfigMap. The broker runs in `rossoctl-system`; an empty value silently disables the OAuth half rather than failing loudly. |

## See also

- [Troubleshooting](../operate/troubleshooting.md) — platform-wide failures
- [Observability](../operate/observability.md) — traces and metrics
