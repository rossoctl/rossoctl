# Operator SPIFFE Authentication E2E Tests

## Context

PR [rossoctl-operator#522](https://github.com/rossoctl/operator/pull/522) removed the spiffe-helper sidecar from the operator pod and migrated to using the go-spiffe SDK directly via `workloadapi.Client.FetchJWTSVID()`.

## Current Status

**✅ Fully Implemented and Tested:**
- `fetchJWTSVID()` method uses `workloadapi.Client.FetchJWTSVID()` to get JWT-SVID from SPIRE
- `getKeycloakIssuer()` method queries `/.well-known/openid-configuration` to get authoritative issuer URL
- Unit tests for error handling in [clientregistration_controller_fetchjwtsvid_test.go](https://github.com/rossoctl/operator/blob/feat/spiffe-sdk-jwt-clean/operator/internal/controller/clientregistration_controller_fetchjwtsvid_test.go)
- Operator initializes with SPIFFE socket when `--use-spiffe-auth=true` flag is set
- ClientRegistrationReconciler watches Deployments/StatefulSets directly (no separate CRD needed)

**✅ E2E Verification Complete (2026-08-27):**
- Operator successfully fetches JWT-SVID from SPIRE using go-spiffe SDK
- Operator authenticates to Keycloak using JWT-SVID (no "Invalid token audience" errors)
- Operator registers clients with SPIFFE IDs as client-id
- Operator creates Secrets: `rossoctl-keycloak-client-credentials-*`
- Multiple successful reconciliations verified in Kind cluster with SPIFFE auth enabled
- Agent-to-tool communication works (MCP protocol, service discovery)

**Key Fix Applied:**
The critical fix was querying Keycloak's OIDC discovery endpoint to get the correct JWT-SVID audience. In Kubernetes deployments:
- `authbridge-config.KEYCLOAK_URL` = in-cluster service URL (e.g., `http://keycloak-service.keycloak.svc:8080`)
- Keycloak's issuer = public URL (e.g., `http://keycloak.localtest.me:8080/realms/rossoctl`)
- JWT-SVID audience must match the issuer URL, not the service URL

See commit `afce861` in PR #522 for implementation details.

## Required Tests (Once CRD is Available)

### 1. Operator Initialization Tests

**Test:** `test_operator_spiffe_auth_enabled`
- **Given:** Operator deployed with `spiffe.operatorAuth.enabled=true` in values
- **When:** Operator pod starts
- **Then:** 
  - Operator logs show: `"SPIFFE ID authentication enabled: using JWT-SVID for client registration"`
  - Operator has single container (no spiffe-helper sidecar)
  - Operator args include `--use-spiffe-auth=true`
  - Operator can connect to SPIRE socket at `/spiffe-workload-api/spire-agent.sock`

**Test:** `test_operator_spiffe_auth_disabled`
- **Given:** Operator deployed with `spiffe.operatorAuth.enabled=false` 
- **When:** Operator pod starts
- **Then:**
  - Operator uses client-secret authentication (not JWT-SVID)
  - No SPIFFE-related log messages

### 2. Client Registration with JWT-SVID

**Test:** `test_client_registration_uses_jwt_svid`
- **Given:** 
  - Operator with SPIFFE auth enabled
  - New AgentRuntime deployed (weather-service example)
- **When:** ClientRegistration controller reconciles the deployment
- **Then:**
  - Operator logs show: `"authenticated with JWT-SVID"` or similar
  - Keycloak client is created with SPIFFE ID as client_id
  - Client credentials Secret is created: `rossoctl-keycloak-client-credentials-*`
  - Secret contains `client-id.txt` and `client-secret.txt`

**Test:** `test_jwt_svid_audience_matches_keycloak_realm`
- **Given:** Operator fetching JWT-SVID for client registration
- **When:** `fetchJWTSVID()` is called with audience = Keycloak realm
- **Then:**
  - JWT-SVID audience claim matches the target Keycloak realm
  - Keycloak accepts the JWT-SVID for authentication
  - No "invalid audience" errors in logs

### 3. Token Exchange with Operator-Registered Clients

**Test:** `test_agent_token_exchange_with_operator_credentials`
- **Given:**
  - Agent registered by operator with JWT-SVID auth
  - Agent has client credentials Secret mounted
- **When:** Agent performs token exchange
- **Then:**
  - Token exchange succeeds using operator-provided credentials
  - Exchanged token has correct audience
  - User identity is preserved through exchange

**Test:** `test_tool_token_exchange_with_operator_credentials`
- **Given:**
  - Tool registered by operator (when `injectTools` feature gate is enabled)
  - Tool has client credentials Secret mounted
- **When:** Agent calls tool (triggering AuthBridge token exchange)
- **Then:**
  - AuthBridge successfully exchanges token for tool audience
  - Tool receives valid JWT
  - No "missing Authorization header" errors

### 4. Error Handling

**Test:** `test_operator_handles_spire_unavailable`
- **Given:** SPIRE agent is not running or socket is unavailable
- **When:** Operator tries to fetch JWT-SVID
- **Then:**
  - Operator logs clear error: `"failed to create SPIFFE Workload API client"`
  - Reconciliation is retried with backoff
  - System degrades gracefully (doesn't crash)

**Test:** `test_operator_handles_invalid_audience`
- **Given:** Operator fetches JWT-SVID with invalid audience
- **When:** JWT-SVID fetch fails
- **Then:**
  - Operator logs error: `"failed to fetch JWT-SVID"`
  - Client registration is retried
  - Event is recorded on AgentRuntime resource

**Test:** `test_operator_handles_keycloak_rejection`
- **Given:** Keycloak rejects JWT-SVID (wrong trust domain, expired, etc.)
- **When:** Operator tries to authenticate with Keycloak
- **Then:**
  - Operator logs Keycloak error response
  - Reconciliation is retried
  - Client registration eventually succeeds after fix

### 5. SPIFFE Trust Domain Validation

**Test:** `test_jwt_svid_trust_domain_matches_keycloak`
- **Given:** Operator SPIFFE ID has trust domain `spiffe://localtest.me/...`
- **When:** JWT-SVID is used to authenticate with Keycloak
- **Then:**
  - Keycloak validates the trust domain via SPIRE bundle
  - Authentication succeeds
  - No "untrusted issuer" errors

### 6. Upgrade/Migration Tests

**Test:** `test_upgrade_from_spiffe_helper_to_sdk`
- **Given:** Existing cluster with old operator (spiffe-helper sidecar)
- **When:** Operator is upgraded to new version (go-spiffe SDK)
- **Then:**
  - Existing client registrations continue to work
  - New registrations use SDK-based JWT-SVID fetching
  - No service disruption

## Test Data Location

Tests should be added to:
- `rossoctl/tests/e2e/token_exchange/test_operator_spiffe_auth.py` (new file)
- `rossoctl/tests/e2e/conftest.py` (add fixtures for operator logs, CRD checks)

## Fixtures Needed

```python
@pytest.fixture
def operator_pod_name():
    """Get the running operator pod name."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            "rossoctl-system",
            "-l",
            "app.kubernetes.io/name=controller-manager",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture
def operator_logs(operator_pod_name):
    """Get operator logs for inspection."""
    result = subprocess.run(
        [
            "kubectl",
            "logs",
            "-n",
            "rossoctl-system",
            operator_pod_name,
            "--tail=200",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


@pytest.fixture
def spiffe_auth_enabled():
    """Check if operator was deployed with SPIFFE auth enabled."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            "-n",
            "rossoctl-system",
            "rossoctl-controller-manager",
            "-o",
            "jsonpath={.spec.template.spec.containers[0].args}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return "--use-spiffe-auth=true" in result.stdout
```

## Verification

Manual verification performed:
- ✅ Operator builds with go-spiffe SDK
- ✅ Operator initializes with SPIFFE socket
- ✅ Single container (no spiffe-helper sidecar)
- ✅ `fetchJWTSVID()` code compiles
- ✅ Unit tests pass for error handling
- ⚠️ Full E2E blocked on ClientRegistration CRD

## Related PRs

- rossoctl-operator#522: Remove spiffe-helper, use go-spiffe SDK
- rossoctl-operator#478: (closed) Previous attempt with spiffe-helper removal
- rossoctl/rossoctl#TBD: E2E tests (this PR - to be created once CRD is available)

## References

- [go-spiffe SDK docs](https://github.com/spiffe/go-spiffe/tree/main/v2)
- [workloadapi.Client.FetchJWTSVID](https://pkg.go.dev/github.com/spiffe/go-spiffe/v2/workloadapi#Client.FetchJWTSVID)
- [jwtsvid.Params](https://pkg.go.dev/github.com/spiffe/go-spiffe/v2/svid/jwtsvid#Params)
- [SPIFFE Workload API spec](https://github.com/spiffe/spiffe/blob/main/standards/SPIFFE_Workload_API.md)
