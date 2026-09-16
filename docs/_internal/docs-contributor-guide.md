---
draft: true       # excluded from https://www.rossoctl.dev/
description: How to add and change the pages under docs/. Where content lives, how to write a page, and what to check before you open a pull request.
---

# Documentation contributor guide

This guide tells you how to add and how to change the pages under `docs/`. It is for a code
contributor and for a documentation contributor. It is the authoritative source for the rules below.

A coding agent reads the same rules through the `meta:write-docs` skill. The skill points to this
file. Change this file first, and the agent follows.

## The two documentation sets

The repository holds two sets of Markdown. Each set has different rules. Find your set before you
write.

| Set | Location | Reader | Published to rossoctl.dev | Rules |
| --- | --- | --- | --- | --- |
| **Product documentation** | `docs/<section>/` | A user of Rossoctl | Yes | This guide. Docusaurus frontmatter. No `#` title in the body. |
| **Internal documentation** | `docs/_internal/` | A contributor or a maintainer | No | Add `draft: true` to the frontmatter. Start the body with a `#` title. |

Everything below applies to the product documentation, unless a rule names `docs/_internal/`.

## Where content lives

Each section has one reader and one purpose. Put your page in the section that matches your reader.

| Section | Reader | What goes there |
| --- | --- | --- |
| `docs/get-started/` | A new user | A numbered procedure that gives a result in one sitting. |
| `docs/concepts/core/` | A user who asks how Rossoctl works | An explanation of a component that is Ready. |
| `docs/concepts/experiments/` | A user who evaluates a feature | An explanation of a feature that is Beta or Alpha. |
| `docs/workloads/` | A developer with agent code | How to put an agent or a tool on the platform. |
| `docs/security/` | A security reviewer | What the platform enforces, and where. |
| `docs/operate/` | A platform engineer | Installation, observability and diagnosis. |
| `docs/reference/` | A user who looks for one fact | A command, a field, a term. |

Files that are not pages:

| Content | Location |
| --- | --- |
| Screenshots, and diagrams from draw.io | `docs/images/` |
| Hand-authored SVG diagrams | `docs/images/`. See [SVG diagram style guide](./svg-diagram-style-guide.md). |
| Mermaid source, and the generated PNG | `docs/diagrams/`. See [CONTRIBUTING.md](../../CONTRIBUTING.md#diagrams). |
| A term that more than one page uses | `docs/reference/glossary.md` |

## Decide where your change goes

Use the first rule that applies.

1. **A page covers the subject.** Change that page. Do not add a second page for the same subject.
2. **No page covers the subject, and a section fits.** Add a page to that section. Give it a
   `sidebar_position` that puts it in reading order.
3. **The feature is an experiment.** Add the page to `docs/concepts/experiments/`. Add a row to the
   table in `docs/concepts/index.md`, with the status Beta or Alpha. Start the page with a
   `:::warning Alpha` callout.
4. **No section fits.** Open an issue. Do not add a section in the pull request. A new section needs a
   maintainer, an `_category_.json` file and a position for each other section.

### If a section is missing and you cannot write it

Open an issue. Give three facts:

- The reader, from [PERSONAS_AND_ROLES.md](../../PERSONAS_AND_ROLES.md).
- The question that the reader asks.
- The page, or the section, that must hold the answer.

Do not put a `TODO` in a page, and do not publish an empty heading. A reader who finds an empty
section reads it as an error in the product.

## Frontmatter

Every page under `docs/<section>/` starts with frontmatter.

```markdown
---
title: RossoCortex
description: See and understand what your AI agent sends — every model, tool and API call.
sidebar_position: 3
---
```

| Key | Required | Rule |
| --- | --- | --- |
| `title` | Yes | The name of the page. The body has no `#` heading, because the title comes from this key. |
| `description` | Yes | One sentence. Say what the reader gets, not what the component is. |
| `sidebar_position` | Yes | The reading order inside the section. |
| `sidebar_label` | No | A shorter title for the sidebar. Use it when the title is long. |

## How to write

The pages follow ASD-STE100 (Simplified Technical English). The rules below are the rules that the
current pages keep. A reader who does not read English as a first language reads these pages, and a
translation tool reads them also.

- **One instruction in one sentence.** Keep a sentence to approximately 20 words.
- **Use the present tense.** Write "RossoCortex removes the definitions", not "will remove".
- **Use the active voice.** Write "The operator injects the sidecar", not "the sidecar is injected".
- **Write to the reader as "you".** Do not write "we".
- **Use one word for one meaning.** A tool is a tool on each page, not a "utility" or a "plugin".
- **Do not use a contraction.** Write "do not", not "don't".
- **Say what a thing does, and what it does not do.** A limit is information, not a weakness.

| Do not write | Write |
| --- | --- |
| Simply install the CLI. | Install the CLI. |
| Please note that the cost is an estimate. | The cost is an estimate. |
| It's easy to see the traffic. | `abctl observe` shows the traffic. |
| This will allow you to reduce tokens. | Two experimental plugins reduce the tokens. |
| We recommend a sidecar. | Use a sidecar on Kubernetes. |

### Callouts

Use a Docusaurus callout. Do not use a blockquote for a callout.

| Callout | Use |
| --- | --- |
| `:::note` | Information that the reader can skip. |
| `:::warning Alpha` | The maturity of a feature, and a risk. |
| `:::info` | A reference to a different page. |
| `:::tip` | A shorter method that gives the same result. |

### Headings

- Use a sentence, and capitalize the first word only: `## Before you start`.
- Number a procedure: `## Step 1: install the program`.
- Do not repeat the title of the page in the first heading.

## Accuracy rules

A wrong claim costs a reader more time than a missing page. Keep these four rules.

1. **A claim must agree with the page that it links to.** Read the target page, and use its words. In
   [#2564](https://github.com/rossoctl/rossoctl/pull/2564), a new introduction promised data on disk
   and a deletion command, and the page that it cited said the opposite.
2. **Do not document behaviour that is not released.** If a claim depends on an open issue, add a
   comment for the release that must confirm it:

   ```markdown
   <!-- VERIFY v0.9.0: confirm the local-only claim once persistence (#901, sqlite) lands. -->
   ```

3. **Give the maturity, and give the default.** A Beta or an Alpha feature needs a `:::warning`
   callout. If a plugin is off by default, write "off by default". See the maturity table in
   `docs/concepts/index.md`.
4. **Show the output that the reader sees.** Copy it from a terminal. Do not write it from memory.

## Links

- Link to a page with a relative path, and keep the `.md` extension:
  `[Read the numbers](../get-started/reading-the-numbers.md)`.
- An anchor is the heading in lower case, with a hyphen for each space: `#the-plugin-chain`.
- Open the target page and confirm that the heading is present. A heading changes more often than a
  file name.
- Give each link descriptive text. Do not write "here" or "this page".

## Page templates

### Task page, for `docs/get-started/` and `docs/workloads/`

````markdown
---
title: <Do the task>
description: <The result that the reader gets.>
sidebar_position: <n>
---

<One paragraph: the result, and the time that the task needs.>

## Before you start

You need:

- <A prerequisite.>

## Step 1: <do the first action>

```bash
<one command>
```

<What the command changes.>

## Step 2: <do the second action>

## Next

- [<The page that follows>](<path>.md)
````

### Concept page, for `docs/concepts/`

```markdown
---
title: <Component>
description: <What the reader gets from the component.>
sidebar_position: <n>
---

<One paragraph: what the component gives the reader. Not the architecture.>

## What you get

- **<A benefit>.** <One sentence.> See [<the detailed page>](<path>.md).

## Install it

<A pointer to the procedure. Do not repeat the procedure.>

## How it works

<The architecture. This is optional depth for the reader who wants it.>

## What <component> does not do

- <A limit.>

## Related pages

- [<A page>](<path>.md) <what it adds.>
```

### Experiment page, for `docs/concepts/experiments/`

```markdown
---
title: <Feature>
description: <What the feature does.>
sidebar_position: <n>
---

<One paragraph: the problem, then the feature.>

:::warning Alpha
This feature is an experiment. The behaviour and the configuration will change.
:::

## The problem that it solves

## How it operates

## How to enable it

## What it does not do
```

### Reference page, for `docs/reference/`

```markdown
---
title: <Command or resource>
description: <What the reader finds here.>
sidebar_position: <n>
---

<One sentence: the scope of the page.>

| <Name> | <Default> | <What it does> |
| --- | --- | --- |
```

## Check your change

Run both checks before you open the pull request. The Docs CI workflow runs the same two tools.

```bash
# 1. Markdown lint, with the configuration of the repository
npx markdownlint-cli2 "docs/**/*.md"

# 2. Relative links in the files that you changed.
#    Install lychee first: brew install lychee (or cargo install lychee)
lychee --offline --config .lychee.toml \
  $(git diff --name-only --diff-filter=d main...HEAD -- '*.md')
```

The link check gates the files that your pull request changes. A broken relative link in a changed
file fails the job.

`.lychee.toml` excludes `docs/_internal/` and `.claude/`. A link in one of those files is not gated,
so open each target and confirm it by hand.

## Checklist

- [ ] The page is in the section that matches the reader.
- [ ] The frontmatter has `title`, `description` and `sidebar_position`.
- [ ] The body has no `#` heading.
- [ ] Each claim agrees with the page that it links to.
- [ ] A Beta or an Alpha feature has a `:::warning` callout, and the default is stated.
- [ ] Each link and each anchor resolves.
- [ ] Each code block has a language tag, and each command runs.
- [ ] `markdownlint-cli2` reports 0 issues.
- [ ] The pull request states the tier. A documentation-only change is Tier 0. See
      [FEATURE_ACCEPTANCE.md](../../FEATURE_ACCEPTANCE.md).
- [ ] Each commit has a DCO sign-off: `git commit -s`.

## Related pages

- [CONTRIBUTING.md](../../CONTRIBUTING.md) gives the pull request process.
- [FEATURE_ACCEPTANCE.md](../../FEATURE_ACCEPTANCE.md) gives the documentation requirement for each
  tier, in Pillar 2.
- [PERSONAS_AND_ROLES.md](../../PERSONAS_AND_ROLES.md) gives each reader.
- [SVG diagram style guide](./svg-diagram-style-guide.md) gives the rules for a hand-authored diagram.
- The `meta:write-docs` skill gives these rules to a coding agent.
- The `docs:review` skill reviews a documentation pull request.
