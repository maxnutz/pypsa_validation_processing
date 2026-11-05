# TODO

Status: reviewed (created 2026-10-29 from the open GitHub issues and the SC items of `specs/open_questions.md`, reviewed on 2026-10-29; WP1 spec review 2026-10-30, reviewed review on 2026-10-30; WP2/WP5 spec review 2026-11-03, reviewed on 2026-11-03; post-SC-14 housekeeping 2026-11-03, reviewed on 2026-11-03; WP3 spec review 2026-11-04, reviewed on 2026-11-04; test configs spec 2026-11-04, reviewed on 2026-11-04; post-#129 cleanup 2026-11-05)

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
- [x] PR #114: read the shares file, `industry_non_energy_shares_year`, checks and skip logic (C2.5); `industry_non_energy_shares_path` set in the local example configs `configs/config.{country,region}-{year,timeseries}.yaml` (owner decision 2026-10-29); these configs are not versioned (`.gitignore` l.76), so the repository is unchanged by this part (owner, PR #127 review 2026-11-03).
- [x] Spec review after WP1 (2026-10-30): C2.3, C2.4, C2.6 and C2.5 aligned with the owner decisions in the reviews of #112–#114.
- [x] PR #117: follow-up from the WP1 spec review: `industry_non_energy_shares_year` checked only if the shares file is read, unreadable shares file → `WARNING` and skip, empty path string = not set (C2.5, C2-AC8, C2-AC8c; SC-39, SC-40, SC-41); energy totals without the D4 share columns → `WARNING` and skip (C2.4, C2-AC6b, C2-AC6c; SC-42).

## WP2 Result validation and aggregation (C6, C8) — depends on WP0, parallel to WP1
- [x] PR #118: structural validation of every result, abort on violation (C6.8–9; SC-8, SC-25). Includes a minimal fix: `Final_Energy_by_Carrier__Coal` returns `0.0` per location instead of `None` without `coal for industry`; full C6.13 in WP4.
- [x] PR #119: aggregation classes `flow` / `stock` / `intensive` in the mapping (C4.5, C8.2; SC-21), incl. parsing the long form of C4.1. Units of the first `stock` / `intensive` variable (e.g. `MW`, `EUR/MWh`) are added to `UNITS_MAPPING` in the PR that adds that variable (owner, PR #119 review 2026-11-02).
- [x] PR #120: drop the copperplate `EU`, `country: EU` = 27 member states (C8.7–8; SC-37). Owner (PR #120 review 2026-11-02): no log message for the drop.

## WP3 Shared definitions in `utils.py` — depends on WP1 and on SC-14
- [x] SC-14 resolved before the first helper or statistics function is implemented (WP3, WP4): resolved by PR #128 (2026-11-03); `CLAUDE.md` "Blueprint" and `sister_packages/CLAUDE.md` name P6 (`specs/constitution/principles.md`) as binding.
One PR per definition, each with unit tests; listed with the variables that need it. All merged 2026-11-04 as a stack; no statistics function was changed. The helpers are named in each D-section of `specs/variables/shared_definitions.md`.
- [x] PR #132: D1 location attribution `attribute_locations` — Electricity, Natural Gas, Oil, Net Imports|Oil, Transportation, Residential and Commercial
- [x] PR #133: D2 `f_oil` `fossil_oil_share` — Oil, Net Imports|Oil
- [x] PR #134: D3 `f_gas` `fossil_gas_share` — Natural Gas
- [x] PR #135: D4 domestic shares `d_k(c)` `apply_domestic_share` (needs `energy_totals`) — Oil, Transportation. The old `get_energy_totals_domestic_share` (`AT` for every location, OQ-1) stays until the WP4 PRs of Transportation and Oil replace it.
- [x] PR #136: D5 non-energy use `non_energy_use` incl. mean for missing countries (needs the shares table) — Natural Gas, Oil, Coal, Industry. Owner (PR #136 review 2026-11-04): a share outside `[0, 1]` is clipped with a `WARNING` (D5).
- [x] PR #137: D6 coke correction `apply_coke_correction` — Coal, Industry. Factor `1.366` to be checked after WP4 (see WP4).
- [x] PR #137: D7 `land transport oil` — Oil, Transportation: no helper; `UNITS_MAPPING` comment and tests only (SC-9 resolved). No division by an engine efficiency, no relabelling to `MWh_LHV` (OQ-29); the functions MAY return the raw unit `land transport`, `Network_Processor` normalises it after the function (C8 step 2).
- [x] PR #138: D8 decentral heat split `decentral_heat_split` — Agriculture, Industry, Residential and Commercial. Owner decisions in the PR #138 review (2026-11-04) are in D8.
- [x] Spec review after WP3 (2026-11-04): D1–D8 name their helpers; owner decisions of the reviews of #132–#138 added to D5 and D8; SC-9, SC-12, SC-20, SC-43–SC-46 resolved.

## WP4 Statistics functions — each depends on WP1, WP2, SC-14 (WP3) and its D-helpers
One PR per function. Order: few dependencies first, so the framework is exercised end-to-end early.
Until the `Net Imports|Oil` PR is merged, the WP4 PRs before it run `pixi run workflow_test` with the line `Net Imports|Oil: Net_Imports__Oil` of `configs/mapping.default.yaml` commented out locally; this change is never committed (owner 2026-11-05). The `Net Imports|Oil` PR runs it with the line active.
- [x] Spec PR: test config setups in `specs/configuration.md` "Test configs" (#129; owner, PR #127 review 2026-11-03; location `pypsa_validation_processing/configs/test/`, not versioned because they refer to local data, owner 2026-11-04 and PR #141 review).
- [x] PR #143: test configs (#129): `pixi.toml` `workflow_test` runs the setups of `specs/configuration.md` "Test configs" on `resources/electricity_network_0p3`; `README.md` l.79, l.109 updated; the earlier example configs `configs/config.{country,region}-{year,timeseries}.yaml` removed (SC-47, CT-AC5). The configs themselves are created locally (not versioned). `CLAUDE.md` "Full local check" in PR #144 (owner request 2026-11-05). Result (PR #143, owner 2026-11-05): all six setups abort on `Net Imports|Oil` (location `co2`, C6.6; SC-31); with that variable commented out in the mapping, all six setups and `pytest` pass. The slow first run of `country-timeseries-AT` (~28 min) did not reproduce; no progress logging is added (owner 2026-11-05). Moved from WP3 (2026-11-04): first item of WP4, so that every function PR and the deep review of the WP3 helpers can run on workflow data.
- [ ] Net Imports|Electricity (none; SC-30; #70)
- [ ] Final Energy [by Carrier]|District Heat (none; SC-29; #63, #73)
- [ ] Final Energy [by Carrier]|Electricity (D1; SC-38; #43)
- [ ] Final Energy [by Carrier]|Coal (D5, D6; #44)
- [ ] Net Imports|Oil (D1, D2; SC-31; #69); fixes the C6.6 abort of `workflow_test` (location `co2`), so later PRs run `workflow_test` with the full mapping
- [ ] Final Energy [by Carrier]|Natural Gas (D1, D3, D5; SC-23, SC-27; #45, #61, #97)
- [ ] Final Energy [by Sector]|Agriculture (D8; SC-34; #13)
- [ ] Final Energy [by Sector]|Residential and Commercial (D1, D8; SC-35; #14)
- [ ] Final Energy [by Sector]|Transportation (D1, D4, D7; SC-32; #15)
- [ ] Final Energy [by Carrier]|Oil (D1, D2, D4, D5, D7; SC-28; #46, #53)
- [ ] Final Energy [by Sector]|Industry (D5, D6, D8; SC-33; #12, #74)
- [ ] All functions return every location (C6.13; SC-26) — checked in each PR above.
- [ ] Deep review of the WP3 helpers after WP4, together with the statistics functions that use them, on workflow data (`pixi run workflow_test` and the test configs of #129); covers `attribute_locations` on real networks (owner, PR #132 and PR #138 reviews 2026-11-04).
- [ ] Spec review after WP4: research the D6 coke factor `1.366` MWh coal per MWh coke (`MWH_COAL_PER_MWH_COKE` in `utils.py`, taken from pypsa-de `get_final_energy` l.2208–2225) in more depth and check it against the PyPSA code that preprocesses the industry data (owner, PR #137 review 2026-11-04).
- [ ] Spec review after WP4: D8 tells CHP heat and solar thermal heat on decentral heat buses apart; the result carrier is `b` for both today (owner, PR #141 review 2026-11-04).

## WP5 Config, units and output (C1, C9, C10) — independent, parallel to WP3/WP4
- [x] PR #122: config validation and defaults (SC-1–5, SC-18, SC-19). Decisions taken in the PR without asking: OQ-31 (case-sensitive codes, confirmed 2026-11-03); OQ-30 (`null` for optional keys, rejected 2026-11-03 → SC-44); OQ-4 (`XK` rejected; owner 2026-11-03: accept `XK` → SC-45).
- [x] PR #123: unit handling (SC-10, SC-24; SC-9 partly: `land transport` stays in `UNITS_MAPPING`, owner decision 2026-11-02). Follow-ups: OQ-29 and OQ-32 resolved 2026-11-03 (no relabelling, no cross-year check); SC-43 open.
- [x] PR #124: output names and timestamps (SC-15, SC-22). Owner (PR #124 review 2026-11-02): timezone-aware snapshots keep their timezone (C10.5).
- [x] PR #125: environment and docs (SC-13, SC-16; OQ-16: `requests` removed, `pypsa` declared in `pixi.toml`; SC-12 for `docs/contributing.md`). SC-17 was already done in PR #112.
- [x] PR #131: SC-12 (`CLAUDE.md` "Code Style": Python ≥ 3.11) and SC-20 (`CLAUDE.md` "Local debugging": all-zero / all-NaN results valid, but check them against the network); `CLAUDE.md` change on explicit owner request, not a spec PR.
- [x] PR #139: follow-up from the WP2/WP5 spec review: `null` for an optional config key = not set, default applies (C1.4, C1-AC3c; SC-44); a bracketed definition unit without comma is a list, `"[TJ]"` → `TJ`, `"[]"` → `ValueError` (C9.3, C9-AC3b; SC-43); `country: XK` accepted, pypsa-eur notation (C1.6, C1-AC2; SC-45). A unit with the same name as a carrier of `n` is valid; only non-empty keys of `UNITS_MAPPING` are checked (C6.5, C9.1; SC-46). Remove the unreachable warn-and-skip branch for a missing function in `_execute_function_for_variable` (missing functions raise at initialisation, C4; SC-6; owner, PR #130 review 2026-11-03).
- [x] Spec review after WP2/WP5 (2026-11-03): TODO ticks, SCs resolved, C6.5, C8.2, C8.7, C9.1, C10.5 aligned with the owner decisions in the reviews of #118–#125; OQ-29–OQ-32 added and decided by the owner in the PR #127 review (2026-11-03), SC-43, SC-44; OQ-4 decided 2026-11-03 (SC-45).

## WP6 Infra-Enshure coupling variables (milestone 2) — independent, parallel to WP4
- [ ] Spec PR #148: D9 and `Price|Final Energy|Industry|{Electricity, Gases, Hydrogen, Solids|Biomass, Solids|Coal, Liquids|Oil}` (#99–#104, umbrella #76); owner decisions 2026-11-05: IAMC names with `Price|…|Industry|…`, Load-weighted marginal price (D9), investments (#106) in a later spec PR.
- [ ] Before implementation: OQ-33 (definitions), OQ-34 (unit, currency year), OQ-35 (methanol, heat; scope of #76).
- [ ] Code PR: D9 helper in `utils.py`, `UNITS_MAPPING` key for the price unit (SC-21), `Price|Final Energy|Industry|Electricity` (#99) as first `intensive` variable. C6.13 for results with a `quantity` level: `utils.ensure_all_locations` (PR #146) accepts only the levels `location` and `unit`, so it needs an extension or a D9-specific fill (value and weight `0.0`).
- [ ] Code PR(s): the other five prices (#100–#104, low prio).
- [ ] Spec PR: investments (#106, OQ-36).

## Later (need specs first)
- Regions and country codes: #96, #39 (OQ-2, OQ-4, OQ-9).
- New variables: Final Energy #71, Ambient Heat #75, Net Imports Biomass/Coal/Natural Gas #66–68. Investments #106 and prices #76, #99–104: WP6.
- Physical method for non-energy use (C2.5) once PyPSA-AT stores industry production in `n.meta`.
- Other: metadata #26, cache #52, documentation #82.
