---
title: Workload identity
description: How SPIRE issues an identity, and how to confirm that it operates.
sidebar_position: 2
---

Each Rossoctl workload receives an identity from [SPIRE](https://spiffe.io/docs/latest/spire-about/).
The workload can prove that identity with cryptography. This identity is the basis of the security
model. Each access decision starts from a proven identity, and not from a credential that someone gave
to the workload.

Install SPIRE with the `--with-spire` option, or with `--with-all`.

## The form of an identity

```
spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}
```

These are examples:

```
spiffe://localtest.me/ns/team/sa/weather-tool
spiffe://localtest.me/ns/team/sa/slack-researcher
spiffe://apps.cluster.example.com/ns/gateway-system/sa/mcp-gateway
```

You set the trust domain at installation time with the `--domain` option. On Kind the default value is
`localtest.me`. The namespace and the service account come from the pod.

The identity comes from **what the workload is**, and the node attests it. It does not come from a value
that the workload asserts. A pod therefore cannot present the identity of a different pod. There is also
no credential to steal, because SPIRE issues the identity again continuously.

## The identity documents

SPIRE issues an identity document in two formats. It renews both formats automatically.

An **X.509 document** is a certificate. Workloads use it for mTLS.

A **JWT document** is a signed token. A workload uses it to authenticate to an HTTP interface such as
Keycloak:

```json
{
  "sub": "spiffe://localtest.me/ns/team/sa/slack-researcher",
  "aud": "rossoctl",
  "iss": "https://spire-server.spire.svc.cluster.local:8443",
  "iat": 1735686000,
  "exp": 1735689600
}
```

A helper program next to your workload reads both documents from SPIRE and writes them to a file. It
replaces each document before the document expires. Your agent does not manage them.

## Confirm that SPIRE operates

The DaemonSets must be present and ready:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

If the `Current` column or the `Ready` column shows `0`, no other feature in this section operates. See
[Troubleshooting](../operate/troubleshooting.md).

The discovery endpoint must return the signing keys:

```bash
curl http://spire-oidc.localtest.me:8080/keys
```

Keycloak uses this endpoint to validate the JWT document of a workload. If the endpoint is empty or does
not respond, SPIFFE authentication cannot operate.

A workload must have received its documents:

```bash
kubectl exec -n team deployment/slack-researcher \
  --container authbridge-proxy -- ls -la /opt/
```

You must see the files `svid.pem`, `svid_key.pem`, `svid_bundle.pem` and `jwt_svid.token`.

Tornjak gives a browser interface for the registered workloads:

```bash
open http://spire-tornjak-ui.localtest.me:8080/
```

## How an identity becomes access

A SPIFFE identity says which workload sent a request. It does not say what the workload can do. The
permissions come from Keycloak.

The operator registers each workload as a Keycloak client, and uses the SPIFFE identity of the workload
as the identifier of the client. The operator does this automatically when it finds a new workload. The
workload can then present its JWT document to Keycloak and receive an access token. It never holds a
client secret.

See [Authentication modes](authentication-modes.md) for the configuration of this exchange, and
[Identity and trust](../concepts/core/identity.md) for the complete chain of delegation.

## Certificates and a suspended computer

The identity documents are short-lived by design. A document can expire while a computer is suspended. The Istio ambient data plane then continues
to present the expired certificate. It does not read a new one. Each address then returns the status 503, and each pod appears
correct.

To recover:

```bash
scripts/k8s/mesh-recover.sh --fix
```

To examine the state without a change, run the script without the `--fix` option. For the details and
the upstream defect, see
[Troubleshooting](../operate/troubleshooting.md#a-cluster-returns-503-after-you-suspend-the-computer).

## Related pages

- [Authentication modes](authentication-modes.md)
- [AuthBridge](authbridge.md)
- [SPIFFE concepts](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/)
