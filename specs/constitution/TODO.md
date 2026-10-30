# TODO

Status: draft (created 2026-10-29 from the open GitHub issues and the SC items of `specs/open_questions.md`, reviewed on 2026-10-29; WP1 spec review 2026-10-30)

Work packages (WP) in implementation order. The order follows the dependencies: a statistics function can only be tested against the specs once `Network_Processor` passes its inputs (C2, C5) and validates its result (C6, C8), and once the shared definitions it uses (D1–D8) exist as helpers in `utils.py`. Packages without mutual dependencies MAY run in parallel. One PR per item marked `PR`, so that every change stays small (`CLAUDE.md`, "Working Principles").

## WP0 Spec gate (before any code)
- [x] Spec PR `spec/eurostat-shares-lookup` merged (ISO codes, `industry_non_energy_shares_year`, mean for missing countries).
- [x] maxnutz/eurostat-energy-balance_processing#10 merged (`EL` → `GR`, `UK` → `GB`); shares CSV regenerated.
- [x] A-7 confirmed by the owner (2026-10-29: skip).
- [x] Status of all specs merged in #108 and #110 set to `reviewed` (2026-10-29).
- [x] Coal non-energy use specified (OQ-28, 2026-10-29).
- [x] maxnutz/eurostat-energy-balance_processing#11 merged (Coal share); shares CSV regenerated.

## WP1 Inputs of statistics functions (C2, C5) — depends on WP0
- [x] PR #112: investment year, `config` and `energy_totals` from `n.meta` (C2.2–C2.4; SC-11, SC-36, SC-7; #48).
- [x] PR #113: signature check at initialisation and kwarg passing incl. `industry_non_energy_shares` (C5; SC-6).
- [x] PR #114: read the shares file, `industry_non_energy_shares_year`, checks and skip logic (C2.5); add `industry_non_energy_shares_path` to `configs/config.{country,region}-{year,timeseries}.yaml` (owner decision 2026-10-29).
- [x] Spec review after WP1 (2026-10-30): C2.3, C2.4, C2.6 and C2.5 aligned with the owner decisions in the reviews of #112–#114.
- [ ] PR: follow-up from the WP1 spec review: `industry_non_energy_shares_year` checked only if the shares file is read, unreadable shares file → `WARNING` and skip, empty path string = not set (C2.5, C2-AC8, C2-AC8c; SC-39, SC-40, SC-41).

## WP2 Result validation and aggregation (C6, C8) — depends on WP0, parallel to WP1
- [ ] PR: structural validation of every result, abort on violation (C6.8–9; SC-8, SC-25).
- [ ] PR: aggregation classes `flow` / `stock` / `intensive` in the mapping (C4.5, C8.2; SC-21). Includes parsing the long form of C4.1: until then, a long-form entry is rejected at initialisation as "function not found" (owner decision 2026-10-29, PR #113 review).
- [ ] PR: drop the copperplate `EU`, `country: EU` = 27 member states (C8.7–8; SC-37).

## WP3 Shared definitions in `utils.py` — depends on WP1 and on SC-14
- [ ] SC-14 resolved before the first helper or statistics function is implemented (WP3, WP4). P6 (`specs/constitution/principles.md`) is binding: exact or semantic pypsa-de match → port the logic of `export_ariadne_variables.py` as is; `pypsa.statistics` only if no match exists; every change to the ported logic is listed in the variable spec. Two instruction files say otherwise and are read by the `developer` role:
  - `CLAUDE.md` l.32 ("Blueprint"): "serves as blueprint for evaluations, but use `pypsa.statistics` more extensively" → contradicts P6. Proposed text: "`export_ariadne_variables.py` is the implementation source: port its logic for every variable it evaluates (exact or semantic match, P6 in `specs/constitution/principles.md`); use `pypsa.statistics` only for variables without a match."
  - `sister_packages/CLAUDE.md` l.7-10: calls `get_final_energy` a "semantic map" and recommends reusing "the accounting logic per variable". Compatible with P6 in substance, but MUST name P6 as the rule, so that "semantic map" is not read as "inspiration only".
  - Who: the owner. `CLAUDE.md` changes only on explicit request ("Forbidden Actions"), `sister_packages/` is read-only for both roles, and spec PRs change only `specs/`. So this is a separate, non-spec PR on explicit request; then mark SC-14 resolved in `open_questions.md` (spec PR).
  - Not affected: WP1, WP2 and WP5 (no statistics logic).
One PR per definition, each with unit tests; listed with the variables that need it.
- [ ] D1 location attribution — Electricity, Natural Gas, Oil, Net Imports|Oil, Transportation, Residential and Commercial
- [ ] D2 `f_oil` — Oil, Net Imports|Oil
- [ ] D3 `f_gas` — Natural Gas
- [ ] D4 domestic shares `d_k(c)` (needs `energy_totals`) — Oil, Transportation
- [ ] D5 non-energy use incl. mean for missing countries (needs the shares table) — Natural Gas, Oil, Coal, Industry
- [ ] D6 coke correction `κ` — Coal, Industry
- [ ] D7 unit of `land transport oil` — Oil, Transportation
- [ ] D8 decentral heat split — Agriculture, Industry, Residential and Commercial

## WP4 Statistics functions — each depends on WP1, WP2, SC-14 (WP3) and its D-helpers
One PR per function. Order: few dependencies first, so the framework is exercised end-to-end early.
- [ ] Net Imports|Electricity (none; SC-30; #70)
- [ ] Final Energy [by Carrier]|District Heat (none; SC-29; #63, #73)
- [ ] Final Energy [by Carrier]|Electricity (D1; SC-38; #43)
- [ ] Final Energy [by Carrier]|Coal (D5, D6; #44)
- [ ] Net Imports|Oil (D1, D2; SC-31; #69)
- [ ] Final Energy [by Carrier]|Natural Gas (D1, D3, D5; SC-23, SC-27; #45, #61, #97)
- [ ] Final Energy [by Sector]|Agriculture (D8; SC-34; #13)
- [ ] Final Energy [by Sector]|Residential and Commercial (D1, D8; SC-35; #14)
- [ ] Final Energy [by Sector]|Transportation (D1, D4, D7; SC-32; #15)
- [ ] Final Energy [by Carrier]|Oil (D1, D2, D4, D5, D7; SC-28; #46, #53)
- [ ] Final Energy [by Sector]|Industry (D5, D6, D8; SC-33; #12, #74)
- [ ] All functions return every location (C6.13; SC-26) — checked in each PR above.

## WP5 Config, units and output (C1, C9, C10) — independent, parallel to WP3/WP4
- [ ] PR: config validation and defaults (SC-1–5, SC-18, SC-19).
- [ ] PR: unit handling (SC-9, SC-10, SC-24).
- [ ] PR: output names and timestamps (SC-15, SC-22).
- [ ] PR: environment and docs (SC-12, SC-13, SC-16, SC-17, SC-20; OQ-16).

## Later (need specs first)
- Regions and country codes: #96, #39 (OQ-2, OQ-4, OQ-9).
- New variables: Final Energy #71, Ambient Heat #75, Net Imports Biomass/Coal/Natural Gas #66–68, Investments #106, prices #76, #99–104 (#100–104 low prio).
- Physical method for non-energy use (C2.5) once PyPSA-AT stores industry production in `n.meta`.
- Other: metadata #26, cache #52, documentation #82.
