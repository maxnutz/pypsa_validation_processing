# Specifications

This folder holds the specifications of `pypsa_validation_processing`. A spec states how the package is **intended** to behave; the code in `pypsa_validation_processing/` is one implementation of it.

## Spec vs. code
- Where spec and code disagree, **the spec wins**. The difference is recorded in [open_questions.md](open_questions.md) and becomes a GitHub issue.
- Specs are never weakened to match the code.
- Only the `spec-writer` role (`.claude/agents/spec-writer.md`) changes files in `specs/`. Spec PRs are titled `spec: …` and use `.github/PULL_REQUEST_TEMPLATE/spec.md`.

Source: `CLAUDE.md`, "Roles"; [constitution/principles.md](constitution/principles.md) P1, P3.

## Layout
```
specs/
├── README.md                     this file
├── initial_prompt.txt            kick-off prompt that created this scaffold (record only)
├── overview.md                   system context, data flow, components, glossary
├── contracts.md                  contracts C1–C11 between components
├── configuration.md              every config key: type, default, allowed values, effect, error
├── open_questions.md             open questions (OQ), spec-vs-code differences (SC), assumptions (A)
├── constitution/
│   ├── mission.md                purpose, users, problem, guiding principles, non-goals
│   ├── tech-stack.md             language, environment, libraries, testing, formatting, docs
│   ├── roadmap.md                phase format; phases derived from constitution/TODO.md (later)
│   └── principles.md             hard rules incl. fail-early rule and implementation source rule
├── templates/
│   └── statistics_function.md    template for one IAMC variable spec
└── variables/
    ├── README.md                 index of variable specs
    └── <function_name>.md        one spec per IAMC variable (later)
```

### Why `constitution/principles.md` exists
The kick-off asks for further constitution files only if needed. `principles.md` is needed because the hard rules (spec wins, no invention, function independence, fail early and loud) and the implementation source rule apply to *every* later spec and code change. Placing them in `mission.md` would mix requirements with motivation; repeating them in each spec would let copies diverge. `mission.md`, the template and `contracts.md` reference `principles.md` instead.

## Naming of spec files
- Variable specs: `specs/variables/<function_name>.md`, where `<function_name>` follows the naming convention of `README.md` ("Naming Convention"): `|` → `__`, space → `_`, other special characters removed.
  Example: `Final Energy [by Carrier]|Electricity` → `specs/variables/Final_Energy_by_Carrier__Electricity.md`.
- Other specs: lowercase, words separated by `_`, e.g. `specs/configuration.md`.

## Status values
Every spec file starts with a `Status:` line.

| Status | Meaning |
|---|---|
| `draft` | Written, not yet reviewed by the owner. Not a basis for implementation. |
| `reviewed` | Approved in a merged spec PR. Basis for implementation. |
| `implemented` | Code and tests satisfy all acceptance criteria; the implementing PR is linked in the spec. |

A spec moves back to `draft` when its requirements change.

## How to add a spec
1. Create a branch `spec/<topic>` from an up-to-date `main`.
2. For an IAMC variable: copy [templates/statistics_function.md](templates/statistics_function.md) to `specs/variables/<function_name>.md`, fill in every section and add a row to [variables/README.md](variables/README.md).
3. For other topics: add or extend a file and update the layout above.
4. Cite a source for every factual claim; mark open questions and assumptions explicitly ([constitution/principles.md](constitution/principles.md) P2).
5. Add new open questions and spec-vs-code differences to [open_questions.md](open_questions.md).
6. Commit only files under `specs/`; open a PR titled `spec: …` with the spec PR template.
