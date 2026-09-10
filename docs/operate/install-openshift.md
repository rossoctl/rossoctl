---
title: Install on OpenShift
description: Install Rossoctl on an OpenShift cluster.
sidebar_position: 3
---

The recommended method is the OpenShift installation script. One command installs SPIRE, cert-manager,
Keycloak, the operator, the MCP Gateway and the console.

## Requirements

| Requirement | Version |
| --- | --- |
| `oc` | 4.16.0 or later |
| An OpenShift cluster | Administrator access. The project tested version 4.19. The test pipeline uses version 4.20. |
| Helm | 3.18.0 or later, below 4 |

:::warning Remove an existing cert-manager first
Rossoctl installs its own cert-manager. If your cluster already has cert-manager, for example from the
Red Hat OpenShift cert-manager Operator, remove it before you run the script.
:::

## Install the platform

```bash
git clone https://github.com/rossoctl/rossoctl.git
cd rossoctl

oc login https://api.your-cluster.example.com:6443 -u kubeadmin -p <password>

./scripts/ocp/setup-rossoctl.sh
```

Run the script from the root directory of the repository, and after you sign in.

### The options

| Option | Function |
| --- | --- |
| `--rossoctl-repo PATH\|URL` | A local directory or a GitHub address. The default action is a clone of `main` into `~/.cache/rossoctl`. |
| `--realm REALM` | The Keycloak realm. The default is `rossoctl`. |
| `--skip-ovn-patch` | Omits the OVN routing change. The operator gives a warning at start-up if the change is absent. |
| `--skip-mcp-gateway` | Omits the MCP Gateway. |
| `--skip-ui` | Omits the console and the backend. |
| `--skip-mlflow` | Omits MLflow. |
| `--operator-image IMG:TAG` | Uses a different operator image. |
| `--dry-run` | Prints each command. It makes no change. |

## Open the console

```bash
echo "https://$(kubectl get route rossoctl-ui -n rossoctl-system \
  -o jsonpath='{.status.ingress[0].host}')"
```

If the cluster uses a self-signed certificate, accept the certificate in your browser. The MCP Inspector
and its proxy use one host name, so one action covers both.

To get the Keycloak administrator credentials:

```bash
kubectl get secret keycloak-initial-admin -n keycloak \
  -o go-template='Username: {{.data.username | base64decode}}  Password: {{.data.password | base64decode}}{{"\n"}}'
```

## Confirm the installation

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
kubectl get deployments -n rossoctl-system
```

If SPIRE reports `0` in the `Current` column or the `Ready` column, see
[Troubleshooting](troubleshooting.md).

## Models

Ollama cannot run on your computer for an OpenShift cluster. The agent is in a remote cluster and cannot
reach your computer. Select one of these three methods.

### Method 1: run Ollama in the cluster

Create a Deployment and a Service in the `rossoctl-system` namespace:

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

Apply the file with `kubectl apply -n rossoctl-system -f ollama.yaml`. Then get a model:

```bash
kubectl exec -n rossoctl-system deploy/ollama -- ollama pull qwen2.5:3b
```

Set the `LLM_API_BASE` variable of each agent to this address:

```
http://ollama.rossoctl-system.svc.cluster.local:11434/v1
```

Use this table to select the resources:

| Model | Memory | CPUs |
| --- | --- | --- |
| 3B, for example `qwen2.5:3b` | 8 Gi | 2 |
| 8B, for example `granite3.3:8b` | 16 Gi | 4 |
| 70B or larger | 64 Gi or more | 8 or more, and a GPU |

For more than a test, do these three actions. Request `nvidia.com/gpu` on a node that has a GPU. Replace
`emptyDir` with a PersistentVolumeClaim, so the model remains after a restart. Use node affinity to place
the pod on a node that has sufficient memory.

### Method 2: use an external Ollama server

Run `OLLAMA_HOST=0.0.0.0 ollama serve` on a computer that the cluster can reach. Then set `LLM_API_BASE`
to `http://<that-address>:11434/v1`.

### Method 3: use a cloud provider

This method is the simplest. See
[Configure a model](../get-started/configure-a-model.md#option-b-a-cloud-provider).

## Related pages

- [Install with Helm](install-helm.md) describes the installation of each chart.
- [Authentication modes](../security/authentication-modes.md)
- [Troubleshooting](troubleshooting.md)
