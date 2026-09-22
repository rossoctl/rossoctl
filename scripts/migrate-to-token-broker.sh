#!/bin/bash
set -euo pipefail

# Switch the cortex outbound plugin chain from token-exchange to token-broker,
# enabling the HITL (human-in-the-loop) OAuth2 flow: an agent that needs
# permissions beyond its own token gets them just-in-time, with user consent,
# without the agent knowing a broker exists.
#
# Doing this by hand is error-prone:
#   * token-exchange and token-broker are mutually exclusive on the outbound
#     chain (both claim the Authorization header), so this replaces rather than
#     appends;
#   * the pipeline lives in exactly one place, authBridge.pipeline, which
#     charts/rossoctl/templates/_helpers.tpl renders into each namespace's
#     authbridge-runtime-config ConfigMap;
#   * the obvious `helm upgrade --reuse-values` silently undoes the change (see
#     the note in Step 2);
#   * injected sidecars only read that ConfigMap at startup, so workloads must
#     be restarted afterwards.
#
# Docs: docs/hitl/hitl-auth-demo.md
#
# PREREQUISITES
#   1. A rossoctl platform install (scripts/kind/setup-rossoctl.sh ...).
#   2. token-broker running in the release namespace. It ships inside the
#      operator image; enable it on the operator chart:
#        --set operator-chart.tokenBroker.enabled=true
#      (requires the operator release that folds token-broker into the operator
#      image — rossoctl/operator#536.)
#   3. A github-oauth-credentials Secret in the release namespace.
#   4. An OAuth-protected resource server serving
#      /.well-known/oauth-protected-resource.
#   See docs/hitl/hitl-auth-demo.md for all four.
#
# USAGE
#   scripts/migrate-to-token-broker.sh [--revert] [--yes]
#
#   --revert   switch back to token-exchange
#   --yes      skip the confirmation prompt
#
# ENVIRONMENT
#   RELEASE          Helm release name      (default: rossoctl)
#   SYSTEM_NS        release namespace      (default: rossoctl-system)
#   BROKER_URL       token-broker base URL  (default: derived from SYSTEM_NS)
#   MCP_SERVER_HOST  resource server host to broker tokens for
#   NAMESPACES       agent namespaces to restart (default: team1 team2)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Configuration -----------------------------------------------------------
# The token-broker service runs in the release namespace (operator chart);
# only the MCP resource server lives in a demo namespace.
RELEASE="${RELEASE:-rossoctl}"
SYSTEM_NS="${SYSTEM_NS:-rossoctl-system}"
BROKER_URL="${BROKER_URL:-http://token-broker.${SYSTEM_NS}.svc.cluster.local:8190}"
MCP_SERVER_HOST="${MCP_SERVER_HOST:-mcp-server-service.rossoctl-demo.svc.cluster.local}"
# Explicit list rather than a glob, so the set is visible and reviewable.
NAMESPACES=(${NAMESPACES:-team1 team2})

CHART_DIR="${REPO_ROOT}/charts/rossoctl"

REVERT=false
ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    --revert) REVERT=true ;;
    --yes|-y) ASSUME_YES=true ;;
    -h|--help) sed -n '3,46p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg (try --help)"; exit 2 ;;
  esac
done

TARGET_PLUGIN="token-broker"
$REVERT && TARGET_PLUGIN="token-exchange"

echo "=== Token-Broker Pipeline Migration ==="
echo ""
if $REVERT; then
  echo "Mode:               REVERT (token-broker -> token-exchange)"
else
  echo "Mode:               MIGRATE (token-exchange -> token-broker)"
  echo "Broker service URL: $BROKER_URL"
  echo "MCP server route:   $MCP_SERVER_HOST"
fi
echo "Release/namespace:  $RELEASE / $SYSTEM_NS"
echo "Chart:              $CHART_DIR"
echo "Restart namespaces: ${NAMESPACES[*]}"
echo ""

# --- Preflight ---------------------------------------------------------------
echo "=== Preflight ==="

if ! helm status "$RELEASE" -n "$SYSTEM_NS" >/dev/null 2>&1; then
  echo "ERROR: no Helm release '$RELEASE' in namespace '$SYSTEM_NS'."
  echo "  Install the platform first: scripts/kind/setup-rossoctl.sh ..."
  exit 1
fi
echo "✓ Helm release '$RELEASE' found in $SYSTEM_NS"

[ -d "$CHART_DIR" ] || { echo "ERROR: chart not found at $CHART_DIR"; exit 1; }
echo "✓ chart present at charts/rossoctl"

if ! $REVERT; then
  if ! kubectl get deploy token-broker -n "$SYSTEM_NS" >/dev/null 2>&1; then
    echo "ERROR: no token-broker Deployment in $SYSTEM_NS."
    echo "  token-broker ships inside the operator image; enable it with:"
    echo "    helm upgrade $RELEASE charts/rossoctl -n $SYSTEM_NS --reuse-values \\"
    echo "      --set operator-chart.tokenBroker.enabled=true"
    exit 1
  fi
  echo "✓ token-broker Deployment present"

  if ! kubectl get secret github-oauth-credentials -n "$SYSTEM_NS" >/dev/null 2>&1; then
    echo "ERROR: Secret github-oauth-credentials missing in $SYSTEM_NS."
    echo "  kubectl create secret generic github-oauth-credentials -n $SYSTEM_NS \\"
    echo "    --from-literal=client-id=<CLIENT_ID> --from-literal=client-secret=<CLIENT_SECRET>"
    echo "  See docs/hitl/hitl-auth-demo.md for creating the OAuth App."
    exit 1
  fi
  echo "✓ github-oauth-credentials Secret present"

  # Non-fatal: the broker only needs the resource server at token-request time,
  # but without it OAuth discovery fails with "no such host".
  mcp_ns="${MCP_SERVER_HOST#*.}"; mcp_ns="${mcp_ns%%.*}"
  mcp_svc="${MCP_SERVER_HOST%%.*}"
  if kubectl get svc "$mcp_svc" -n "$mcp_ns" >/dev/null 2>&1; then
    echo "✓ resource server Service $mcp_svc found in $mcp_ns"
  else
    echo "⚠ resource server Service $mcp_svc not found in namespace $mcp_ns —"
    echo "  token requests will fail OAuth discovery until it is deployed."
    echo "  See docs/hitl/hitl-auth-demo.md."
  fi
fi

# --- Idempotence check -------------------------------------------------------
# Read the pipeline the release is actually running, rather than whatever state
# charts/rossoctl/values.yaml happens to be in. This script never writes to the
# chart; the new pipeline is handed to helm from a temp file.
LIVE_PIPELINE="$(helm get values "$RELEASE" -n "$SYSTEM_NS" --all -o yaml 2>/dev/null \
  | python3 -c "
import sys, yaml
try:
    d = yaml.safe_load(sys.stdin) or {}
except yaml.YAMLError:
    sys.exit(0)
print((d.get('authBridge') or {}).get('pipeline', ''))
")"

if [ -n "$LIVE_PIPELINE" ]; then
  if echo "$LIVE_PIPELINE" | grep -qE "^[[:space:]]*-[[:space:]]*name:[[:space:]]*${TARGET_PLUGIN}[[:space:]]*$"; then
    echo ""
    echo "✓ The release already runs '${TARGET_PLUGIN}' on the outbound chain."
    echo "  Nothing to do."
    $REVERT || echo "  (Use --revert to switch back to token-exchange.)"
    exit 0
  fi
  echo "✓ live pipeline read from the release"
else
  echo "⚠ could not read authBridge.pipeline from the release; proceeding anyway"
fi

if ! $ASSUME_YES; then
  echo ""
  read -p "Continue? (y/n) " -n 1 -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# --- Step 1: render the new pipeline ----------------------------------------
echo ""
echo "=== Step 1: Rendering the ${TARGET_PLUGIN} pipeline ==="

PIPELINE_TMP="$(mktemp)"
trap 'rm -f "$PIPELINE_TMP"' EXIT

# Helm template expressions are kept verbatim: the chart renders this block
# through tpl(), so {{ .Values.* }} must survive into the ConfigMap unevaluated.
REVERT="$REVERT" BROKER_URL="$BROKER_URL" MCP_SERVER_HOST="$MCP_SERVER_HOST" \
python3 > "$PIPELINE_TMP" <<'PYTHON_SCRIPT'
import os

revert = os.environ["REVERT"] == "true"

inbound = '''inbound:
  plugins:
    - name: jwt-validation
      config:
        issuer: "{{ .Values.keycloak.publicUrl }}/realms/{{ .Values.keycloak.realm }}"
        keycloak_url: "http://keycloak-service.{{ .Values.keycloak.namespace }}.svc:8080"
        keycloak_realm: {{ .Values.keycloak.realm | quote }}
outbound:
  plugins:
'''

token_exchange = '''    - name: token-exchange
      config:
        keycloak_url: "http://keycloak-service.{{ .Values.keycloak.namespace }}.svc:8080"
        keycloak_realm: {{ .Values.keycloak.realm | quote }}
        default_policy: "passthrough"
        identity:
          type: {{ eq .Values.authBridge.clientAuthType "federated-jwt" | ternary "spiffe" .Values.authBridge.clientAuthType | quote }}
          {{- if eq .Values.authBridge.clientAuthType "federated-jwt" }}
          jwt_audience: "{{ .Values.keycloak.publicUrl }}/realms/{{ .Values.keycloak.realm }}"
          {{- end }}'''

# default_policy passthrough means only hosts matching a route are brokered;
# everything else is forwarded untouched.
token_broker = f'''    - name: token-broker
      config:
        broker_url: "{os.environ["BROKER_URL"]}"
        default_policy: "passthrough"
        routes:
          rules:
            - host: "{os.environ["MCP_SERVER_HOST"]}"
              action: "broker"'''

print(inbound + (token_exchange if revert else token_broker))
PYTHON_SCRIPT

echo "✓ pipeline rendered (outbound: ${TARGET_PLUGIN})"

# --- Step 2: apply via Helm --------------------------------------------------
echo ""
echo "=== Step 2: Upgrading the Helm release ==="

# --reuse-values keeps whatever the original install set (openshift=false,
# component toggles, image overrides, ...) without this script having to know
# them. But it snapshots the release's COMPUTED values, so on its own it also
# carries forward the PREVIOUS authBridge.pipeline and silently undoes Step 1.
# --set-file re-supplies just that one key and takes precedence.
#
# Do NOT use `-f charts/rossoctl/values.yaml` instead: passing the whole file
# overrides the reused values with the file's defaults, including
# `openshift: true`, which trips the mcp-gateway OpenShift guard.
helm upgrade "$RELEASE" "$CHART_DIR" \
  -n "$SYSTEM_NS" \
  --reuse-values \
  --set-file authBridge.pipeline="$PIPELINE_TMP" \
  --timeout 10m

echo "✓ Helm release upgraded"

# --- Step 3: restart workloads ----------------------------------------------
# Sidecars read their config only at startup, so pods started before the upgrade
# still run the old pipeline. Deleting them makes Kubernetes recreate them with
# the new one.
#
# Two ways of finding those pods, because neither alone is both fast and complete:
#
#   By label: the operator sets rossoctl.io/type=agent|tool on every workload it
#   injects, so one query per namespace finds them. (Do not select on
#   rossoctl.io/inject — it only ever holds "disabled", to opt a workload out.)
#
#   By container name: an injected pod always has a container called
#   authbridge-proxy or envoy-proxy. Checking every pod costs one call each, but
#   catches anything the label query misses.
#
# Both run; a pod deleted by the first is skipped by the second.
echo ""
echo "=== Step 3: Restarting workloads to pick up the new pipeline ==="

for NS in "${NAMESPACES[@]}"; do
  kubectl get ns "$NS" >/dev/null 2>&1 || continue
  echo "Restarting workloads in namespace: $NS"

  # Workloads the operator injects: agents and tools.
  PODS=$(kubectl get pods -n "$NS" \
    -l 'rossoctl.io/type in (agent,tool)' -o name 2>/dev/null || true)
  if [ -n "$PODS" ]; then
    echo "  deleting injected agent/tool pods"
    echo "$PODS" | xargs -r kubectl delete -n "$NS" --wait=false 2>/dev/null || true
  fi

  # Anything else running a cortex sidecar that the label query missed.
  for pod in $(kubectl get pods -n "$NS" \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null); do
    if kubectl get pod "$pod" -n "$NS" -o jsonpath='{.spec.containers[*].name}' 2>/dev/null \
         | grep -q 'authbridge\|envoy-proxy'; then
      echo "  deleting $pod (has a cortex sidecar)"
      kubectl delete pod "$pod" -n "$NS" --wait=false >/dev/null 2>&1 || true
    fi
  done

  echo "✓ namespace $NS restarted"
done

# --- Verify -----------------------------------------------------------------
echo ""
echo "=== Verification ==="
echo ""
echo "Confirm the plugin reached a namespace config:"
echo "  kubectl get cm authbridge-runtime-config -n ${NAMESPACES[0]} -o yaml \\"
echo "    | grep -A6 'name: ${TARGET_PLUGIN}'"
echo ""
echo "Confirm a sidecar built its pipeline without errors:"
echo "  kubectl logs -n ${NAMESPACES[0]} <pod> -c authbridge-proxy | grep -i pipeline"
echo ""
if $REVERT; then
  echo "Reverted to token-exchange."
else
  echo "Migrated to token-broker. Drive the flow from the app-demo UI — see"
  echo "docs/hitl/hitl-auth-demo.md."
fi
echo ""
echo "To undo: $0 --revert"
