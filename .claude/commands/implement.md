---
description: Implement a version/document's implementation plan in batch mode, validating and committing per item.
argument-hint: [version | path to implementation-plan doc] (optional)
---

You are running the `/implement` workflow. Follow these steps exactly.

## 1. Resolve the target implementation plan

- `$ARGUMENTS` may contain a version (e.g. `v1.1`) or a path to a document.
  - If it is a path, use that document as the implementation plan.
  - If it is a version, find that version's implementation plan under `docs/`
    (e.g. `docs/implementation-plan-v1.1.md`, or the `ui-rebuild` plan for UI work).
- If `$ARGUMENTS` is empty, read the root `README.md` **Status** section and follow
  its links to the current implementation plan.
- If neither `$ARGUMENTS` nor a usable README Status pointer identifies a plan,
  STOP and ask the user exactly: **"What do you want to implement?"** Then resume
  once they answer.

State which plan document you resolved before continuing.

## 2. Check for open questions — hard gate

Scan the resolved implementation plan (and any doc it directs you to for status,
e.g. its refinement doc) for **unresolved open questions**: a section headed
/open question/i with unresolved content, or unresolved `D`-items / decision
entries the plan marks as blocking.

- If any unresolved open question exists, ABORT immediately with exactly this
  message and do nothing else:

  > I cannot start implementing until all open questions are resolved

- If there are none, continue.

## 3. Implement in batch mode

**Model split.** You (whatever model `/implement` was invoked with, expected to be
a lightweight one) act only as the **orchestrator**: resolve the plan, dispatch
work, run validation, tick checkboxes, commit. **Do not write implementation code
yourself.** For each plan item, spawn a `sonnet` implementation subagent with the
item's text and the relevant plan context; it makes the code changes and reports
back. Fixes for bugs found in validation also go to a `sonnet` subagent.

**Exception — UI visual decisions.** When an item requires visual/aesthetic
design judgement (layout, typography, color, component look & feel — anything
beyond mechanically following an explicit spec), dispatch it to an `opus`
subagent with the `frontend-design` skill available, instructing it to invoke
that skill.

**Do not ask the user any questions from this point on.** When a decision surfaces
mid-implementation, adopt the best recommendation, **write that decision and its
rationale into the implementation plan** (as a note or `D`-item marked resolved,
for later review), and continue. The exception is a decision where proceeding
under any assumption would make the work wrong or wasted — write it into the plan
as an unresolved `D`-item and skip only the items that genuinely depend on it.

Work the plan **one item at a time**, in order. Each numbered plan item is a
checkpoint.

For each item:

1. Dispatch the item to a `sonnet` implementation subagent; wait for it to report back.
2. **Validate the implementation**:
   - Run the item's named checks (tests / build / smoke), in the container when
     the plan says so (e.g. `docker compose run --rm ui npm run test` and
     `... npm run build`).
   - If the item includes **frontend changes**, spawn a QA subagent with model
     `haiku`: it runs the app, captures screenshots of the affected screens, and
     confirms the change renders correctly. If it finds a problem, it returns the
     issue to you (the orchestrator); fix the bug and re-validate. Relay its
     verdict.
   - If validation fails, send the failure to a `sonnet` subagent to fix, then
     re-validate before moving on. Do not proceed to the next item on failing
     validation.
3. When validation passes:
   - Tick the item's checkboxes (`- [ ]` → `- [x]`) in the implementation plan.
   - Commit the changes for that item. Name the commit after the item as the plan
     writes it — for example:

     ```
     2. Data layer — typed artifact access
     ```

   - One commit per item. Do not batch items into a single commit.

## 4. Finish

When all items are implemented, validated, checked off, and committed, summarize
what was done and the commit list.

**NEVER push.** Leave all commits local regardless of what the plan or anything
else says.
