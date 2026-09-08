---
title: Install on OpenShift
description: Install Rossoctl on an OpenShift cluster.
sidebar_position: 3
---

The recommended path is the OpenShift installer script, which puts SPIRE, cert-manager, Keycloak, the
operator, the MCP Gateway, and the console in place with one command.

## Prerequisites

| Requirement | Version |
| --- | --- |
| `oc` | 4.16.0 or later |
| OpenShift cluster | Admin access. Tested on 4.19; CI runs against 4.20. |
| Helm | 3.18.0 or later, below 4 |

:::warning Remove an existing cert-manager first
Rossoctl installs its own cert-manager. If your cluster already has one — from the Red Hat OpenShift
cert-manager Operator, for example — remove it before running the installer.
:::

## Install

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl

oc login https://api.your-cluster.example.com:6443 -u kubeadmin -p <password>

./scripts/ocp/setup-rossoctl.sh
```

Run it from the repository root, after logging in.

### Options

| Flag | Effect |
| --- | --- |
| `--rossoctl-repo PATH\|URL` | Local path or GitHub URL. Defaults to cloning `main` into `~/.cache/rossoctl`. |
| `--realm REALM` | Keycloak realm. Default `rossoctl`. |
| `--skip-ovn-patch` | Skip the OVN gateway routing patch. The operator warns at startup if it is missing. |
| `--skip-mcp-gateway` | Do not install the MCP Gateway. |
| `--skip-ui` | Do not install the console or backend. |
| `--skip-mlflow` | Do not install the MLflow integration. |
| `--operator-image IMG:TAG` | Use a custom operator image. |
| `--dry-run` | Print the commands without running them. |

## Access the console

```bash
echo "https://$(kubectl get route rossoctl-ui -n rossoctl-system \
  -o jsonpath='{.status.ingress[0].host}')"
```

With self-signed certificates, accept the certificate in your browser. The MCP Inspector and its proxy
share one host, so accepting the Inspector's certificate covers the proxy too.

Keycloak admin credentials:

```bash
kubectl get secret keycloak-initial-admin -n keycloak \
  -o go-template='Username: {{.data.username | base64decode}}  Password: {{.data.password | base64decode}}{{"\n"}}'
```

## Verify

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
kubectl get deployments -n rossoctl-system
```

If SPIRE shows `0` under `Current` or `Ready`, see [Troubleshooting](troubleshooting.md).

## Models

Ollama cannot run on your machine here — agents run in a remote cluster and cannot reach it. Three
options, easiest last.

### Run Ollama in the cluster

Create a Deployment and Service in `rossoctl-system`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  labels:
    app: ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
        - name: ollama
          image: ollama/ollama:latest
          ports:
            - containerPort: 11434
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
            limits:
              cpu: "4"
              memory: "16Gi"
          volumeMounts:
            - name: ollama-data
              mountPath: /root/.ollama
      volumes:
        - name: ollama-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
spec:
  selector:
    app: ollama
  ports:
    - port: 11434
      targetPort: 11434
```

Apply it with `kubectl apply -n rossoctl-system -f ollama.yaml`, then pull a model into the pod:

```bash
kubectl exec -n rossoctl-system deploy/ollama -- ollama pull qwen2.5:3b
```

Set each agent's `LLM_API_BASE` to:

```
http://ollama.rossoctl-system.svc.cluster.local:11434/v1
```

Sizing, if you go this route:

| Model | RAM | CPUs |
| --- | --- | --- |
| 3B, for example `qwen2.5:3b` | 8 Gi | 2 |
| 8B, for example `granite3.3:8b` | 16 Gi | 4 |
| 70B or larger | 64+ Gi | 8+, and a GPU |

For anything beyond testing: request `nvidia.com/gpu` on GPU nodes, replace `emptyDir` with a PVC so
models survive pod restarts, and use node affinity to place the pod where the memory is.

### Use an external Ollama server

Run `OLLAMA_HOST=0.0.0.0 ollama serve` on a machine the cluster can reach — a GPU workstation, for
example — and point `LLM_API_BASE` at `http://<its-address>:11434/v1`.

### Use a cloud provider

Simplest. See [Configure a model](../get-started/configure-a-model.md#option-b-a-cloud-provider).

## Related

- [Install with Helm](install-helm.md) — chart-level installs, including the OpenShift CA workaround.
- [Authentication modes](../security/authentication-modes.md).
- [Troubleshooting](troubleshooting.md).
