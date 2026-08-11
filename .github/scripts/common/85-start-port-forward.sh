#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/env-detect.sh"
source "$SCRIPT_DIR/../lib/logging.sh"

log_step "85" "Starting port-forward to Istio gateway"

# ============================================================================
# Wait for weather-service deployment to be ready
# (Even though we're port-forwarding to the gateway, we still need to ensure
# the backend services are healthy before tests can pass)
# ============================================================================

log_info "Waiting for weather-service deployment rollout to complete..."
kubectl rollout status deployment/weather-service -n team1 --timeout=120s || {
    log_error "Weather-service rollout not complete after 120s"
    kubectl get pods -n team1 -l app.kubernetes.io/name=weather-service
    kubectl get events -n team1 --sort-by='.lastTimestamp' --field-selector reason!=Pulling 2>/dev/null | tail -10
    exit 1
}

# Brief settle time — allow any cascading rollouts (webhook re-injection) to trigger
sleep 5

# Re-check rollout after settle (catches cascading rollouts from webhook restart)
kubectl rollout status deployment/weather-service -n team1 --timeout=60s 2>/dev/null || true

# ============================================================================
# Port-forward to Istio Gateway (http-istio)
# This is the production path - all traffic routes through the gateway
# using HTTPRoute hostname matching
# ============================================================================

log_info "Port-forwarding Istio gateway (http-istio) -> localhost:8080"

# Single port-forward to the gateway - all services are accessed via hostname routing
kubectl port-forward -n rossoctl-system svc/http-istio 8080:80 > /tmp/port-forward-gateway.log 2>&1 &
GATEWAY_PORT_FORWARD_PID=$!

if [ "$IS_CI" = true ]; then
    echo "GATEWAY_PORT_FORWARD_PID=$GATEWAY_PORT_FORWARD_PID" >> $GITHUB_ENV
else
    echo $GATEWAY_PORT_FORWARD_PID > /tmp/port-forward-gateway.pid
fi

# Wait for gateway port-forward to be ready
GATEWAY_READY=false
for i in {1..15}; do
    # Test gateway by hitting the UI route (should return HTML)
    if curl -s --max-time 2 -H "Host: rossoctl-ui.localtest.me" http://localhost:8080/ >/dev/null 2>&1; then
        log_success "Gateway port-forward is ready (localhost:8080) after ${i}s"
        GATEWAY_READY=true
        break
    fi
    sleep 1
done

if [ "$GATEWAY_READY" = false ]; then
    log_error "Gateway port-forward not ready after 15s"
    log_info "Gateway pod status:"
    kubectl get pods -n rossoctl-system -l app.kubernetes.io/name=gateway --no-headers 2>/dev/null || \
        kubectl get pods -n rossoctl-system -l istio=ingressgateway --no-headers 2>/dev/null || true
    log_info "Gateway logs (last 20 lines):"
    kubectl logs -n rossoctl-system -l app.kubernetes.io/name=gateway --tail=20 2>/dev/null || \
        kubectl logs -n rossoctl-system -l istio=ingressgateway --tail=20 2>/dev/null || true
    exit 1
fi

# ============================================================================
# Set environment variables for tests
# All services are accessed via the gateway with proper hostnames
# ============================================================================

DOMAIN="${DOMAIN_NAME:-localtest.me}"

# Weather agent - accessed via gateway with Host header
AGENT_HOST="weather-service.team1.svc.cluster.local"
if [ "$IS_CI" = true ]; then
    echo "AGENT_URL=http://localhost:8080" >> $GITHUB_ENV
    echo "AGENT_HOSTNAME=${AGENT_HOST}" >> $GITHUB_ENV
else
    export AGENT_URL="http://localhost:8080"
    export AGENT_HOSTNAME="${AGENT_HOST}"
fi

# Keycloak - accessed via gateway with Host header
KEYCLOAK_HOSTNAME="keycloak.${DOMAIN}"
if [ "$IS_CI" = true ]; then
    echo "KEYCLOAK_URL=http://localhost:8080" >> $GITHUB_ENV
    echo "KEYCLOAK_HOSTNAME=${KEYCLOAK_HOSTNAME}" >> $GITHUB_ENV
else
    export KEYCLOAK_URL="http://localhost:8080"
    export KEYCLOAK_HOSTNAME="${KEYCLOAK_HOSTNAME}"
fi

# Backend API - accessed via gateway with Host header
BACKEND_HOSTNAME="rossoctl-api.${DOMAIN}"
if kubectl get svc -n rossoctl-system rossoctl-backend >/dev/null 2>&1; then
    if [ "$IS_CI" = true ]; then
        echo "ROSSOCTL_BACKEND_URL=http://localhost:8080" >> $GITHUB_ENV
        echo "ROSSOCTL_BACKEND_HOSTNAME=${BACKEND_HOSTNAME}" >> $GITHUB_ENV
    else
        export ROSSOCTL_BACKEND_URL="http://localhost:8080"
        export ROSSOCTL_BACKEND_HOSTNAME="${BACKEND_HOSTNAME}"
    fi
fi

# MLflow - accessed via gateway with Host header
MLFLOW_HOSTNAME="mlflow.${DOMAIN}"
if kubectl get svc -n rossoctl-system mlflow >/dev/null 2>&1 || \
   kubectl get svc -n redhat-ods-applications mlflow >/dev/null 2>&1; then
    if [ "$IS_CI" = true ]; then
        echo "MLFLOW_URL=http://localhost:8080" >> $GITHUB_ENV
        echo "MLFLOW_HOSTNAME=${MLFLOW_HOSTNAME}" >> $GITHUB_ENV
    else
        export MLFLOW_URL="http://localhost:8080"
        export MLFLOW_HOSTNAME="${MLFLOW_HOSTNAME}"
    fi
fi

# ============================================================================
# Verify routing works for each service
# ============================================================================

log_info "Verifying gateway routing for each service..."

# Test weather agent (internal cluster hostname - no external HTTPRoute)
log_info "Testing weather-service route..."
if curl -s --max-time 3 -H "Host: ${AGENT_HOST}" http://localhost:8080/.well-known/agent-card.json >/dev/null 2>&1; then
    log_success "Weather agent route is working"
else
    log_warning "Weather agent route test failed (may not have HTTPRoute configured)"
fi

# Test Keycloak
log_info "Testing Keycloak route..."
if curl -s --max-time 3 -H "Host: ${KEYCLOAK_HOSTNAME}" http://localhost:8080/ >/dev/null 2>&1; then
    log_success "Keycloak route is working"
else
    log_error "Keycloak route test failed"
    log_info "HTTPRoute status:"
    kubectl get httproute -n keycloak keycloak -o yaml 2>/dev/null || true
    exit 1
fi

# Test Backend API (if deployed)
if kubectl get svc -n rossoctl-system rossoctl-backend >/dev/null 2>&1; then
    log_info "Testing backend API route..."
    if curl -s --max-time 3 -H "Host: ${BACKEND_HOSTNAME}" http://localhost:8080/health >/dev/null 2>&1 || \
       curl -s --max-time 3 -H "Host: ${BACKEND_HOSTNAME}" http://localhost:8080/api/v1/ >/dev/null 2>&1; then
        log_success "Backend API route is working"
    else
        log_warning "Backend API route test failed (may require authentication)"
    fi
fi

# Test MLflow (if deployed)
if kubectl get svc -n rossoctl-system mlflow >/dev/null 2>&1 || \
   kubectl get svc -n redhat-ods-applications mlflow >/dev/null 2>&1; then
    log_info "Testing MLflow route..."
    if curl -s --max-time 3 -H "Host: ${MLFLOW_HOSTNAME}" http://localhost:8080/ >/dev/null 2>&1; then
        log_success "MLflow route is working"
    else
        log_warning "MLflow route test failed (may require authentication)"
    fi
fi

log_success "Gateway port-forward started successfully"
log_info ""
log_info "Access services via gateway with Host headers:"
log_info "  Keycloak: curl -H 'Host: ${KEYCLOAK_HOSTNAME}' http://localhost:8080/"
log_info "  Backend:  curl -H 'Host: ${BACKEND_HOSTNAME}' http://localhost:8080/health"
log_info "  MLflow:   curl -H 'Host: ${MLFLOW_HOSTNAME}' http://localhost:8080/"
log_info ""
log_info "Tests will automatically use proper hostnames via *_HOSTNAME environment variables"
