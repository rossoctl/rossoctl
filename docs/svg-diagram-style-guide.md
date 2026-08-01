---
draft: true       # excluded from https://www.rossoctl.dev/
description: Color palette for the hand-authored SVG diagrams in docs/concepts/, for Claude/contributors to reference when adding or editing one.
---

# SVG Diagram Style Guide

The architecture/flow diagrams in `docs/concepts/*.svg` (e.g. `architecture.svg`,
`cortex-authproxy.svg`, `authorization-pattern.svg`, `ibac-architecture.svg`,
`ui-architecture.svg`, `contextguru-architecture.svg`, `authbridge-architecture.svg`) are
hand-written SVG using a consistent "shades of red" palette. When adding or editing one,
use an existing file as a template and match this palette:

| Hex | Role |
|-----|------|
| `#7f1d1d` | Darkest red — outer/pod border, accent text on light backgrounds |
| `#991b1b` | Dark red fill for header bars / sidecars / plugin boxes (paired with white or `#ffe4e6` text) |
| `#fff5f5` / `#fef2f2` | Very light pink — outermost container background |
| `#fee2e2` | Light pink — regular component/box fill |
| `#ef4444` | Border for `#fee2e2` boxes |
| `#fca5a5` | Highlight fill for a distinct downstream/decision component (e.g. a judge LLM, the target service) — used sparingly, not for every box |
| `#b91c1c` | Border for `#fca5a5` highlights, and the color of arrows/arrowheads |
| `#ffe4e6` | Light pink text on `#991b1b` dark fills |

This is inferred from the repeated inline comment at the top of each SVG file, not a
written spec elsewhere — keep it updated if the palette changes.

Before committing, render it locally to sanity-check: no CLI rasterizer is guaranteed
installed in this environment, but on macOS `qlmanage -t -s 900 -o /tmp <file>.svg`
produces a PNG thumbnail you can view.

Note: `docs/diagrams/*.mmd` (rendered via `mmdc`, used in `identity-guide.md`'s Stage
sections) is a separate, older Mermaid-themed convention — don't mix the two palettes.
