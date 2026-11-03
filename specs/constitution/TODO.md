# TODO

Status: reviewed (created 2026-10-29 from the open GitHub issues and the SC items of `specs/open_questions.md`, reviewed on 2026-10-29; WP1 spec review 2026-10-30, reviewed review on 2026-10-30; WP2/WP5 spec review 2026-11-03, reviewed on 2026-11-03; post-SC-14 housekeeping 2026-11-03)

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
- [ ] Non-versioned test configs in `config/test` with network `resources/electricity_network_0p3` (#129; owner, PR #127 review 2026-11-03).
One PR per definition, each with unit tests; listed with the variables that need it.
- [ ] D1 location attribution — Electricity, Natural Gas, Oil, Net Imports|Oil, Transportation, Residential and Commercial
- [ ] D2 `f_oil` — Oil, Net Imports|Oil
- [ ] D3 `f_gas` — Natural Gas
- [ ] D4 domestic shares `d_k(c)` (needs `energy_totals`) — Oil, Transportation
- [ ] D5 non-energy use incl. mean for missing countries (needs the shares table) — Natural Gas, Oil, Coal, Industry
- [ ] D6 coke correction `κ` — Coal, Industry
- [ ] D7 `land transport oil` — Oil, Transportation: no division by an engine efficiency. No unit relabelling to `MWh_LHV` (OQ-29 resolved 2026-11-03); `land transport` stays a key of `UNITS_MAPPING` (owner, PR #123 review 2026-11-02); the functions MAY return the raw unit `land transport`, `Network_Processor` normalises it after the function (C8 step 2).
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
- [x] PR #122: config validation and defaults (SC-1–5, SC-18, SC-19). Decisions taken in the PR without asking: OQ-31 (case-sensitive codes, confirmed 2026-11-03); OQ-30 (`null` for optional keys, rejected 2026-11-03 → SC-44); OQ-4 (`XK` rejected; owner 2026-11-03: accept `XK` → SC-45).
- [x] PR #123: unit handling (SC-10, SC-24; SC-9 partly: `land transport` stays in `UNITS_MAPPING`, owner decision 2026-11-02). Follow-ups: OQ-29 and OQ-32 resolved 2026-11-03 (no relabelling, no cross-year check); SC-43 open.
- [x] PR #124: output names and timestamps (SC-15, SC-22). Owner (PR #124 review 2026-11-02): timezone-aware snapshots keep their timezone (C10.5).
- [x] PR #125: environment and docs (SC-13, SC-16; OQ-16: `requests` removed, `pypsa` declared in `pixi.toml`; SC-12 for `docs/contributing.md`). SC-17 was already done in PR #112.
- [ ] SC-12 (`CLAUDE.md` "Code Style": Python ≥ 3.12) and SC-20 (`CLAUDE.md` "Local debugging": all-NaN results "not valid"): need a `CLAUDE.md` change on explicit owner request ("Forbidden Actions"); not a spec PR.
- [ ] PR: follow-up from the WP2/WP5 spec review: `null` for an optional config key = not set, default applies (C1.4, C1-AC3c; SC-44); a bracketed definition unit without comma is a list, `"[TJ]"` → `TJ`, `"[]"` → `ValueError` (C9.3, C9-AC3b; SC-43); `country: XK` accepted, pypsa-eur notation (C1.6, C1-AC2; SC-45). A unit with the same name as a carrier of `n` is valid; only non-empty keys of `UNITS_MAPPING` are checked (C6.5, C9.1; SC-46).
- [x] Spec review after WP2/WP5 (2026-11-03): TODO ticks, SCs resolved, C6.5, C8.2, C8.7, C9.1, C10.5 aligned with the owner decisions in the reviews of #118–#125; OQ-29–OQ-32 added and decided by the owner in the PR #127 review (2026-11-03), SC-43, SC-44; OQ-4 decided 2026-11-03 (SC-45).

## Later (need specs first)
- Regions and country codes: #96, #39 (OQ-2, OQ-4, OQ-9).
- New variables: Final Energy #71, Ambient Heat #75, Net Imports Biomass/Coal/Natural Gas #66–68, Investments #106, prices #76, #99–104 (#100–104 low prio).
- Physical method for non-energy use (C2.5) once PyPSA-AT stores industry production in `n.meta`.
- Other: metadata #26, cache #52, documentation #82.
