---
title: Authentication modes
description: Select between client secrets and SPIFFE authentication.
sidebar_position: 4
---

Rossoctl has two modes for the authentication of the operator and your workloads to Keycloak. The
installer configures both modes automatically. This page explains which mode you have, and why you can
change it.

| | Client secrets, the default | SPIFFE authentication, recommended |
| --- | --- | --- |
| The operator authenticates with | Administrator credentials for Keycloak | Its own SPIFFE identity |
| A workload authenticates with | An OAuth2 client secret | Its own SPIFFE identity |
| Requirements | None | SPIRE, from the `--with-spire` option |
| Credentials in the cluster | One Secret for each workload | None |

The two modes are independent. The operator can use SPIFFE authentication while the workloads use client
secrets, or the reverse.

## Client secrets

This mode is the default, and it operates on any installation.

The operator uses administrator credentials to register a Keycloak client for each agent and each tool.
Each workload receives an OAuth2 client secret. Kubernetes holds that secret in a Secret in the
namespace of the workload.

### How the mode operates

1. At installation time, a Helm job reads the administrator credentials from the
   `keycloak-initial-admin` Secret. The job creates a `rossoctl-keycloak-client-secret` Secret in each
   agent namespace.
2. When the operator finds a new workload, it reads `keycloak-initial-admin` and registers an OAuth2
   client in Keycloak.
3. The operator writes the new `client_id` and `client_secret` values to a
   `rossoctl-keycloak-client-credentials-*` Secret in the namespace of the workload.
4. AuthBridge reads those files and uses them for the token exchange.

You configure nothing. The operator creates a Secret for each workload when you deploy the workload.

### To use a different administrator Secret

```yaml
keycloak:
  adminSecretName: keycloak-initial-admin
  adminUsernameKey: username
  adminPasswordKey: password
```

### After you change the administrator credentials

The operator holds the credentials in memory. Restart the operator so that it reads the Secret again:

```bash
kubectl rollout restart deployment/rossoctl-controller-manager -n rossoctl-system
```

Confirm that the operator authenticates:

```bash
POD=$(kubectl get pod -n rossoctl-system -l control-plane=controller-manager \
  -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n rossoctl-system "$POD" -c manager | grep -i "keycloak\|auth" | tail -5
```

## SPIFFE authentication

Use this mode when you have SPIRE. Rossoctl creates no credential, holds no credential and renews no
credential. There is therefore nothing that can leak.

### How the mode operates

SPIRE gives each workload a short-lived JWT document that contains the SPIFFE identity of the workload.
The workload presents that document to Keycloak as a client assertion, as
[RFC 7523](https://tools.ietf.org/html/rfc7523) describes. Keycloak returns an access token.

At installation time, a Helm job with the name `operator-client-bootstrap` runs one time. It uses
administrator credentials to configure Keycloak in three steps:

1. It creates a SPIFFE identity provider in Keycloak. The provider uses the discovery endpoint of SPIRE.
2. It creates a Keycloak client for the operator. The client uses the `federated-jwt` authenticator, and
   the subject is the SPIFFE identity of the operator.
3. It gives the client the `manage-clients` role. This role is limited. It is not the administrator role.

The operator then authenticates on each cycle:

```
Operator pod
├─ spiffe-helper container ──► SPIRE
│     writes the JWT document to /opt/jwt_svid.token, and renews it
└─ manager container
      reads the JWT document ──► exchanges it with Keycloak ──► access token
```

### The audience must be the public address

This requirement is the most common cause of a failure.

The `aud` claim of the JWT document must be exactly the issuer address of the Keycloak realm. That
address is always `keycloak.publicUrl/realms/<realm>`. Rossoctl calculates it from your Helm values.

The address must be the **external, public** address. It must not be the internal address of the
service. Keycloak has the public address in its issuer configuration, and the check is a comparison of
two strings. The internal address reaches the same server and still fails the check.

If SPIFFE authentication fails with an audience error or an issuer error, examine the
`keycloak.publicUrl` value first.

## Which mode to select

Select **SPIFFE authentication** if you installed SPIRE with the `--with-spire` option. This mode
removes each stored credential. It is the stronger mode and there is less to operate.

Select **client secrets** if you do not run SPIRE, or if you evaluate Rossoctl and want the smallest
installation.

## Related pages

- [Workload identity](workload-identity.md)
- [AuthBridge](authbridge.md)
