---
title: Workload identity
description: How SPIFFE identities are issued, what they look like, and how to verify them.
sidebar_position: 2
---

Every Rossoctl workload gets an identity from [SPIRE](https://spiffe.io/docs/latest/spire-about/) that
it can prove cryptographically. This is the root of the security model: access decisions start from a
verified identity, not from a credential a workload was handed.

Install SPIRE with `--with-spire` (or `--with-all`).

## The identity format

```
spiffe://{trust-domain}/ns/{namespace}/sa/{service-account}
```

Examples:

```
spiffe://localtest.me/ns/team/sa/weather-tool
spiffe://localtest.me/ns/team/sa/slack-researcher
spiffe://apps.cluster.example.com/ns/gateway-system/sa/mcp-gateway
```

The trust domain is set at install time with `--domain` (default `localtest.me` on Kind). Namespace and
service account come from the pod.

This matters: the identity is derived from **what the workload is**, attested by the node, rather than
from something the workload claims. A pod cannot present another pod's identity, and there is no
credential to steal, because the identity is re-issued continuously.

## SVIDs

SPIRE issues identity documents — SVIDs — in two formats, and both rotate automatically.

**X.509 SVID** — a certificate, used for mTLS between workloads.

**JWT SVID** — a signed token, used to authenticate to HTTP APIs such as Keycloak:

```json
{
  "sub": "spiffe://localtest.me/ns/team/sa/slack-researcher",
  "aud": "rossoctl",
  "iss": "https://spire-server.spire.svc.cluster.local:8443",
  "iat": 1735686000,
  "exp": 1735689600
}
```

A `spiffe-helper` sidecar, injected alongside your workload, fetches these from the SPIRE workload API
and writes them to disk, refreshing them before they expire. Your agent does not manage them.

## Verify SPIRE is working

The DaemonSets should be present and ready:

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

If `Current` or `Ready` is `0`, nothing else in this section will work. See
[Troubleshooting](../operate/troubleshooting.md).

The OIDC discovery endpoint should return signing keys:

```bash
curl http://spire-oidc.localtest.me:8080/keys
```

This endpoint is what lets Keycloak validate a workload's JWT SVID. If it is empty or unreachable,
SPIFFE authentication cannot work.

A workload should have received its documents:

```bash
kubectl exec -n team deployment/slack-researcher \
  --container authbridge-proxy -- ls -la /opt/
```

You should see `svid.pem`, `svid_key.pem`, `svid_bundle.pem`, and `jwt_svid.token`.

Tornjak gives you a browsable view of registered workloads:

```bash
open http://spire-tornjak-ui.localtest.me:8080/
```

## How identity becomes access

A SPIFFE identity says who a workload is. It does not by itself say what the workload may do — that
comes from Keycloak.

Each workload is registered as a Keycloak client using its SPIFFE ID as the client identifier. The
operator does this automatically when it sees a new workload. From then on the workload can present its
JWT SVID to Keycloak and get an access token, without ever holding a client secret.

See [Authentication modes](authentication-modes.md) for how that exchange is configured, and
[Identity and trust](../concepts/identity.md) for the full delegation chain.

## Certificates and host suspend

SVIDs are short-lived by design. If you suspend a laptop running a Kind cluster for longer than the
SVID lifetime, the Istio ambient data plane keeps serving expired certificates and does not re-fetch.
Everything returns `503` while all pods look healthy.

Recovery:

```bash
scripts/k8s/mesh-recover.sh --fix
```

Run without `--fix` to diagnose without changing anything. Details and the upstream issue are in
[Troubleshooting](../operate/troubleshooting.md#mesh-wide-503-after-host-suspend).

## Related

- [Authentication modes](authentication-modes.md) — client secrets versus SPIFFE.
- [AuthBridge](authbridge.md) — the plugins that use these identities.
- [SPIFFE concepts](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/) — the upstream standard.
