---
title: Authentication modes
description: Choose between provisioned client secrets and SPIFFE authentication.
sidebar_position: 4
---

Rossoctl supports two ways for the operator and your workloads to authenticate to Keycloak. Both are
configured automatically at install time; this page explains which you have and why you might change.

| | Client secrets (default) | SPIFFE authentication (recommended) |
| --- | --- | --- |
| Operator authenticates with | Keycloak admin credentials | Its own SPIFFE identity |
| Workloads authenticate with | A provisioned OAuth2 client secret | Their own SPIFFE identity |
| Requires | nothing extra | SPIRE — `--with-spire` |
| Credentials stored in the cluster | Yes, one Secret per workload | None |

The two are independent. You can run the operator on SPIFFE while workloads still use client secrets,
or the reverse.

## Client secrets

The default, and it works on any install.

The operator uses admin credentials to register a Keycloak client for each workload, and each workload
gets a provisioned OAuth2 client secret stored as a Kubernetes Secret in its namespace.

### How it works

1. At install, a Helm job reads admin credentials from the `keycloak-initial-admin` Secret and creates
   a `rossoctl-keycloak-client-secret` in each agent namespace.
2. When the operator's client-registration controller sees a new workload, it reads
   `keycloak-initial-admin` and registers an OAuth2 client in Keycloak.
3. The operator writes the generated `client_id` and `client_secret` into a
   `rossoctl-keycloak-client-credentials-*` Secret in the workload's namespace.
4. AuthBridge reads those files and uses them for outbound token exchange.

Nothing to set up. Per-workload Secrets are created on demand.

### Point the operator at a different admin Secret

```yaml
keycloak:
  adminSecretName: keycloak-initial-admin
  adminUsernameKey: username
  adminPasswordKey: password
```

### After rotating admin credentials

The operator caches them. Restart it so it re-reads the Secret:

```bash
kubectl rollout restart deployment/rossoctl-controller-manager -n rossoctl-system
```

Confirm it is authenticating:

```bash
POD=$(kubectl get pod -n rossoctl-system -l control-plane=controller-manager \
  -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n rossoctl-system "$POD" -c manager | grep -i "keycloak\|auth" | tail -5
```

## SPIFFE authentication

Recommended wherever you have SPIRE. No credential is provisioned, stored, or rotated by hand — there is
nothing to leak.

### How it works

SPIRE issues each workload a short-lived JWT SVID containing its SPIFFE identity. The workload presents
that to Keycloak as a client assertion ([RFC 7523](https://tools.ietf.org/html/rfc7523)) and gets an
access token back.

At install, a Helm job (`operator-client-bootstrap`) runs once with admin credentials to configure
Keycloak:

1. Creates a SPIFFE identity provider backed by SPIRE's OIDC discovery endpoint.
2. Creates a Keycloak client for the operator with `clientAuthenticatorType: federated-jwt` and the
   operator's SPIFFE ID as its subject.
3. Grants it `manage-clients` — scoped, not full admin.

After that the operator authenticates on every reconcile:

```
Operator pod
├─ spiffe-helper sidecar ──► SPIRE workload API
│     writes JWT SVID to /opt/jwt_svid.token, rotating it
└─ manager
      reads the JWT SVID ──► exchanges it with Keycloak ──► access token ──► Admin API
```

### The audience must be the public URL

This is the one thing that catches people.

The JWT SVID's `aud` claim must equal Keycloak's realm issuer URL, which is always
`keycloak.publicUrl/realms/<realm>`. It is derived from your Helm values automatically.

It has to be the **external, public URL** — not the in-cluster service address. Keycloak's issuer is
configured with the external URL and the check is a plain string comparison, so an in-cluster address
fails even though it reaches the same server.

If SPIFFE authentication fails with an audience or issuer mismatch, check `keycloak.publicUrl` first.

## Which should you use

Use **SPIFFE** if you installed with `--with-spire`. It removes provisioned credentials entirely, which
is the stronger posture and less to operate.

Use **client secrets** if you are not running SPIRE, or you are evaluating and want the smallest
install.

## Related

- [Workload identity](workload-identity.md) — verifying SPIRE.
- [AuthBridge](authbridge.md) — what uses these tokens.
