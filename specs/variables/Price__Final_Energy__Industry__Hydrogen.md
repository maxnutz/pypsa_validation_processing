# `Price|Final Energy|Industry|Hydrogen`

Status: reviewed
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Price\|Final Energy\|Industry\|Hydrogen` |
| Function name | `Price__Final_Energy__Industry__Hydrogen` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml`, long form `{function: Price__Final_Energy__Industry__Hydrogen, aggregation: intensive}` (C4.1) |
| Aggregation class | `intensive` (C4.5); weight = withdrawal of the Load `H2 for industry` in `MWh` (D9) |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed.

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #101 (milestone "Implement Infra-Enshure Coupling Variables"; umbrella #76 "Prices of carriers for industry demand") |
| Variable name | `Price\|Final Energy\|Industry\|Hydrogen` (issue title and IAMC name; owner decision 2026-11-05: singular `Price` and sector level `Industry` as in pypsa-de and #76) |
| Description | Prices of Final Energy\|Hydroghen per unit. (#101) |
| Unit | not given in the issue; `EUR_2020/MWh` (OQ-34, owner 2026-11-11) |
| Contained in a definitions folder? | no. `sister_packages/energy-scenarios-at-workflow/definitions/variable/` has no `Price` variable (searched 2026-11-05) (OQ-33) |

```yaml
n/a
```

Issue title and IAMC name are identical: #101 was renamed from `Prices|Final Energy|…` to the IAMC name on 2026-11-06 (owner, PR #148 review).

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | marginal price of the Load's bus, currency per `MWh_LHV`; `n.statistics.revenue` labels it `MWh_LHV` | D9 |
| Unit label returned by the function | `EUR_2020/MWh` for `value` and `weight` rows (C6.12) | D9, OQ-34 |
| Normalised unit (`utils.UNITS_MAPPING`) | `EUR_2020/MWh` (key `EUR_2020/MWh` → `EUR_2020/MWh`, added with the first `intensive` variable, SC-21; parsed by `iam_units`) | C9.1 |
| Target unit | not part of the variable spec: conversion to the unit of a definitions folder is done with `pyam` in `Network_Processor` (C9), not in the function | C9 |
| Conversion | none in the function (C9) | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_prices` (helper `price_load`, l.3378-3402) |
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L4086-L4088` |
| pypsa-de variable name | `Price\|Final Energy\|Industry\|Hydrogen`, computed as `price_load(n, "H2 for industry", region)[0]` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as far as needed for the function contract:
- Region = location (D1.1) instead of `n.loads.bus.str.contains(region)`; per-location values are aggregated to the country by C8 (weighted mean).
- CO2 price included: the bus marginal price `λ_b` as in `price_load`, nothing subtracted (D9; owner decision 2026-11-06 after PR #148, reversing its review decision; removing the CO2 price is #163).
- Returns `value` and `weight` rows (C6.12) instead of the tuple `(price, load)`.
- `price_load` returns NaN for a total load < 1 MWh; here the value is NaN only for a weight of `0.0` or NaN (D9 item 3, A-5); a location with a weight between 0 and 1 MWh is evaluated normally.
- Snapshot weighting per C6.10/C6.12: `price_load` does not weight snapshots; identical for constant gₜ (C6.12).

P6.4 (switch to `pypsa.statistics`): not proven. The `−revenue / withdrawal` check in D9 compares yearly totals over all locations for `gas for industry` only; P6.4 requires a per-location, per-snapshot comparison (`aggregate_per_year=False`) for this carrier and both code line counts. Until then rule 1 applies and the function ports `price_load` (D9). The implementing PR MAY record the proof here and switch.

## 5. Match type
- Match type: `exact`
- Reasoning: Same variable name and the same formula (`price_load` on the Load `H2 for industry`, D9). The issue text spells "Hydroghen"; issue title and IAMC name use `Hydrogen`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| Load | `H2 for industry` | `H2 for industry` | withdrawal (weight), withdrawal × bus marginal price (cost) | yes | measured on `resources/20261020_carbon_accounting_run/networks/solved_2040.nc`; sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py l.4086-4088 |
| any other component at the `H2 for industry` bus | – | `H2 for industry` | – | no (they set the bus price, they are not priced demand) | D9 |

Measured (`resources/20261020_carbon_accounting_run/networks/solved_2040.nc`, 2026-11-05): 51 `H2 for industry` Loads, one per location, on regional buses with carrier `H2 for industry` and unit `MWh_LHV`; yearly Load-weighted price over all locations 72.06 EUR/MWh, including the CO2 price (D9).

## 7. Accounting rule and sign convention
- Formula: `value(l) = P[H2 for industry](l)`, `weight(l) = L[H2 for industry](l)` (D9).
- Sign convention: weight ≥ 0 (C6.12). The value MAY be negative if marginal prices are negative; G1 and G2 do not apply (not a `Final Energy` variable).
- Weighting: per C6.12 (yearly value = Σₜ vₜ·wₜ·gₜ / Σₜ wₜ·gₜ, yearly weight = Σₜ wₜ·gₜ; snapshot weight rows unweighted).
- Special cases ported from pypsa-de: none.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | switch Series / DataFrame (C6) | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |
| `industry_non_energy_shares` | no | – | – |

## 9. Return format
- `aggregate_per_year=True`: `pd.Series`, MultiIndex `[location, unit, quantity]`, `quantity ∈ {value, weight}`; value = weighted mean over snapshots, weight = weighted withdrawal in `MWh` (C6.12). Both rows carry the unit label `EUR_2020/MWh`.
- `aggregate_per_year=False`: `pd.DataFrame`, same MultiIndex, columns = snapshots of `n`; value = `K_t / w_t` (NaN where `w_t` is `0.0` or NaN), weight = unweighted withdrawal per snapshot (C6.12).
- No country aggregation inside the function (C6, C8).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| location without a `H2 for industry` Load | value and weight NaN (every snapshot with `aggregate_per_year=False`); the location is not dropped (C6.12, C6.13, A-5) |
| carrier `H2 for industry` not present in `n` | value and weight NaN for every location of `n.buses.location` (C6.13). The function MUST NOT return `None` or zero rows (C6.7) |
| Load present, withdrawal 0 in a snapshot / all year | value NaN, weight `0.0` for that snapshot / location (D9 items 1 and 3) |
| country or region without any `H2 for industry` Load | value NaN after region aggregation (C8.2); `pyam` drops NaN rows (OQ-12) |
| negative marginal price | negative value, weight unchanged (section 7) |
| network without `n.buses_t.marginal_price` (not solved) | out of scope: C2 requires solved networks |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1, has an index level `quantity` with exactly `value` and `weight`, every value row has its weight row (C6.12), and every row has the unit label `EUR_2020/MWh`.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2 and the `quantity` checks of AC1.
- AC3: Mock network, locations `A`, `B`; one `H2 for industry` Load at `A` with `p = [10, 30]` MW, bus marginal price `λ = [50, 100]` EUR/MWh, 2 snapshots, weighting 1. Yearly: `(A, value) = 87.5` (= 3500 / 40), `(A, weight) = 40`. Snapshots: `(A, value) = [50, 100]`, `(A, weight) = [10, 30]`. `B` (no Load): value and weight NaN.
- AC3a: As AC3 with snapshot weighting 2: yearly `(A, value) = 87.5`, `(A, weight) = 80`; snapshot rows unchanged (C6.12).
- AC4: The `True` and `False` results are consistent per C6-AC3 (`intensive`).
- AC5: As AC3 with `λ = [−20, 100]`: yearly value `(−200 + 3000) / 40 = 70.0`; snapshot value `−20` for the first snapshot (negative prices pass).
- AC6: C6-AC6: a mock network without the carrier `H2 for industry` returns value and weight NaN for every location, not `None` and not zero rows. A Load with `p = [0, 0]` at `A` gives value NaN and weight `0.0` at `A` (both values of `aggregate_per_year`); with `p = [10, 0]` the snapshot values are `[50, NaN]` and the yearly value is `50`.
- AC7: Other components at the same bus change the result only through `λ_b` (D9); e.g. `capital_cost > 0` of a Link with carrier `H2 for industry` does not change it.
- AC8 (CO2 price included): as AC3, plus one Link supplying the Load's bus with `efficiency = 1`, `p0 = [10, 30]` and `bus2` on a bus with carrier `co2`, `efficiency2 = 0.2`, marginal price `[−100, −100]` EUR/t: the result equals AC3 (snapshot values `[50, 100]`, yearly value `87.5`); the CO2 port of the supplying Link is not evaluated (D9).

## 12. Open questions
- ~~OQ-33~~ resolved (owner, 2026-11-11): the variable is evaluated only with `definitions_path: false` (C3.2, no unit conversion) until the definitions of the Infra-Enshure coupling variables, made in another repository, are imported (PR #148 review 2026-11-06).
- ~~OQ-34~~ resolved (owner, 2026-11-11): unit label `EUR_2020/MWh` (section 3).

## 13. Sources
- #101, #76, milestone "Implement Infra-Enshure Coupling Variables"
- `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` l.3378-3402 (`price_load`), l.4086-4088 (commit `a5baa7e9`)
- PyPSA statistics accessor (`revenue`, `withdrawal`): https://docs.pypsa.org/latest/api/networks/statistics/
- measurement on `resources/20261020_carbon_accounting_run/networks/solved_2040.nc` (D9); `resources/carriers_bus_carriers_components.csv` is outdated (no `coal for industry` Load, `H2 for industry` on bus carrier `H2`) and not used as a source
- D1, D9 in [shared_definitions.md](shared_definitions.md); C4.5, C6.12, C6.13, C8 in [../contracts.md](../contracts.md); A-5, A-8 in [../open_questions.md](../open_questions.md)
