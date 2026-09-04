---
description: Small, scoped change end-to-end — plan inline, implement, smoke test, review, document, commit.
argument-hint: [description of the small change]
---

# /quick-fix

A tight loop for **one small, well-scoped change** — a bug fix, a tweak, a
small addition someone can describe in a sentence. This is deliberately the
lightweight counterpart to `/spec-doc` + `/implement`: no refinement document,
no implementation-plan folder. If the request grows into something that needs
either while you're working it, say so and suggest switching — don't force a
multi-day feature through this loop.

Follow the steps below in order for `$ARGUMENTS` (if empty, ask what the
change is before step 1). Don't skip ahead, and don't silently merge steps.

## 1. Plan in-memory

State the plan directly in the conversation: which files you expect to touch
and what changes in each. **Do not create a refinement document, an
implementation plan, or any new file under `docs/` at this stage** — the plan
lives only in the chat and is thrown away once implemented. Keep it short.

If the requirement turns out to be too big for this loop — ballooning past a
handful of files, or past a single clear idea — stop before step 2. Give a
short TLDR of *why* it's too big (not just "this is big"), then ask the user
to choose: **confirm anyway** (proceed through this loop despite the size) or
**switch to a regular `/spec-doc` session** for it instead. Don't decide this
unilaterally in either direction.

## 2. Ask: fold in more, or implement now?

Before writing any code, ask the user (AskUserQuestion or equivalent) to
choose:

- **a) add another quick change** to the same plan — loop back to step 1 and
  extend it, or
- **b) implement** what's planned so far.

## 3. Implement + smoke test

Implement using the **Sonnet** model. If the current session is already
running as Sonnet, just write the code directly. If it's running as a
different model (e.g. this loop was reached from an Opus planning session),
delegate the actual code-writing to a Sonnet subagent (the Agent tool,
`model: "sonnet"`) rather than implementing it on the current model — this
mirrors the user's standing planner/implementer split: heavier-reasoning
models plan and review, Sonnet writes the code.

Then run a smoke test scoped to what changed, using this
repo's Docker services — never host-installed tooling (CLAUDE.md "Docker
only"):

- UI (`ui/`) changes: `docker compose run --rm --no-deps --entrypoint sh ui -c
  "npm run build && npm test"` at minimum; if the change is visual, consider
  whether the Playwright visual-regression suite
  (`docs/reference/ui-regression_guide.md`) needs a run too.
- Analyzer (`src/`) changes: `docker compose run --rm test`, or the narrower
  `--stage` invocation from `docs/reference/phase_1_validation_cli.md` if only
  one stage is touched.
- MCP server changes: whatever this repo's MCP test entry point is — check
  `mcp/` for its own README/scripts before assuming.

Fix any breakage before moving on. Don't count a build-only pass as a smoke
test if the project has real tests to run.

## 4. Ask for review

Report what changed and the smoke-test result, then ask the user to look at
the actual behavior (running app, rendered UI, analyzer output — whatever
fits) before it's considered done. Do not proceed to step 5 until they
confirm. If they ask for a revision, loop back to step 3 (or step 1, if the
shape of the change needs to change).

## 5. Update the spec docs — as current definition, not a refinement entry

Once confirmed, edit the *current* spec docs that describe this behavior
directly in place — e.g. `docs/reference/ui_development.md`,
`docs/reference/ui-regression_guide.md`, `docs/data_folder_reference.md`, or
the analogous analyzer/MCP doc. This is a **definition update**: the doc
should read as if it always described the shipped behavior, not as a dated
changelog entry. Follow the repo's standing doc rules (`CLAUDE.md`,
`docs/constitution.md`): `docs/` holds current material only, delete or
rewrite a section that's now wrong rather than appending a correction beside
it, and never invent a new archive folder. Do not write this into
`docs/experiments_pending.md` or a `product-refinement-vX.Y.md` — those are
for different-shaped work (experiments, and larger refinement-tracked
features), not this loop.

## 6. Commit

Before staging, run `git status` and `git diff` and check the result against
what this quick-fix actually touched — exclude anything changed by something
else in the working tree (another session, an unrelated in-flight edit) even
if it's sitting right next to your files. Stage exactly your files. Commit on
the current branch (don't create a new one unless asked) with a message
titled:

```
[quick-fix] <short, specific title>
```

followed by a short body if the change needs one line more than the title
gives it.

## 7. Restart or close

Ask whether to start another quick-fix now (loop back to step 1) or close out
the session here.
