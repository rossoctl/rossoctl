# Design: Proactive SVID near-expiry detection, SPIRE TTL right-sizing, and 503 troubleshooting docs

**Issue:** [rossoctl/rossoctl#1899](https://github.com/rossoctl/rossoctl/issues/1899) — Mesh-wide 503 from expired SPIRE workload SVIDs on long-running/suspended Kind clusters.

**Date:** 2026-08-24
**Status:** Approved (brainstorming) — pending implementation plan
**Author:** cwiklik (Assisted-By: Claude Code)

## Background

On a long-running Kind cluster whose host is suspended longer than the SPIRE
credential lifetimes (SVID/CA/SA-token), every gateway-routed service returns
HTTP 503: the Ambient data plane (ztunnel + waypoints) keeps serving expired
mTLS certs and never re-fetches fresh ones. The cluster looks healthy to
`kubectl get pods`; the failure is only visible in ztunnel logs.

Two parts of the response are **already merged**:

- **Part A — [#2179](https://github.com/rossoctl/rossoctl/pull/2179)**:
  `scripts/k8s/mesh-recover.sh` — reactive detect + recover (rollout-restart
  ztunnel/waypoints/gateway). Exit codes `0=OK`, `2=DEGRADED` (restart helps),
  `3=INCONCLUSIVE`.
- **Part B — [#2452](https://github.com/rossoctl/rossoctl/pull/2452)**:
  a feature-flagged, Kind-only CronJob (`charts/rossoctl-deps/templates/mesh-selfheal.yaml`)
  that wraps Part A to auto-remediate on a schedule. Off by default.

Both are **reactive** — they act only once certs have already expired (503s,
"expired" log lines). Neither warns *before* the outage, tunes the TTLs that
make the outage likely, nor documents the failure for users.

**Out of scope (upstream):** the root-cause SPIRE agent re-attest deadlock and
ztunnel not re-fetching fresh SVIDs are tracked upstream
([ztunnel#1679](https://github.com/istio/ztunnel/issues/1679)). This work does
**not** `Close #1899`; it advances the issue's remediation points #4 (docs), #5
(TTL right-sizing), and #6 (proactive detection).

## Goals

1. **Proactive detection** — warn on *near-expiry* (not-yet-expired) SVIDs/CA
   before the 503, surfaced on the manual `k8s:health` / preflight path.
2. **TTL right-sizing (Kind-dev-only)** — lengthen SPIRE CA and x509 SVID TTLs
   so a normal overnight suspend no longer expires everything at once.
3. **Troubleshooting docs** — document the post-suspend 503, diagnosis, and
   recovery for users.

## Non-goals

- Fixing the upstream re-attest deadlock / ztunnel re-fetch (ztunnel#1679).
- Changing OpenShift SPIRE TTLs (suspend is not a production concern; the OCP
  path is separate and gated on `.Values.openshift`).
- Adding proactive detection to the automated CronJob image (see Decision D3).
- Auto-restarting on near-expiry (see Decision D2).

## Design

### Unit 1 — `check_cert_expiry()` in `scripts/k8s/mesh-recover.sh`

A new `check_*` function feeding the existing `record()` accumulator, adding a
new **`WARN`** status (advisory) alongside `OK`/`DEGRADED`/`INCONCLUSIVE`.

**Detection mechanism (graceful degradation, mirroring the existing
`istioctl`-optional pattern):**

1. If `istioctl` is present → `istioctl ztunnel-config certificates <ztunnel-pod>`;
   parse each SVID's expiry.
2. Else if `openssl` is present → read the trust-bundle CA cert from the
   `spire-bundle` (ns `spire-system`) or `istio-ca-root-cert` (ns
   `zero-trust-workload-identity-manager`) ConfigMap and run
   `openssl x509 -enddate`.
3. Else → `record` an `INCONCLUSIVE` finding
   ("cert-expiry tooling (istioctl/openssl) unavailable"). Non-fatal. This is
   the tool-less CronJob-image case, so the automated path simply skips the
   check rather than false-alarming.

**Threshold:** warn when remaining validity `< 25%` of the cert's total
lifetime (computed from `notBefore`/`notAfter`), so it adapts across the long
CA and the short SVIDs. Overridable via env `CERT_WARN_PCT` (default `25`) with
an absolute floor `CERT_WARN_SECONDS` (default `600`).

**Exit / behavior:** near-expiry maps to a **new exit code `4`** (advisory).
Precedence for the process exit code: `DEGRADED(2) > INCONCLUSIVE(3) > WARN(4) > OK(0)`
— i.e. an actual outage still wins and still triggers recovery; near-expiry only
sets the exit code when nothing worse is present. The `--json` output gains
`WARN`-status entries in its `checks` array.

### Unit 2 — CronJob wrapper mapping (`mesh-selfheal-wrapper.sh`)

The wrapper (`charts/rossoctl-deps/files/mesh-selfheal-wrapper.sh`) currently
maps rc `0→MeshHealthy`, `2→remediate`, `3→MeshInconclusive`. Add:

- `rc=4` → emit a `MeshNearExpiry` **Warning** Event with the summary; **no
  restart, no gating**; exit 0.

In practice the CronJob image (alpine/k8s, no openssl/istioctl) records the
check as INCONCLUSIVE, so rc=4 is primarily produced on the manual path. The
mapping is added for completeness and forward-compatibility.

### Unit 3 — `k8s:health` skill surfacing

Update `.claude/skills/k8s:health/SKILL.md` to run `mesh-recover.sh` (detect
mode) and surface the near-expiry `WARN`, replacing its current
"defer to `istio:mesh-selfheal`" note for the **proactive** case (the reactive
503 case still defers to recovery). `.github/scripts/common/90-preflight-checks.sh`
is intentionally **not** touched — it runs on fresh CI clusters where certs are
never near expiry.

### Unit 4 — SPIRE TTL right-sizing (Kind)

Kind installs SPIRE from the upstream SPIFFE hardened Helm charts
(`spiffe.github.io/helm-charts-hardened`: `spire-crds` 0.5.0 + `spire` 0.27.0),
configured entirely via `--set` flags in `scripts/kind/setup-rossoctl.sh`
(~lines 698–725). Today only `...clusterSPIFFEIDs.default.jwtTTL=5m` is set;
`ca_ttl` and the x509 SVID TTL are unset → chart defaults.

Add TTL `--set` flags next to the existing `jwtTTL`:

- **CA TTL: 24h → 168h (7d)**
- **x509 SVID TTL (ClusterSPIFFEID `ttl`): default → 24h**

**Rationale:** a 7d CA + 24h SVID lets a developer suspend overnight (~16h)
without the CA/SVIDs expiring at once, shrinking the #1899 vulnerability window,
while keeping dev credentials reasonably short. Honors SPIRE's constraint that
the x509 SVID TTL be well under the CA TTL (rotation at half-life). Kind-dev-only.

**To confirm during planning:** the exact upstream value keys and any
chart-version-specific naming in helm-charts-hardened `spire` 0.27.0 (e.g.
`spire-server.caTTL` vs `spire-server.ca_ttl`, and the ClusterSPIFFEID `ttl`
key), plus that the resulting SVIDs actually mint at the new TTL. The proposed
values are tunable.

### Unit 5 — Troubleshooting docs

Add a section to `docs/users-guides/troubleshooting.md`:
**"Mesh-wide 503 after laptop suspend (expired SPIRE SVIDs)"** covering:

- Symptom: all `*.localtest.me:8080` return 503 while pods/gateway look healthy.
- Diagnosis: the issue's one-liners (ztunnel `certificate expired`; spire-agent
  `reattest`/`token has expired`; SVID/CA TTLs; agent restart reason).
- Recovery: `scripts/k8s/mesh-recover.sh --fix` (or the manual rollout restart);
  pointer to the optional mesh-selfheal CronJob.
- Expectation: suspend longer than the CA TTL requires a data-plane restart or
  cluster recreate.

Cross-link from the `k8s:health` and `ui-debug` (502/503) skills.

## Decisions (from brainstorming)

- **D1 — Scope:** all three of detection + TTL + docs (not verification-only).
- **D2 — Near-expiry behavior:** advisory `WARN` only; no auto-restart.
- **D3 — Detection home:** the preflight / `k8s:health` path (tools present on a
  dev machine); the tool-less CronJob degrades to a skipped/INCONCLUSIVE check.
  No CronJob image change, no new RBAC.
- **D4 — TTL scope:** Kind-dev-only (`setup-rossoctl.sh`); OCP untouched.

## Gating / feature-flag posture

Per repo policy, new *features* are feature-flagged off by default. Here:

- Detection lives in a **script** (`mesh-recover.sh`) and inherits its callers'
  gating — manual `k8s:health` is opt-in; the CronJob is already flag-off. No
  new backend/frontend feature flag applies.
- TTL is a **dev-install config change** in the Kind setup script, not a runtime
  feature.

## Testing strategy

- **Detection (Unit 1/2):**
  - Live on `kind-rossoctl` with a deliberately high `CERT_WARN_PCT` (or low
    threshold) to force a `WARN` against current certs; confirm exit code 4 and
    the `WARN` JSON entry.
  - Run the detect path in the tool-less `alpine/k8s` image and confirm graceful
    `INCONCLUSIVE`/skip (no false alarm, non-fatal).
  - Confirm precedence: with an actual outage present, `DEGRADED(2)` still wins.
- **TTL (Unit 4):** run the modified `setup-rossoctl.sh` on Kind; confirm the
  SPIRE server CA TTL and minted x509 SVID TTL reflect the new values
  (`istioctl ztunnel-config certificates` validity window / SPIRE server config).
- **Docs (Unit 5):** link check; verify commands against a live cluster.

## Delivery

Single PR to `main`. Advances #1899 points #4/#5/#6; references "Part of #1899"
(does not close it — root cause is upstream ztunnel#1679).
