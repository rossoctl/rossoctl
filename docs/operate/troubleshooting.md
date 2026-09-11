---
title: Troubleshooting
description: The failures that occur most often, and the recovery for each one.
sidebar_position: 6
---

This page has two parts. The first part is the laptop install of Cortex. The second part is the
Kubernetes platform. If your condition is not here, ask in
[Slack](https://ibm.biz/rossoctl-slack), or open an issue on
[rossoctl/rossoctl](https://github.com/rossoctl/rossoctl/issues).

## On a laptop

These conditions occur with the laptop install from
[Quickstart on a laptop](../get-started/laptop.md). You do not need a Kubernetes cluster for this
part.

<!-- VERIFY v0.9.0: confirm the CA path, the service commands, the log path and the port against a
     v0.9.0 install. The laptop install (install.sh, abctl service, the launchd/systemd units) is a
     release target; see cortex#944 and cortex#945. -->

### The certificate authority is not trusted

Your agent reports a TLS error, or a certificate error, when it calls the model. The cause is that
the agent does not trust the certificate of RossoCortex.

Cortex writes its certificate authority to `~/.cortex/ca/ca.crt`. The `--claude-code` install
configures Claude Code for you. For another agent, you set the certificate variable yourself. See
[Other agents](../get-started/laptop.md#other-agents).

To confirm the certificate, read it:

```bash
openssl x509 -in ~/.cortex/ca/ca.crt -noout -subject -dates
```

If the file is absent, the install did not complete. Run the install again.

### The port 47600 is already in use

The install or the service reports that the port is in use. RossoCortex listens on three loopback
ports: 47600 for the proxy, 47601 for the session interface and 47602 for the statistics.

Find the program that holds the port:

```bash
lsof -nP -iTCP@127.0.0.1:47600 -sTCP:LISTEN
```

If the program is a previous Cortex service, stop it with `abctl service stop`. If it is another
program, stop that program, or change the ports of Cortex.

### The service does not start, or starts and stops

Read the status first:

```bash
abctl service status
```

On macOS, the service runs under `launchd`. On Linux, it runs under `systemd`. To read the service
log:

```bash
# macOS
log show --predicate 'process == "authbridge-proxy"' --last 10m

# Linux
journalctl --user -u cortex --since "10 minutes ago"
```

A service that starts and then stops usually has a port conflict, or a certificate that it cannot
write. The log gives the cause.

### Another program stopped working

If `git`, `gh`, `ssh` or `curl` stops working after you install Cortex, the cause is a proxy or a
certificate variable in your environment that sends other programs through Cortex.

Cortex configures only your agent. It does not set a global proxy. Examine your shell profile and
your environment for a `HTTP_PROXY`, `HTTPS_PROXY` or `NODE_EXTRA_CA_CERTS` value that you did not
intend:

```bash
env | grep -iE "PROXY|CA_CERT|CA_BUNDLE|SSL_CERT"
```

Remove the value that is not correct, and open a new terminal. See the tool-compatibility work in
cortex#946 and cortex#947.

### No events appear, though the agent runs

The agent runs, but `abctl observe` shows no events. Check each cause in order:

1. **The service does not run.** Run `abctl service status`.
2. **The agent does not use the proxy.** For an agent that is not Claude Code, confirm that you set
   the proxy variable and the certificate variable. See
   [Other agents](../get-started/laptop.md#other-agents).
3. **The agent sends no traffic yet.** Send a message to the agent, and watch for the events.

### The numbers are wrong or absent

- **The token count is zero.** RossoCortex reads the token counts from the reply of the model. A
  reply that Cortex cannot parse gives no counts. Confirm that the model is an OpenAI-compatible or an
  Anthropic endpoint.
- **The cost is zero, but the tokens are correct.** Cortex has no rate for that model. See
  [Read the cost](../get-started/reading-the-numbers.md#read-the-cost).
- **The pruning figure is zero.** The agent has no tool definitions to remove, or you did not enable
  pruning. See [Read the pruning savings](../get-started/reading-the-numbers.md#read-the-pruning-savings).

### Where the logs are, and what to attach to a bug report

The service log is in the location that the service status reports. To attach a useful report to an
issue, include:

- The output of `abctl --version`.
- The output of `abctl service status`.
- Your operating system and your architecture (`uname -sm`).
- The name of your agent, and the model.
- The last part of the service log, with any secret removed.

Open the issue with the **Laptop feedback** form on
[rossoctl/cortex](https://github.com/rossoctl/cortex/issues/new/choose). The form asks for each item
in the list above.

## On Kubernetes

The rest of this page is the Kubernetes platform.

### During the installation

#### The installation reports "exceeded its progress deadline"

The usual cause is a slow image download, and not a defect. Find the deployment that did not start, and
run the installer again:

```bash
kubectl get deployments --all-namespaces
```

Add the `--preload-images` option to the next installation. The script then downloads the images first,
which avoids the rate limits of Docker Hub.

#### You use Podman and not Docker

The installer needs a `docker` command on your path.

```bash
sudo ln -s /opt/podman/bin/podman /usr/local/bin/docker
brew install docker-credential-helper
```

If Keycloak reports insufficient memory, give the machine more memory:

```bash
podman machine stop
podman machine set --memory=12288 --cpus=8
podman machine start
```

To start again with a new machine:

```bash
podman machine rm -f
podman machine init --rootful --memory 18432 --cpus 6
podman machine start
```

To delete the cluster and keep the Podman machine:

```bash
kind delete cluster --name rossoctl
```

#### A build pod stays in `Pending` with `Insufficient cpu`

The node has insufficient CPU. The platform pods alone can request almost 4 CPUs.

Give the runtime 6 CPUs and create the cluster again, or deploy each agent from an image and not from
source. See [Machine size](index.md#machine-size).

#### The console shows an empty page on macOS

If **Content & Privacy Restrictions** are active, the console can show an empty page. The setting is in
System Settings, then Screen Time, then Content & Privacy Restrictions.

Disable the restrictions, and then restart the console:

```bash
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

#### The SPIRE DaemonSets report 0 ready

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

No feature that needs a workload identity operates until these DaemonSets are ready. Examine the pods for
a scheduling failure or an image download failure, and confirm that the node has capacity.

### When you deploy an agent or a tool

#### `Init:ErrImagePull` or `Init:ImagePullBackOff`

In almost all cases, your GitHub token is expired:

```
failed to authorize: failed to fetch oauth token: unexpected status from GET request to
https://ghcr.io/token?scope=repository%3Arossoctl%2F...: 403 Forbidden
```

Examine your [personal access token](https://github.com/settings/personal-access-tokens/). It needs the
`repo`, `write:packages` and `read:packages` permissions.

A 403 status from `ghcr.io` during the installation of a chart is usually a stored credential that is no
longer valid:

```bash
docker logout ghcr.io
docker login ghcr.io -u <your-github-username>
```

#### You must change a value in `.secrets.yaml`

The installer copies each secret into the namespaces. A change to the file is therefore not sufficient.
Delete the Secret in each namespace that received it, and then run the installer again:

```bash
kubectl get secret --all-namespaces
kubectl -n team1 delete secret github-token-secret
scripts/kind/setup-rossoctl.sh
```

### During operation

#### The chat page reports the status 503

The console shows this message:

```
An unexpected error occurred during A2A chat streaming: HTTP Error 503:
Network communication error: peer closed connection without sending complete message body
```

The log of the agent shows a `ConnectionResetError` message or a `ProtocolError` message.

The agent cannot reach its model. If the agent uses Ollama, the `ollama serve` command is almost certainly
not active:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

If the agent does not use Ollama, examine the model configuration of the agent:

```bash
kubectl exec -n team1 <agent-pod> -- env | grep LLM_
```

#### A service stops responding

This condition occurs with Keycloak and with the console. Restart the data plane:

```bash
kubectl rollout restart daemonset -n istio-system ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
```

#### A cluster returns 503 after you suspend the computer

**The condition.** Each address on `*.localtest.me:8080` returns the status 503 with the message
`upstream connect error ... connection termination`. Each pod is in the `Running` state, the gateway
reports `1/1`, and the `HTTPRoute` and `Gateway` resources report `Accepted`.

**The cause.** You suspended the computer for longer than the lifetime of a SPIRE identity document. The
Istio ambient data plane, which is ztunnel and the waypoints, continues to present expired certificates.
It does not read new certificates.

**To confirm the cause:**

```bash
kubectl logs -n istio-system -l app=ztunnel --tail=100 \
  | grep -iE "certificate expired|CertificateExpired"

kubectl logs -n spire-system -l app.kubernetes.io/name=agent --tail=100 \
  | grep -iE "reattest|service account token has expired"
```

**To recover:**

```bash
scripts/k8s/mesh-recover.sh --fix
```

Without the `--fix` option, the script reports the condition and prints the commands. It makes no change.

**To detect the condition before an outage,** run the script without the `--fix` option at a regular
interval. It exits with the code 4 when the first identity document expires in less than
`CERT_WARN_SECONDS`, which is 6 hours by default. The script needs `kubectl` access and `jq`. On Kind you
can also enable the `meshSelfHeal` feature flag, which adds a CronJob that does the restart.

**Expect this condition on a development cluster.** After a long suspension, you must restart the
data plane or create a new cluster. The cause is an upstream defect:
[istio/ztunnel#1679](https://github.com/istio/ztunnel/issues/1679).

#### Keycloak reports a connection error to its database

This condition occurs after the cluster runs for one day or longer. The cause is not completely
understood. For the investigation, see
[rossoctl#115](https://github.com/rossoctl/rossoctl/issues/115).

There is no reliable method to restart the database and Keycloak. The only reliable method is a new
installation of Keycloak:

```bash
helm uninstall keycloak -n keycloak
scripts/kind/setup-rossoctl.sh

kubectl rollout restart daemonset -n istio-system ztunnel
kubectl rollout restart -n rossoctl-system deployment http-istio
kubectl rollout restart -n rossoctl-system deployment rossoctl-ui
```

You must then restart each agent, so that each agent gets its Keycloak client again.

#### The operator cannot authenticate to Keycloak

This condition occurs after you change the administrator credentials. The operator holds the credentials
in memory. Restart it:

```bash
kubectl rollout restart deployment/rossoctl-controller-manager -n rossoctl-system
```

To confirm the result:

```bash
POD=$(kubectl get pod -n rossoctl-system -l control-plane=controller-manager \
  -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n rossoctl-system "$POD" -c manager | grep -i "keycloak\|auth" | tail -5
```

#### SPIFFE authentication reports an audience error or an issuer error

The `aud` claim of the identity document must be exactly `keycloak.publicUrl/realms/<realm>`. It must be
the **external** address. Keycloak has the public address in its issuer configuration, and the check is a
comparison of two strings. The internal address of the service reaches the same server and still fails.

Examine the `keycloak.publicUrl` value in your Helm values. See
[Authentication modes](../security/authentication-modes.md#the-audience-must-be-the-public-address).

#### The Skills entry does not appear in the console

The feature flag is not set. Enable it without a new installation:

```bash
helm upgrade rossoctl charts/rossoctl -n rossoctl-system \
  --reuse-values --set featureFlags.skills=true
```

Then confirm that the backend registered the routes:

```bash
kubectl logs -n rossoctl-system -l app.kubernetes.io/name=rossoctl-backend \
  | grep "skills routes registered"
```

### Commands for diagnosis

```bash
# Each pod that is not correct, in each namespace
kubectl get pods --all-namespaces | grep -vE "Running|Completed"

# Each address and each credential
./.github/scripts/local-setup/show-services.sh

# The RossoCortex configuration of one agent
rossoctl agents authbridge get <agent>

# The environment of one pod
kubectl exec -n <namespace> <pod> -- env | sort

# The log of the RossoCortex sidecar
kubectl logs -n <namespace> <pod> -c authbridge-proxy

# The log of the operator
kubectl logs -n rossoctl-system -l control-plane=controller-manager -c manager --tail=100
```
