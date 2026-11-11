# Principles

Status: reviewed; draft (P6 rules 1 and 4)

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
  - A **configuration error** MUST raise an exception during initialisation: invalid or missing required config, missing results, definitions or mapping file, a mapped function that does not exist or has a non-conforming signature (C4, C5).
  - A variable that **cannot be run because special input data is not available** (e.g. `energy_totals.csv`) MUST log a `WARNING` and be skipped; all other variables MUST still be evaluated. This is the only case in which a variable is skipped.
  - A variable that is run but produces a **structurally invalid result** (contract C6) MUST abort the run with an exception naming the variable. Values that are all zero or all NaN are not a structural error.

## P6 Implementation source rule
For every statistics function the implementation source is chosen in this order:

1. **Exact match.** If `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` evaluates the same IAMC variable, the statistics function MUST port that pypsa-de logic as-is: same components, carriers, bus carriers, sign conventions and special cases. Exceptions: rule 4; the adaptations to the function contract (last paragraph of this section); and deviations decided by the owner. Each exception except rule 4 MUST be listed in the variable spec (section 4) with its reason and the owner decision (date, PR) (owner, PR #175 review 2026-11-11). Examples: the `V2G` subtraction in `Final Energy [by Carrier]|Electricity` and `…|Transportation`; marginal instead of cost-based prices in D9.
2. **Semantic match.** If the pypsa-de variable name differs (naming or hierarchy) but the meaning is the same, rule 1 applies. The variable spec MUST name the pypsa-de variable and function (with line range) and justify why they match.
3. **No match.** Only if no matching variable exists in `export_ariadne_variables.py` is the function built with the `pypsa.statistics` accessor (https://docs.pypsa.org/latest/api/networks/statistics/).
4. **Switch to `pypsa.statistics` for exact matches.** For an exact match (rule 1), the function SHOULD be built with the `pypsa.statistics` accessor instead of the ported pypsa-de logic, but only if both conditions hold (owner decision 2026-11-05):
   - **Same result, proven.** The `pypsa.statistics` evaluation and the pypsa-de logic (with the changes allowed below) give the same result for every location and every snapshot, i.e. compared with `aggregate_per_year=False` (non-aggregated data; the yearly values follow from them by C6.10–C6.12), on at least one solved PyPSA-AT network in `resources/`. With pypsa rounding switched off (`round=False`), a port value `b` and a `pypsa.statistics` value `a` are equal if `|a − b| ≤ 1e-9 + 1e-9·|b|` (absolute and relative tolerance `1e-9`, in the unit of the result; `numpy.isclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True)`). NaN equals only NaN: NaN in both is equal (e.g. D9 values without weight, C6.12), NaN against a number is not (owner, PR #175 review 2026-11-11). Every compared value MUST be equal. A proof in which all compared values are zero or NaN (e.g. a network without the evaluated carriers) is not valid: at least one location MUST have a value that is neither zero nor NaN (owner, PR #149 review; NaN added in the PR #175 review). The variable spec MUST record the proof in section 4: network file, pypsa version, date, the two evaluations compared and the result.
   - **Who proves.** The proof is run by the `developer` in the PR that implements the function, on a network in `resources/`, and is reported in that PR's description. A spec that says "not proven" does not block the switch: the developer MAY prove it in the implementing PR. Since the developer never changes `specs/`, the `spec-writer` then records the proof and the line counts in section 4 of the variable spec in a follow-up spec PR (`CLAUDE.md` "Roles"; owner, PR #175 review 2026-11-11). If the proof fails, the PR ports the pypsa-de logic (rule 1).
   - **Shorter code.** The `pypsa.statistics` implementation has fewer code lines than the port: lines of the statistics function plus helpers in `utils.py` that only this function uses, without docstrings, comments and blank lines. The variable spec MUST name both counts (an estimate from a draft implementation is enough).

   If both conditions hold, the match type stays `exact` and the spec states the source as "`pypsa.statistics`, equivalent to pypsa-de (P6.4)". If either condition fails or is not proven, rule 1 applies unchanged: the function ports the pypsa-de logic and the spec names `export_ariadne_variables.py` as source. Semantic matches (rule 2) are not covered: they keep the ported logic.

The ported logic is changed only as far as needed to fit the function contract: stand-alone function, shared helpers only in `utils.py` (P4), return format of C6, no country aggregation inside the function. Every such change MUST be listed in the variable spec.

`CLAUDE.md` ("Blueprint") and `sister_packages/CLAUDE.md` follow this rule since PR #128 (SC-14 resolved, [open_questions.md](../open_questions.md)). If an instruction file disagrees with P6, P6 takes precedence.

## P7 Requirement language
Specs use MUST / SHOULD / MAY (RFC 2119 meaning). Acceptance criteria MUST be concrete enough to become unit tests in `tests/`.

## P8 Small steps
Changes are incremental and touch only what is needed (`CLAUDE.md`, "Working Principles").
