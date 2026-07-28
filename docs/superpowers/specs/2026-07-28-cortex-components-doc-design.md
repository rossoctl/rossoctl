# Cortex Component Documentation Redesign

Date: 2026-07-28
Status: Approved design, implemented in the same PR as this spec
Target file: `docs/Concepts/components.md` (source of truth in `rossoctl/rossoctl`; the
docs site at rossoctl.dev mirrors this repo at build time via `scripts/sync-docs.sh`)

## Problem

The components page at `/docs/Concepts/components#identity--auth-bridge` documents the
platform's security layer under the heading **"Identity & Auth Bridge"**. Two problems:

1. **Stale, inconsistent naming.** The `kagenti-extensions` repo was renamed to
   **`cortex`** (`rossoctl/cortex`). The newer concept pages already adopt the new
   model, opening with "X is a **Rossoctl Cortex** plugin..." (see `ibac-plugin.md`,
   `sparc-plugin.md`). But `components.md` still uses the pre-rename framing:
   **AuthBridge** as the umbrella term, and confusingly uses **"Cortex"** as a
   sub-heading for the AuthProxy *sidecar*. The page contradicts its siblings.

2. **Too low-level.** The section leans on implementation detail (Envoy sidecar,
   ext-proc, iptables interception, JWT env vars) that will change as the security
   layer evolves toward pluggable technologies.

## Decision

Rewrite the "Identity & Auth Bridge" section of `components.md` as a single unified
component called **Cortex**, framed by durable security *capabilities* and the
*technologies* that deliver them, at a higher conceptual level.

### Framing rules (agreed)

- **Retire the name "AuthBridge"** from this page entirely. It is being superseded by
  Cortex. Where mechanics read "AuthBridge does X", they become "Cortex does X" or are
  removed.
- **No "plugin interface" / pipeline / sidecar mechanism language.** How Cortex is
  wired is an implementation detail that may change; the docs stay at the capability
  level.
- **Cortex is Rossoctl's security layer** for agentic systems: trusted identity,
  authentication, secure delegation (token exchange), client registration, access
  control, and guardrails for agents and tools.
- **CPEX, Praxis, IBAC, SPARC** are presented as the **technologies Cortex uses/supports**
  to deliver those capabilities, framed as an evolving set with room for emerging ones.
- The durable concepts (SPIFFE/SPIRE identity, token exchange, client registration,
  access control) stay constant regardless of which technology implements them.

### Scope boundary

- **This change edits `docs/Concepts/components.md` only.**
- Other files that still say "AuthBridge" (repo `README.md` component table,
  `docs/Concepts/identity-guide.md`, and any others) are **out of scope** and listed as
  follow-ups below. Do not touch them in this change.

## New section structure (Proposal A — approved)

Replaces current lines 478–616. Anatomy:

```
## Cortex

**Repository:** rossoctl/cortex

[Intro, 1–2 sentences: Cortex is Rossoctl's security layer for agentic systems. It gives
 agents and tools a trusted identity and enforces authentication, secure delegation, and
 safe behavior at every hop, replacing static credentials with dynamic, short-lived,
 audience-scoped tokens.]

### What Cortex provides   (functional capabilities — durable concepts)
| Capability          | Description |
|---------------------|-------------|
| Trusted Identity    | SPIFFE/SPIRE workload identities (SVIDs) and attestation |
| Authentication      | Inbound token validation — signature, issuer, and audience |
| Secure Delegation   | OAuth2 Token Exchange (RFC 8693) with audience scoping |
| Client Registration | Automated Keycloak client provisioning per workload |
| Access Control      | Policy-driven allow/deny on agent and tool actions |
| Guardrails          | Content and behavior safety enforcement |

### Technologies Cortex supports   (the "how" — evolving set)
| Technology | Role | Status |
|------------|------|--------|
| CPEX  | Policy orchestration and access control (APL policy DSL, Cedar/OPA PDPs, composable effects) | Supported |
| IBAC  | Intent-Based Access Control — denies actions that don't match the user's declared intent | Supported (see IBAC page) |
| SPARC | Pre-tool reflection — catches hallucinated / ungrounded tool calls before they execute | Supported (see SPARC page) |
| Praxis | — | Emerging / planned |

[Note line: the set of supported technologies grows over time; the identity, delegation,
 and access-control concepts above stay constant.]

### Foundation
- **SPIRE** — workload identity (SVIDs, attestation). Identity format
  `spiffe://<trust-domain>/ns/<namespace>/sa/<service-account>`.
- **Keycloak** — identity provider, OAuth/OIDC flows, token exchange, SSO.

### Authorization Pattern
[Keep authorization-pattern.svg (User → Keycloak → Agent → Tool, each backed by
 short-lived SPIRE identities). Reword surrounding prose to drop AuthBridge/sidecar terms.
 Keep the four security properties: no static secrets, short-lived tokens, audience
 scoping, transparent to the application.]

[Link to the Identity Guide for the deep dive.]
```

### Content sourcing notes (accuracy)

- **CPEX** description grounded in `cortex/authbridge/authlib/plugins/cpex/README.md` and
  `docs/cpex-plugin.md`: CPEX orchestrates policy for agentic entities, using an APL
  policy DSL, Cedar/OPA PDPs, and composable effects. Link:
  `https://github.com/contextforge-org/cpex`.
- **IBAC / SPARC** descriptions grounded in the existing `docs/Concepts/ibac-plugin.md`
  and `docs/Concepts/sparc-plugin.md`; link to those pages rather than restating detail.
- **Praxis** — list only, marked "Emerging / planned", no invented capability description.
- **Client Registration** is handled by the `rossoctl-operator`'s
  `ClientRegistrationReconciler` (uses SPIFFE ID as client identifier). Describe the
  outcome (automated per-workload client provisioning), not the reconciler mechanics.

## Same-page consistency edits (all within components.md)

| Location | Current | Change |
|----------|---------|--------|
| Line 16 (TOC) | `- [Identity & Auth Bridge](#identity--auth-bridge)` | `- [Cortex](#cortex)` |
| Line 188 (comment in AgentRuntime YAML) | `# ... triggers AuthBridge sidecar injection automatically.` | Reword to drop the retired name and the mechanism detail: `# ... enrolls the workload with Cortex automatically.` |
| Lines 478–616 (section) | "Identity & Auth Bridge" section | Replaced with the Cortex structure above |
| Line 724 (Related Documentation) | `- [Identity, Security, and Auth Bridge](./identity-guide.md)` | `- [Cortex Identity Guide](./identity-guide.md)` |

### Diagrams

- **Keep** `authorization-pattern.svg` (embedded in the Authorization Pattern subsection);
  reword surrounding prose only.
- **Remove** the `cortex-authproxy.svg` embed and its ASCII-art source comment (current
  lines ~508–541): it depicts the Envoy AuthProxy sidecar with inbound/outbound ext-proc
  mechanics — exactly the implementation detail to de-emphasize. The SVG file stays on
  disk (not deleted) in case history or other pages reference it; it is simply no longer
  embedded on this page.

### Anchor change caveat

The section anchor changes from `#identity--auth-bridge` to `#cortex`. Docusaurus does
not auto-redirect heading anchors. The only in-repo link to the old anchor is the TOC
entry in this same file (updated above). External bookmarks to the old anchor will break;
this is accepted.

## Out of scope (follow-ups, do NOT edit in this change)

- Repo `README.md`: "Identity & Auth Bridge" row in the components table (line ~7 area)
  still points at `./docs/identity-guide.md` and uses the old name.
- `docs/Concepts/identity-guide.md`: still contains "AuthBridge" references; the H1 is
  being changed to "Cortex" separately in PR #2300.
- Any other `docs/` pages containing "AuthBridge" — sweep in a later dedicated change.

## Success criteria

1. `components.md` has a single **Cortex** component section; the word "AuthBridge" no
   longer appears anywhere on the page.
2. The section leads with functional capabilities and presents CPEX/IBAC/SPARC as
   supported technologies plus Praxis as emerging, with no plugin-interface/sidecar
   mechanism language.
3. TOC, Related Documentation, and the stray YAML comment are consistent with the rename.
4. The `authorization-pattern.svg` diagram remains; the `cortex-authproxy.svg` embed is
   removed.
5. Markdown Lint (`.markdownlint-cli2.yaml`, MD049 underscore emphasis, MD056 table
   columns) passes on the changed file; internal links resolve.

## Verification plan

- Run repo `markdownlint-cli2` on `docs/Concepts/components.md`.
- Grep the file to confirm zero "AuthBridge" / "Auth Bridge" occurrences remain.
- Confirm the new capability and technology tables have correct column counts (MD056).
- Confirm all in-section links (identity-guide, IBAC page, SPARC page, CPEX repo) resolve.
