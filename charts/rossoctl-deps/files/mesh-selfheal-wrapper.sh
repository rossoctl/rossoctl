#!/usr/bin/env bash
#
# mesh-selfheal-wrapper.sh — Part B scheduling+safety wrapper around mesh-recover.sh
# (rossoctl/rossoctl#1899). Run by the mesh-selfheal CronJob on each tick:
#   1. detect: mesh-recover.sh --json   (exit 0 healthy / 2 degraded / 3 inconclusive)
#   2. on degraded, apply cooldown + max-restart(window) gating from a state ConfigMap
#   3. if allowed: mesh-recover.sh --fix   (rollout restart ztunnel + waypoints + gateway)
#   4. emit k8s Events throughout; persist restart state back to the ConfigMap
#
# Env (set by the CronJob):
#   GATEWAY_URL, PROBE_HOST (optional), INCLUDE_SPIRE (true/false),
#   COOLDOWN_SECONDS, MAX_RESTARTS, WINDOW_SECONDS, STATE_NS, STATE_CM, CRONJOB_NAME
set -uo pipefail

NS="${STATE_NS:?STATE_NS required}"
CM="${STATE_CM:?STATE_CM required}"
COOLDOWN="${COOLDOWN_SECONDS:-900}"
MAX_RESTARTS="${MAX_RESTARTS:-5}"
WINDOW="${WINDOW_SECONDS:-3600}"
CRONJOB="${CRONJOB_NAME:-mesh-selfheal}"
now=$(date +%s)

log() { echo "[mesh-selfheal] $*" >&2; }

# Best-effort k8s Event against the CronJob so `kubectl describe cronjob mesh-selfheal` shows history.
emit_event() {  # $1=type(Normal|Warning) $2=reason $3=message
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  kubectl -n "$NS" create -f - >/dev/null 2>&1 <<EOF || log "event emit failed (non-fatal): $2"
apiVersion: v1
kind: Event
metadata:
  generateName: mesh-selfheal-
  namespace: ${NS}
type: ${1}
reason: ${2}
message: ${3}
firstTimestamp: ${ts}
lastTimestamp: ${ts}
count: 1
source:
  component: mesh-selfheal
involvedObject:
  apiVersion: batch/v1
  kind: CronJob
  name: ${CRONJOB}
  namespace: ${NS}
EOF
}

read_state() {  # $1=key ; echoes value or 0
  local v; v=$(kubectl -n "$NS" get cm "$CM" -o "jsonpath={.data.$1}" 2>/dev/null || true)
  echo "${v:-0}"
}

# --- 1. detect (never mutates) ---
args=(--json --gateway-url "$GATEWAY_URL")
[ -n "${PROBE_HOST:-}" ] && args+=(--probe-host "$PROBE_HOST")
[ "${INCLUDE_SPIRE:-false}" = "true" ] && args+=(--include-spire)

summary=$(bash /scripts/mesh-recover.sh "${args[@]}" 2>/dev/null); rc=$?
log "detect rc=$rc summary=$summary"

case "$rc" in
  0) emit_event Normal MeshHealthy "gateway reachable, mesh certs OK"; exit 0 ;;
  3) emit_event Warning MeshInconclusive "cannot confirm mesh health (restart would not help): ${summary}"; exit 0 ;;
  2) : ;;  # degraded/recoverable — fall through to gating
  *) log "unexpected rc=$rc; treating as inconclusive"; emit_event Warning MeshInconclusive "mesh-recover.sh rc=$rc"; exit 0 ;;
esac

# --- 2. gating (cooldown + max-restarts within a rolling window) ---
last=$(read_state last_restart)
count=$(read_state restart_count)
wstart=$(read_state window_start)
[ "$wstart" = "0" ] && wstart=$now
# reset the rolling window if it has elapsed
if [ $((now - wstart)) -ge "$WINDOW" ]; then count=0; wstart=$now; fi

if [ $((now - last)) -lt "$COOLDOWN" ]; then
  emit_event Warning MeshCooldown "degraded but within ${COOLDOWN}s cooldown since last restart — skipping: ${summary}"
  log "in cooldown ($((now - last))s < ${COOLDOWN}s); skip"
  exit 0
fi
if [ "$count" -ge "$MAX_RESTARTS" ]; then
  emit_event Warning MeshRestartCapHit "degraded but restart cap ${MAX_RESTARTS}/${WINDOW}s reached — manual intervention needed: ${summary}"
  log "restart cap hit ($count >= $MAX_RESTARTS); skip"
  exit 0
fi

# --- 3. remediate ---
emit_event Warning MeshDegraded "recoverable mesh outage detected — issuing rollout restart: ${summary}"
log "degraded — running --fix"
bash /scripts/mesh-recover.sh --fix "${args[@]:1}" >&2 2>&1 || log "mesh-recover.sh --fix returned non-zero (continuing)"

# --- 4. persist state + Event ---
kubectl -n "$NS" patch cm "$CM" --type merge \
  -p "{\"data\":{\"last_restart\":\"$now\",\"restart_count\":\"$((count + 1))\",\"window_start\":\"$wstart\"}}" \
  >/dev/null 2>&1 || log "state ConfigMap patch failed (non-fatal)"
emit_event Normal MeshRecoverAttempted "rollout restart issued (attempt $((count + 1))/${MAX_RESTARTS} in window)"
log "recover attempted; state updated (count=$((count + 1)))"
exit 0
