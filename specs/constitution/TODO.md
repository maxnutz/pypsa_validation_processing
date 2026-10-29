# TODO

Status: draft (created 2026-10-29 from the open GitHub issues and the SC items of `specs/open_questions.md`)

Work packages (WP) in implementation order. The order follows the dependencies: a statistics function can only be tested against the specs once `Network_Processor` passes its inputs (C2, C5) and validates its result (C6, C8), and once the shared definitions it uses (D1–D8) exist as helpers in `utils.py`. Packages without mutual dependencies MAY run in parallel. One PR per item marked `PR`, so that every change stays small (`CLAUDE.md`, "Working Principles").

## WP0 Spec gate (before any code)
- [ ] Spec PR `spec/eurostat-shares-lookup` merged (ISO codes, `industry_non_energy_shares_year`, mean for missing countries).
- [ ] maxnutz/eurostat-energy-balance_processing branch `iso-country-codes` merged (`EL` → `GR`, `UK` → `GB`); shares CSV regenerated.
- [x] A-7 confirmed by the owner (2026-10-29: skip).
- [x] Status of all specs merged in #108 and #110 set to `reviewed` (2026-10-29).
- [ ] Coal non-energy use specified (discussion 2026-10-29).

## WP1 Inputs of statistics functions (C2, C5) — depends on WP0
- [ ] PR: investment year, `config` and `energy_totals` from `n.meta` (C2.2–C2.4; SC-11, SC-36, SC-7; #48).
- [ ] PR: signature check at initialisation and kwarg passing incl. `industry_non_energy_shares` (C5; SC-6).
- [ ] PR: read the shares file, `industry_non_energy_shares_year`, checks and skip logic (C2.5); add `industry_non_energy_shares_path` to `configs/config.{country,region}-{year,timeseries}.yaml` (owner decision 2026-10-29).

## WP2 Result validation and aggregation (C6, C8) — depends on WP0, parallel to WP1
- [ ] PR: structural validation of every result, abort on violation (C6.8–9; SC-8, SC-25).
- [ ] PR: aggregation classes `flow` / `stock` / `intensive` in the mapping (C4.5, C8.2; SC-21).
- [ ] PR: drop the copperplate `EU`, `country: EU` = 27 member states (C8.7–8; SC-37).

## WP3 Shared definitions in `utils.py` — depends on WP1
One PR per definition, each with unit tests; listed with the variables that need it.
- [ ] D1 location attribution — Electricity, Natural Gas, Oil, Net Imports|Oil, Transportation, Residential and Commercial
- [ ] D2 `f_oil` — Oil, Net Imports|Oil
- [ ] D3 `f_gas` — Natural Gas
- [ ] D4 domestic shares `d_k(c)` (needs `energy_totals`) — Oil, Transportation
- [ ] D5 non-energy use incl. mean for missing countries (needs the shares table) — Natural Gas, Oil, Industry
- [ ] D6 coke correction `κ` — Coal, Industry
- [ ] D7 unit of `land transport oil` — Oil, Transportation
- [ ] D8 decentral heat split — Agriculture, Industry, Residential and Commercial

## WP4 Statistics functions — each depends on WP1, WP2 and its D-helpers
One PR per function. Order: few dependencies first, so the framework is exercised end-to-end early.
- [ ] Net Imports|Electricity (none; SC-30; #70)
- [ ] Final Energy [by Carrier]|District Heat (none; SC-29; #63, #73)
- [ ] Final Energy [by Carrier]|Electricity (D1; SC-38; #43)
- [ ] Final Energy [by Carrier]|Coal (D6; #44)
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
