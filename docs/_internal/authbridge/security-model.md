---
draft: true       # excluded from https://www.rossoctl.dev/
---

# AuthBridge Security Model

## The Problem: Why Agents Cannot Hold Their Own Credentials

Traditional applications manage their own credentials — API keys, service account
tokens, client secrets. This model breaks down for AI agents:

1. **Agents are autonomous** — they decide which tools to call at runtime. Giving an
   agent broad credentials means a hallucination or prompt injection can trigger
   unauthorized access.

2. **Blast radius** — a compromised agent namespace with static credentials exposes
   every service those credentials can reach. With token exchange, a compromised
   token grants access to one service for a short window.

3. **No audit trail** — if agents hold long-lived tokens, there's no record of *why*
   a particular call was made or *who* initiated the chain. Token exchange preserves
   the delegation chain.

4. **Credential sprawl** — at scale (50+ agents), managing per-agent secrets for every
   tool becomes operationally untenable.

AuthBridge solves this by moving credential management to the infrastructure layer.
Agents never see tokens. The platform issues short-lived, narrowly-scoped credentials
on demand, for each specific outbound call.

## Trust Model

### Who Trusts Whom

```
End User ──trust──► Rossoctl Platform ──trust──► Keycloak (IdP)
                         │                           │
                         │ enforces                   │ issues tokens
                         ▼                           ▼
                    AuthBridge ◄────────── SPIFFE/SPIRE (workload identity)
                         │
                         │ scoped tokens
                         ▼
                   External Tools / LLMs
```

| Relationship | Trust basis |
|---|---|
| End user → Platform | The platform enforces access policy; the agent cannot bypass it |
| Platform → Agent | The agent is authenticated via workload identity (SPIFFE SVID) |
| Platform → Keycloak | Keycloak issues and validates tokens; the platform trusts its signatures |
| Tool → Platform | Tools verify the audience-scoped token AuthBridge presents |
| Agent → AuthBridge | Agents trust that auth is handled transparently (they don't need to know) |

### What Is Enforced vs. Advisory

| Control | Enforced? | Mechanism |
|---|---|---|
| Outbound tool access (host allowlist) | Enforced | Proxy blocks disallowed destinations |
| Inbound JWT validation | Enforced | Requests without valid JWT are rejected (401) |
| Token exchange (credential injection) | Enforced | Proxy adds auth headers; agent cannot skip |
| Egress capture (proxy-init enforce-redirect) | Enforced | iptables in the pod network namespace redirect all TCP egress to the sidecar; non-TCP except DNS is dropped |
| HTTP_PROXY routing | Advisory | Agent *could* ignore env vars; enforce-redirect captures that traffic |

## How AuthBridge Protects End Users

When you send a message to an agent:

1. **Your identity enters the chain** — Your OAuth token is validated at the platform
   edge. The agent receives a request with your scoped identity attached.

2. **The agent cannot exceed your permissions** — When the agent calls a tool on your
   behalf, AuthBridge exchanges its workload identity for a token that reflects *your*
   authorization scope, not a blanket service account.

3. **Tool access is restricted** — The agent can only reach tools listed in its access
   policy. If the agent (due to hallucination or injection) tries to call an unauthorized
   service, AuthBridge blocks the request and returns a 403.

4. **Everything is logged** — Each token exchange, each allowed/denied request is
   recorded. The platform provides an audit trail of what was accessed and why.

5. **Credentials are ephemeral** — Tokens last seconds to minutes, not days. Even if
   intercepted, they're useless shortly after.

## Token Exchange (RFC 8693)

AuthBridge uses OAuth 2.0 Token Exchange to convert workload identity into
audience-scoped access tokens:

```
Agent's SPIFFE JWT-SVID                    Audience-scoped token
(proves "I am weather-agent               (grants access to
 in namespace team1")                       weather-api only, for 60s)
         │                                          ▲
         ▼                                          │
    ┌─────────────────────────────────────────────────┐
    │              Keycloak Token Exchange              │
    │                                                  │
    │  subject_token: agent's SVID                     │
    │  audience: weather-api                           │
    │  scope: read:forecast                            │
    │  → issues: short-lived token for weather-api     │
    └──────────────────────────────────────────────────┘
```

**Properties:**
- Tokens are audience-scoped: a token for `weather-api` cannot be used against `github-api`
- Tokens are short-lived: TTL of seconds to minutes
- The delegation chain is preserved: the token carries claims about the original user
- No admin credentials needed: the agent authenticates with its workload identity

## Workload Identity (SPIFFE/SPIRE)

Every agent pod receives a cryptographic identity without static secrets:

- **SPIFFE ID format:** `spiffe://rossoctl.io/ns/team1/sa/weather-agent`
- **Issued by SPIRE:** Hardware-attested, automatically rotated
- **Used for:** Authenticating to Keycloak for token exchange, mTLS in service mesh
- **No secrets in pods:** No client_secret, no API key, no password — just a short-lived
  JWT-SVID that proves workload identity

This eliminates the class of vulnerabilities where stolen credentials grant persistent
access. A SPIFFE SVID is valid only for the attested workload and expires quickly.

## Access Control

### Host-Based Tool Allowlists

Each agent has a route configuration specifying which external hosts it can reach:

```yaml
routes:
  rules:
    - host: "weather-api.example.com"
      target_audience: "weather-api"
    - host: "github.com"
      target_audience: "github"
```

Requests to unlisted hosts are blocked at the proxy. The agent receives a 403.

### Protocol-Aware Inspection (MCP / A2A)

AuthBridge's plugin pipeline can inspect request bodies for MCP and A2A protocol
traffic:

- **MCP parser** — extracts tool name, arguments, and resource URIs from JSON-RPC calls
- **A2A parser** — extracts session ID, message parts, and role from agent-to-agent requests
- **Guardrail plugins** — downstream plugins can evaluate whether a tool call aligns
  with the user's original intent (session-aware, multi-turn)

### Enforcement Layers

| Layer | What it enforces | Bypass resistant? |
|---|---|---|
| HTTP_PROXY routing | All outbound traffic goes through proxy | No (agent can ignore env vars) |
| Egress capture (proxy-init enforce-redirect) | iptables in the pod network namespace redirect all TCP egress to the sidecar; non-TCP except DNS is dropped | Yes, if the agent has no NET_ADMIN and does not run as UID 1337 |
| Token exchange | Only proxy can obtain tool tokens | Yes (requires workload identity) |
| Inbound JWT validation | Only authenticated callers reach the agent | Yes (proxy rejects) |

The combination of enforce-redirect + token exchange means that if an agent process
ignores HTTP_PROXY, its direct connections still go through the sidecar (the
`proxy-init` iptables rules redirect them to the sidecar transparent listener),
and it cannot forge credentials (only the proxy has the workload identity to
exchange tokens).

`egressEnforcement: enforce-redirect` is the default. The resolution order is:
the AgentRuntime CR, then the `egressEnforcement` key in the namespace ConfigMap
`authbridge-runtime-config`, then `enforce-redirect`. The operator Helm value
`allowedEgressEnforcement` limits the values that workloads can select. Only the
`proxy-init` init container has NET_ADMIN. The agent container needs no
privilege.

#### Why not NetworkPolicy

A Kubernetes NetworkPolicy selects pods, not containers. All containers in a pod
share one network namespace. Thus a NetworkPolicy cannot allow egress from the
`authbridge-proxy` sidecar and deny egress from the agent container. A policy
that denies external egress for the pod also blocks the sidecar.

#### `egressEnforcement: none`

Under `none`, the operator does not inject `proxy-init`, and there is no egress
enforcement. HTTP_PROXY routing is cooperative only: an agent that ignores the
env vars bypasses the proxy. This mode is for platforms without iptables (for
example ROSA HCP).

## Threat Model

### Attacks AuthBridge Prevents

| Attack | Mitigation |
|---|---|
| **Agent credential theft** | No credentials to steal — tokens are ephemeral and proxy-managed |
| **Privilege escalation via tool call** | Host allowlist + audience scoping prevent reaching unauthorized services |
| **Prompt injection → unauthorized access** | Even if the agent is tricked, the proxy enforces access policy |
| **Lateral movement** | Per-agent identity + per-service tokens limit blast radius |
| **Token replay** | Short TTL + audience binding make stolen tokens useless quickly |
| **Proxy bypass** | `proxy-init` enforce-redirect captures direct egress from the agent container and sends it through the sidecar |
| **Impersonation** | SPIFFE workload attestation ensures only the real agent gets its identity |
| **Admin credential compromise** | [Epic #1426] moving toward zero admin creds in agent namespaces |

### Attacks Outside Current Scope

| Attack | Status | Reference |
|---|---|---|
| TLS/HTTPS content inspection (MITM) | Under investigation | Proxy sees hostname but not request body for HTTPS |
| Intent-based access control | Experimental | Session store + guardrail plugins ([Epic #1458]) |
| LLM connection governance | Planned | Allowlisting which LLMs agents can reach |
| Event-driven agent identity | Planned | [Epic #1460] — CloudEvents origin verification |

## Further Reading

- [Identity in Agentic Platforms: Enabling Secure Least-Privilege Access](https://medium.com/rossoctl-the-agentic-platform/identity-in-agentic-platforms-enabling-secure-least-privilege-access-996527f1c983)
- [Security in and around MCP, Part 2: MCP in Deployment](https://medium.com/rossoctl-the-agentic-platform/security-in-and-around-mcp-part-2-mcp-in-deployment-65bdd0ba9dc6)
- [Security in and around MCP, Part 3: MCP Server Identity](https://medium.com/rossoctl-the-agentic-platform/security-in-and-around-mcp-part-3-mcp-server-identity-10d6768d96c1)
- [Rossoctl Identity Guide](../../security/index.md)
- [AuthBridge Architecture](https://github.com/rossoctl/cortex/blob/main/authbridge/README.md)
