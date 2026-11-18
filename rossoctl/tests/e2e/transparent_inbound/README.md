# Transparent inbound E2E

Gates the inbound half of the AuthBridge interception story
(rossoctl/cortex#330): with `inboundInterception: transparent`, JWT validation
must not be sidestepped by another pod dialing the agent's real port.

The assertion that matters is `test_direct_pod_dial_is_validated`. Everything
else exists to prove the shape is actually the one under test, and that turning
the feature on did not break the things it runs alongside (health probes, the
session-events API, egress enforcement).

`test_reverse_proxy_control_bypass_is_reachable` deliberately documents the
*old* behavior: under the default `reverse-proxy` mechanism the relocated agent
port answers without validation. If that test ever fails because the bypass is
gone, the default changed — which is a decision, not a bug, and the test should
be retired with it.

## Modules

| Module | Covers |
|---|---|
| `test_transparent_inbound.py` | The bypass property, injected shape, multi-port capture, sidecar ports, egress |
| `test_transparent_inbound_mtls.py` | Inbound mTLS through the transparent listener (rossoctl/cortex#780) |
| `test_transparent_inbound_ambient.py` | The same bypass property on the Istio ambient / HBONE path (rossoctl/cortex#780) |
| `test_egress_bypass.py` | Egress bypass is captured, proxy path, DNS, K8s API, unprivileged agent (#1940) |

`test_egress_bypass.py` dials `TI_EGRESS_TARGET` (default `http://rossoctl-ui.rossoctl-system.svc.cluster.local:8080/`) for its reach tests.

The mTLS module closes a gap the first one could not see. The transparent
listener reuses the reverse proxy's mTLS posture via `WrapListener`, and the
startup log said `mtls=true`, but no TLS client had ever been driven at it. The
untested part is the *combination*: `SO_ORIGINAL_DST` recovery happens on the raw
connection, before `tlssniff` peeks the first byte — had those interfered, the
logs would still have looked correct. It asserts plaintext is refused under
`strict` (so `tlssniff` is provably engaged, since the same request is a 401
under permissive), that a ClientHello reaches a real server-side handshake, and
that a valid SVID **completes** the handshake and then still gets a 401 from
`jwt-validation` — transport authentication is not request authorization.

It is module-scoped rather than session-scoped because it flips the same
namespace: it sets up and tears down within itself, restoring from a baseline
captured before the suite touched the namespace, so module order cannot change
the namespace's final state. It skips when SPIRE supplies no SVIDs, since a
completed-handshake assertion is not possible there.

The ambient module covers a path the other two structurally cannot reach. Without
a ztunnel, a pod-to-pod dial arrives as ordinary TCP and is captured in
`nat PREROUTING` by `AB_INBOUND`. Under ambient it never reaches `PREROUTING` at
all: ztunnel terminates HBONE on `:15008` and re-originates a local connection,
which surfaces in `nat OUTPUT` and is captured by a separate mark-based DNAT at
the head of `AB_REDIRECT` — ahead of that chain's ztunnel-mark `RETURN`. Two
paths, two rules, and the same 401 either way, so no other test can tell which
one carried the request. Hence `test_hbone_delivered_request_is_validated`
asserts the **path** as well as the status, from ztunnel's own access log:
without that, the module silently degrades into a duplicate of
`test_direct_pod_dial_is_validated` the moment ambient stops being engaged.

Removing that one DNAT rule from a live pod's netns makes the mesh-delivered
request return **200** — the app answering unvalidated — and the module fails
with that diagnosis, while the health-port test keeps passing. Rule ordering and
packet counters are not asserted directly: they are not reachable from a test
pod, and every way the rule can regress (deleted, ordered after the mark
`RETURN`, matching too narrowly) ends in that same 200. The counter-level
evidence for the rules as programmed is recorded on rossoctl/cortex#780.

Unlike the other two modules it is deliberately **not** `kind_only`. The platform
ships the ambient data plane on OpenShift only — `charts/rossoctl-deps/templates/istio-operand.yaml`
gates the `Istio`, `IstioCNI` and `ZTunnel` operands on `.Values.openshift`, and
`deployments/envs/dev_values*.yaml` set it false — so a Kind-only ambient test
could never run where ambient actually is the shipped configuration. It self-gates
on a ready ztunnel found by label across all namespaces (the platform chart uses
`istio-ztunnel`, a community `istio/ztunnel` install defaults to `istio-system`,
and neither changes the rule under test) plus `istio.io/dataplane-mode=ambient` on
both namespaces, skipping with whichever is missing named. Being unmarked makes it
the first module here to run on OpenShift, so its first run there may surface
pre-existing suite or platform issues rather than ambient ones.

## Namespaces

Runs in **pre-onboarded** namespaces (`team1`/`team2` by default, override with
`TI_NS_TRANSPARENT` / `TI_NS_CONTROL`) rather than creating its own. A fresh
namespace lacks the platform's per-namespace plumbing — `authbridge-config`, and
the Keycloak client registration that produces each agent's credentials Secret —
so an injected pod there never starts, for reasons unrelated to this feature.

Each fixture flips the namespace's `inboundInterception` in place and **restores
the original body on teardown**. These are shared namespaces: leaving one flipped
would silently change every other agent in it on its next pod recreation.

## Where it runs

Included in the shared e2e target list in
`.github/scripts/operator/90-run-e2e-tests.sh`, so it runs wherever that runner
does (Kind and HyperShift e2e, release validation) rather than only by hand.

It **self-gates** so that is safe on clusters running older images: if the injected
sidecar declares no `transparent-in` port, the deployed operator ignored the
namespace's `inboundInterception` and the suite skips with that cause named. It
becomes a real gate as soon as the cluster's operator and authbridge carry the
feature.

## Requirements

- A cluster with the operator + authbridge images built from this branch.
- `proxy.allowedInboundInterception` must permit `transparent` (the default).
- Linux nodes: the feature is iptables-based. Skipped elsewhere.
- **Working Keycloak client registration.** The injected sidecar mounts a
  per-agent credentials Secret the operator's ClientRegistration controller creates
  *asynchronously*. Where that path does not complete, every injected pod stays
  `Pending` on `FailedMount` — including default reverse-proxy ones — so it says
  nothing about interception. The suite **skips with the cause named** rather than
  failing and pointing suspicion at the interception rules.

  The controller logs its exact reason and then requeues every 30s, so read the
  log rather than guessing:

  ```sh
  kubectl logs -n rossoctl-system deployment/rossoctl-controller-manager \
    | grep -E 'cannot resolve|waiting for|registration failed|skipping'
  ```

  The reason that bit this suite, and the reason the fixtures create a dedicated
  ServiceAccount, is documented at the manifest in `conftest.py`: with SPIRE
  enabled the controller derives the Keycloak client ID from the **Deployment pod
  template's** `serviceAccountName` and refuses on `default`. The AuthBridge
  webhook does create a per-agent SA and set it on the **pod**, but never on the
  template — so the webhook's fixup is invisible to the controller, and the pod
  ends up mounting a Secret that the controller has already declined to create.
  That split is latent rather than an active platform defect: every path that
  creates a workload for real — the backend's agent and tool manifests, and the
  `7x-deploy-*` scripts — already sets `serviceAccountName`, so only a
  hand-written Deployment like this fixture ever reaches the refusal. Setting it
  here is matching what those paths do, not working around a bug. Note the
  `k8s.keycloak.org` CRD is **not** in this path — the controller uses Keycloak's
  admin REST API directly.

  `TI_STUB_CREDENTIALS=1` creates a placeholder Secret so the interception
  boundary can still be tested on a cluster where registration is genuinely
  broken. It is opt-in on purpose: stubbing by default would let the suite go
  green on such a cluster. The stub is sound for these assertions — the Secret is
  for *outbound* token-exchange, and inbound validation rejects a request with no
  Authorization header before any IdP contact — but it would **not** be sound for
  any test needing a valid token.

Four platform constraints the fixtures satisfy, each of which otherwise
produces a silently meaningless run:

- The namespace needs `rossoctl-enabled=true`, or the injection webhook's
  `namespaceSelector` skips it and the pod comes up with no sidecar at all.
- The pod template needs an explicit `serviceAccountName` (a dedicated SA, not
  `default`), or with SPIRE enabled the credentials Secret is never created and
  every pod stays `FailedMount` forever. See the requirement above.
- `rossoctl.io/type` cannot be applied by hand — the `agent-label-protection`
  ValidatingAdmissionPolicy rejects it. Injection is driven through an
  AgentRuntime CR, which is how agents are deployed for real.
- Readiness alone is not a usable gate: the AgentRuntime controller labels the
  pod template *after* the Deployment exists, so the first ready pod predates
  injection. The fixtures wait for the `authbridge-proxy` container.

```sh
uv run pytest rossoctl/tests/e2e/transparent_inbound/ -v
```
