#!/usr/bin/env bash
# Enable SPIFFE identity for workloads in the test namespace.
#
# Switches from client-secret to federated-jwt authentication,
# ensuring each workload has a dedicated ServiceAccount and
# re-registering Keycloak clients with SPIFFE IDs.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

log_step "56" "Enable SPIFFE identity in $TX_NAMESPACE"

KC_URL=$(get_keycloak_url)
PLATFORM="${PLATFORM:-$(detect_platform)}"

if [[ "$PLATFORM" == "ocp" ]]; then
  KC_HOST="${KEYCLOAK_HOST:-$(kubectl get route -n "$KC_NAMESPACE" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)}"
else
  KC_HOST="${KEYCLOAK_HOST:-keycloak.localtest.me}"
fi

# --- Detect SPIFFE IDP ---
TOKEN=$(get_admin_token "$KC_URL")
AUTH_TYPE="client-secret"
if [[ -n "$TOKEN" ]]; then
  HAS_SPIFFE_IDP=$(curl -sk "$KC_URL/admin/realms/$TX_REALM/identity-provider/instances" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null | jq -r '.[] | select(.providerId == "spiffe") | .alias' 2>/dev/null || true)
  if [[ -n "$HAS_SPIFFE_IDP" ]]; then
    AUTH_TYPE="federated-jwt"
    log_info "SPIFFE IDP '$HAS_SPIFFE_IDP' found — using federated-jwt"
  else
    log_warn "No SPIFFE IDP found — falling back to client-secret"
  fi
fi

# --- Update authbridge-config ---
log_info "Updating authbridge-config (SPIRE_ENABLED=true, CLIENT_AUTH_TYPE=$AUTH_TYPE)"
kubectl patch configmap authbridge-config -n "$TX_NAMESPACE" --type=merge \
  -p "{\"data\":{\"SPIRE_ENABLED\":\"true\",\"CLIENT_AUTH_TYPE\":\"$AUTH_TYPE\"}}"

# --- Update authbridge-runtime-config ---
log_info "Updating authbridge-runtime-config (identity type + jwt_svid_path)"
RUNTIME_YAML=$(kubectl get configmap authbridge-runtime-config -n "$TX_NAMESPACE" -o jsonpath='{.data.config\.yaml}')
UPDATED_YAML=$(echo "$RUNTIME_YAML" | python3 -c "
import sys
lines = []
has_svid = False
for line in sys.stdin:
    stripped = line.rstrip()
    if 'jwt_svid_path' in stripped:
        has_svid = True
    lines.append(stripped)
result = []
for line in lines:
    if 'type: \"client-secret\"' in line:
        result.append(line.replace('client-secret', 'spiffe'))
    else:
        result.append(line)
    if 'client_secret_file' in line and not has_svid:
        indent = len(line) - len(line.lstrip())
        result.append(' ' * indent + 'jwt_svid_path: \"/opt/jwt_svid.token\"')
print('\n'.join(result))
")
kubectl patch configmap authbridge-runtime-config -n "$TX_NAMESPACE" --type=merge \
  -p "{\"data\":{\"config.yaml\":$(echo "$UPDATED_YAML" | jq -Rs .)}}"

# --- Align the SVID audience/issuer with Keycloak's ACTUAL realm issuer ---
# The JWT-SVID's `aud` (and the AuthBridge inbound issuer) must equal Keycloak's realm
# issuer, or KC rejects the assertion with "Invalid token audience" (#2342). The operator
# injects the spiffe-helper config (which mints the SVID audience) from authbridge-config's
# JWT_AUDIENCE — NOT the spiffe-helper-config ConfigMap — so patch that (and any per-workload
# copies), then restart the workloads so the SVID is re-minted with the correct audience.
# Derived from the live realm, so it is correct on Kind (http://…:8080) and OCP (https://…).
log_info "Aligning SVID audience/issuer with Keycloak realm issuer"
KC_ISSUER=$(curl -sk "${KC_URL}/realms/${TX_REALM}/.well-known/openid-configuration" 2>/dev/null | jq -r '.issuer // empty')
if [[ -n "$KC_ISSUER" ]]; then
  log_info "Keycloak realm issuer: $KC_ISSUER"
  for CM in authbridge-config $(kubectl get cm -n "$TX_NAMESPACE" -o name 2>/dev/null | sed 's|configmap/||' | grep -E '^authbridge-config-'); do
    kubectl get cm "$CM" -n "$TX_NAMESPACE" >/dev/null 2>&1 || continue
    kubectl patch configmap "$CM" -n "$TX_NAMESPACE" --type=merge \
      -p "{\"data\":{\"JWT_AUDIENCE\":\"$KC_ISSUER\",\"ISSUER\":\"$KC_ISSUER\"}}" 2>/dev/null || true
  done
  # Restart the workloads so spiffe-helper re-mints the SVID with the aligned audience.
  kubectl rollout restart deployment -n "$TX_NAMESPACE" 2>/dev/null || true
  kubectl rollout status deployment -n "$TX_NAMESPACE" --timeout=180s 2>/dev/null || \
    kubectl wait --for=condition=Available deployment --all -n "$TX_NAMESPACE" --timeout=180s 2>/dev/null || true
else
  log_warn "Could not read Keycloak realm issuer — SVID audience may not match (see #2342)"
fi

# --- Ensure dedicated ServiceAccounts ---
log_info "Ensuring dedicated ServiceAccounts"
WORKLOADS=$(kubectl get deploy -n "$TX_NAMESPACE" -l 'rossoctl.io/type in (agent,tool)' -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)
if [[ -z "$WORKLOADS" ]]; then
  WORKLOADS=$(kubectl get deploy -n "$TX_NAMESPACE" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null | grep -E "tx-e2e-" || true)
fi

for DEPLOY in $WORKLOADS; do
  CURRENT_SA=$(kubectl get deploy "$DEPLOY" -n "$TX_NAMESPACE" -o jsonpath='{.spec.template.spec.serviceAccountName}' 2>/dev/null || true)
  if [[ -z "$CURRENT_SA" || "$CURRENT_SA" == "default" ]]; then
    kubectl create sa "$DEPLOY" -n "$TX_NAMESPACE" 2>/dev/null || true
    kubectl patch deploy "$DEPLOY" -n "$TX_NAMESPACE" --type=json \
      -p="[{\"op\":\"add\",\"path\":\"/spec/template/spec/serviceAccountName\",\"value\":\"${DEPLOY}\"}]"
    log_info "  $DEPLOY: created SA and updated deployment"
  fi
done

# --- Delete old credentials for re-registration ---
log_info "Deleting old Keycloak clients for re-registration"
if [[ -n "$TOKEN" ]]; then
  TOKEN=$(get_admin_token "$KC_URL")
  CLIENT_UUIDS=$(curl -sk "$KC_URL/admin/realms/$TX_REALM/clients?max=100" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null | \
    jq -r ".[] | select(.clientId | contains(\"/ns/${TX_NAMESPACE}/sa/\") or startswith(\"${TX_NAMESPACE}/\")) | .id" 2>/dev/null || true)
  for UUID in $CLIENT_UUIDS; do
    TOKEN=$(get_admin_token "$KC_URL")
    curl -sk -X DELETE "$KC_URL/admin/realms/$TX_REALM/clients/$UUID" \
      -H "Authorization: Bearer $TOKEN" -o /dev/null 2>/dev/null || true
  done
fi

log_info "Deleting old credential secrets"
for SECRET in $(kubectl get secrets -n "$TX_NAMESPACE" -o name 2>/dev/null | grep rossoctl-keycloak-client-credentials); do
  kubectl delete "$SECRET" -n "$TX_NAMESPACE" 2>/dev/null || true
done

# --- Restart workloads ---
log_info "Restarting workloads to pick up SPIFFE identity"
for DEPLOY in $WORKLOADS; do
  kubectl rollout restart "deploy/$DEPLOY" -n "$TX_NAMESPACE" 2>/dev/null || true
done

log_success "SPIFFE identity enabled in $TX_NAMESPACE"
