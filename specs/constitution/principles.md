# Principles

Status: draft

Hard rules for all specs and code changes. Contracts in [contracts.md](../contracts.md) refine them.

## P1 Spec wins
A spec states intended behaviour; code is one implementation of it. Where they disagree, the spec wins and the difference is recorded in [open_questions.md](../open_questions.md) and becomes a GitHub issue. Specs MUST NOT be weakened to match code. Source: `CLAUDE.md`, "Roles".

## P2 No invention, cite sources
Specs and code MUST NOT invent datasets, files, APIs, carriers, config keys or IAMC variables. Every factual claim in a spec MUST cite its source (file path + symbol/line, definition file, or doc URL). Assumptions and open questions MUST be marked explicitly (`> **Open question:** …`, `> **Assumption:** …`). Source: `CLAUDE.md`, "Forbidden Actions".

## P3 Roles
- Only the `spec-writer` changes `specs/`; the `developer` never does (`CLAUDE.md`, "Roles").
- Definitions in `sister_packages/energy-scenarios-at-workflow/definitions/` are out of scope and MUST NEVER be changed (owner decision, kick-off review).
- Files in `pypsa_validation_processing/configs/` MUST be changed only on explicit request, or temporarily for testing purposes; temporary test changes MUST NOT be committed (owner decision, kick-off review; `CLAUDE.md`, "Forbidden Actions").

## P4 Function independence
Statistics functions MUST NOT call or import each other. Shared logic MUST live in `pypsa_validation_processing/utils.py`; `utils.py` MUST NOT call statistics functions. Statistics functions MUST NOT aggregate to country level. Details: contracts C5–C7. Source: `CLAUDE.md`, "Function Architecture (Critical)".

## P5 Fail early and loud
Decision of the owner (kick-off review, 2026-10-07).
- **Early:** Problems MUST be detected at the earliest possible stage. Everything that can be checked from config, mapping file, definitions and the results folder MUST be checked during initialisation of `Network_Processor`, before any network is evaluated.
- **Loud:** Every detected problem MUST either raise an exception or be logged at level `WARNING` or higher, naming the affected variable, function or file. Silent fallbacks (e.g. replacing an unknown unit by NaN or a default unit) are not allowed.
- **Abort vs. skip:**
  - A problem that makes the whole run invalid (invalid or missing required config, missing results or definitions folder) MUST raise an exception.
  - A variable that **cannot be run** (its mapped function is missing, or special input data it needs, such as `energy_totals.csv`, is not available) MUST log a `WARNING` and be skipped; all other variables MUST still be evaluated. This is the only case in which a variable is skipped.
  - A variable that is run but produces an **invalid result** (contract C6) MUST abort the run with an exception naming the variable, because the result would otherwise be silently wrong.

## P6 Implementation source rule
For every statistics function the implementation source is chosen in this order:

1. **Exact match.** If `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` evaluates the same IAMC variable, the statistics function MUST port that pypsa-de logic as-is: same components, carriers, bus carriers, sign conventions and special cases.
2. **Semantic match.** If the pypsa-de variable name differs (naming or hierarchy) but the meaning is the same, rule 1 applies. The variable spec MUST name the pypsa-de variable and function (with line range) and justify why they match.
3. **No match.** Only if no matching variable exists in `export_ariadne_variables.py` is the function built with the `pypsa.statistics` accessor (https://docs.pypsa.org/latest/api/networks/statistics/).

The ported logic is changed only as far as needed to fit the function contract: stand-alone function, shared helpers only in `utils.py` (P4), return format of C6, no country aggregation inside the function. Every such change MUST be listed in the variable spec.

This rule takes precedence over the general hint in `CLAUDE.md` ("Blueprint": "use `pypsa.statistics` more extensively"). The conflict is recorded as SC-14 in [open_questions.md](../open_questions.md) so `CLAUDE.md` can be aligned.

## P7 Requirement language
Specs use MUST / SHOULD / MAY (RFC 2119 meaning). Acceptance criteria MUST be concrete enough to become unit tests in `tests/`.

## P8 Small steps
Changes are incremental and touch only what is needed (`CLAUDE.md`, "Working Principles").
