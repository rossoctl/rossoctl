---
name: docs:review
description: AI-assisted documentation review for Rossoctl PRs — structure, accuracy, links, conciseness
---

```mermaid
flowchart TD
    START([docs:review]) --> GATHER["Phase 1: Gather changed docs"]
    GATHER --> ANALYZE["Phase 2: Analyze each file"]
    ANALYZE --> REPORT["Phase 3: Report findings"]
    REPORT --> SUBMIT["Phase 4: Post review"]
```

> Follow this diagram as the workflow.

# Documentation Review

AI-assisted review of documentation changes in Rossoctl PRs. Checks structure,
accuracy, links, conciseness, and consistency against
[docs/_internal/docs-contributor-guide.md](../../../docs/_internal/docs-contributor-guide.md), the
authoritative standard, and the `meta:write-docs` skill that applies it. Use alongside the automated
`Docs CI` workflow (markdownlint, lychee) for comprehensive coverage.

## Table of Contents

- [When to Use](#when-to-use)
- [Phase 1: Gather Changed Docs](#phase-1-gather-changed-docs)
- [Phase 2: Analyze Each File](#phase-2-analyze-each-file)
- [Phase 3: Report Findings](#phase-3-report-findings)
- [Phase 4: Post Review](#phase-4-post-review)
- [Review Checklist](#review-checklist)
- [Related Skills](#related-skills)

## When to Use

- Reviewing a PR that adds or modifies `docs/**` or `*.md` files
- Validating documentation quality before merge
- Invoked as `/docs:review <PR-number>` or `/docs:review` (auto-detects current PR)

## Phase 1: Gather Changed Docs

```bash
export LOG_DIR=/tmp/rossoctl/docs-review/$PR_NUMBER
mkdir -p $LOG_DIR

# Get list of changed markdown files
gh pr diff <PR-number> --name-only | grep '\.md$' > $LOG_DIR/changed-files.txt

# Save the full diff for context
gh pr diff <PR-number> > $LOG_DIR/pr.diff 2>&1
```

If no `.md` files are changed, report "No documentation changes found" and stop.

## Phase 2: Analyze Each File

For each changed markdown file, read the full file and check against these
categories. Use subagents for large PRs (>5 files changed).

### 2.1 Structure

For a product page under `docs/<section>/`:

- [ ] Frontmatter has `title`, `description` and `sidebar_position`
- [ ] No `#` heading in the body (the frontmatter `title` provides it)
- [ ] No manual Table of Contents and no `---` rules between sections (Docusaurus builds the TOC)
- [ ] One-paragraph overview at the top, and it states what the reader gets
- [ ] The page is in the section that matches its reader
- [ ] Heading hierarchy is correct (no skipped levels like `##` to `####`)

For an internal document under `docs/_internal/`:

- [ ] Frontmatter has `draft: true`
- [ ] Single `#` title at the top, then a one-paragraph overview
- [ ] Table of Contents with working anchor links (required if >50 lines)

### 2.2 Accuracy

- [ ] Shell commands are syntactically valid and runnable
- [ ] YAML/JSON snippets are valid (check indentation, quoting)
- [ ] Version numbers match current releases (check `gh release list` output)
- [ ] File paths referenced actually exist in the repo (`ls` or `find` to verify)
- [ ] Environment variables and config keys match actual code
- [ ] Kubernetes resource names, namespaces, and labels are consistent with the codebase
- [ ] **Each claim agrees with the page it links to** — open the cited page and compare the wording
- [ ] No behavior from an unmerged issue is documented as released (or it carries a `VERIFY` comment)
- [ ] A Beta or Alpha feature carries a `:::warning` callout, and the default is stated
- [ ] Token counts and costs are scoped to a model call, and the cost is described as an estimate

### 2.3 Links

- [ ] Internal cross-references (`[text](../path.md)`) point to existing files
- [ ] Anchor links (`[text](#heading)`) resolve to actual headings in the target file
- [ ] External URLs are reachable (defer to lychee CI for exhaustive checking)
- [ ] No bare URLs — all links use `[descriptive text](url)` format

### 2.4 Conciseness

- [ ] No unnecessary prose — prefer bullets and tables over paragraphs
- [ ] No redundant sections that repeat information available elsewhere
- [ ] Code blocks include only the relevant fields, not entire manifests
- [ ] Steps are numbered when order matters, bulleted when it does not
- [ ] List items are 1-2 lines max

### 2.5 Consistency

- [ ] Terminology is consistent (e.g., "GA release" not mixed with "stable release" without definition)
- [ ] Component names match official naming (e.g., "AuthBridge" not "auth bridge" or "Auth-Bridge")
- [ ] Code block language tags are present and correct (`bash`, `yaml`, `text`)
- [ ] Callout style matches project convention: `:::note`, `:::warning`, `:::info`, `:::tip`
      (a blockquote is not a callout)
- [ ] ASD-STE100 prose: present tense, active voice, "you" not "we", no contraction, no "simply"
- [ ] No serial comma — the pages write "A, B and C"

## Phase 3: Report Findings

Produce a structured summary grouped by severity:

```markdown
## Documentation Review: PR #<number>

### Files reviewed
- `docs/getting-started/install.md` (modified)
- `docs/releasing.md` (new)

### Issues found

#### Must fix
- **docs/getting-started/install.md:42** — Broken anchor link `#choosing-a-version` (heading was renamed)
- **docs/releasing.md:15** — YAML snippet has incorrect indentation

#### Suggestions
- **docs/releasing.md:78** — This paragraph could be condensed to a bullet list
- **docs/getting-started/install.md:130** — Consider adding `git checkout` step to the OpenShift clone block

#### Looks good
- Structure follows the `meta:write-docs` template
- All shell commands are syntactically valid
- Version numbers match current releases
```

### Severity definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| **Must fix** | Broken links, invalid commands, incorrect information | Block merge |
| **Suggestion** | Style improvements, conciseness, missing context | Optional |
| **Looks good** | Positive observations worth noting | Informational |

## Phase 4: Post Review

Present the review to the user. If the user approves, post as a GitHub PR review:

```bash
# Post as a review comment (not inline, to avoid noise on large PRs)
gh pr review <PR-number> --comment --body "$(cat $LOG_DIR/review-summary.md)"
```

For critical issues, use `--request-changes` instead of `--comment`.

## Review Checklist

Quick reference for the complete review criteria:

- [ ] Title + overview paragraph present
- [ ] TOC with working anchors (if >50 lines)
- [ ] Section separators (`---`) between major sections
- [ ] Code blocks have language tags
- [ ] Commands are runnable
- [ ] YAML/JSON is valid
- [ ] Version numbers are current
- [ ] Internal links resolve
- [ ] No bare URLs
- [ ] Concise — no walls of text
- [ ] Consistent terminology
- [ ] Follows the contributor guide and `meta:write-docs` conventions

## Related Skills

- `meta:write-docs` — Documentation writing standards and templates
- `github-pr-review` — General PR review workflow (code + docs). Not bundled in this repo; import via `/plugin install github-pr-review@rossoctl-agent-skills`.
- `repo:pr` — PR creation conventions
