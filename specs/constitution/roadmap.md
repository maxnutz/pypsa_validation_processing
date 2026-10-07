# Roadmap

Status: draft (structure only)

## Basis
The roadmap MUST be derived from `specs/constitution/TODO.md`.

> **Note:** `TODO.md` does not exist yet. It is created in a separate step from the existing GitHub issues and is not part of the kick-off scaffold. Until then, this file contains no phases.

## Rules
- Phases are very small, incremental units of work (`CLAUDE.md`, "Working Principles": no big-bang changes).
- Every phase MUST reference the `TODO.md` items (and their GitHub issues) it includes.
- A phase that implements a statistics function MUST depend on an approved (`reviewed`) variable spec in `specs/variables/`.
- Phase order follows the dependencies; phases without mutual dependencies MAY run in parallel.
- A phase is done only if all its done criteria are met and checked against the PR readiness checklist in `CLAUDE.md`.

## Phase format
Copy this block for every phase.

```markdown
### Phase <n>: <short title>
- **Goal:** <one sentence: what is true after this phase>
- **Included items:** <TODO.md items / GitHub issues, e.g. `TODO.md#<anchor>` (#<issue>)>
- **Done criteria:**
  - [ ] <testable criterion, e.g. acceptance criteria of specs/variables/<function>.md covered by tests>
  - [ ] `pixi run test` passes
  - [ ] `pixi run workflow_test` passes
- **Dependencies:** <phases or specs that must be finished first, or "none">
```

## Phases
_None yet. Filled in after `TODO.md` exists._
