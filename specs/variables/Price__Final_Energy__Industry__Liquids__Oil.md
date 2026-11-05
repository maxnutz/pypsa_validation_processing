# `Price|Final Energy|Industry|Liquids|Oil`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Price\|Final Energy\|Industry\|Liquids\|Oil` |
| Function name | `Price__Final_Energy__Industry__Liquids__Oil` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml`, long form `{function: Price__Final_Energy__Industry__Liquids__Oil, aggregation: intensive}` (C4.1) |
| Aggregation class | `intensive` (C4.5); weight = withdrawal of the Load `naphtha for industry` in `MWh` (D9) |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed.

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #104 (milestone "Implement Infra-Enshure Coupling Variables"; umbrella #76 "Prices of carriers for industry demand") |
| Variable name | `Prices\|Final Energy\|Oil` (issue); IAMC name `Price\|Final Energy\|Industry\|Liquids\|Oil` (owner decision 2026-11-05: singular `Price` and sector level `Industry` as in pypsa-de and #76) |
| Description | Prices of Final Energy\|Naphtha = Final Energy\|Oil per unit. Includes oil from various sources, inlcluding fossil oil, and non-fossil oil (#104) |
| Unit | not given in the issue (OQ-34) |
| Contained in a definitions folder? | no. `sister_packages/energy-scenarios-at-workflow/definitions/variable/` has no `Price` variable (searched 2026-11-05) (OQ-33) |

```yaml
n/a
```

Issue and IAMC name differ (`Prices` → `Price`, added level `Industry`, carrier hierarchy of pypsa-de); decided by the owner on 2026-11-05.

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | marginal price of the Load's bus, currency per `MWh_LHV`; `n.statistics.revenue` labels it `MWh_LHV` | D9 |
| Unit label returned by the function | `EUR/MWh` for `value` and `weight` rows (C6.12) | D9, OQ-34 |
| Normalised unit (`utils.UNITS_MAPPING`) | `EUR/MWh` (key to be added with the first `intensive` variable, SC-21) | C9.1 |
| Target unit | none: not in the definitions, so no conversion (C3.2, C9.6). Currency year and IAMC unit (`EUR_2020/GJ` in pypsa-de, l.5752-5753) open (OQ-34) | OQ-34 |
| Conversion | none | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_prices` (helper `price_load`, l.3378-3402) |
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L3988-L3990` |
| pypsa-de variable name | `Price\|Final Energy\|Industry\|Liquids\|Oil`, computed as `get_weighted_costs_links(["naphtha for industry"], n, region)` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as far as needed for the function contract:
- Region = location (D1.1) instead of `n.loads.bus.str.contains(region)`; per-location values are aggregated to the country by C8 (weighted mean).
- Returns `value` and `weight` rows (C6.12) instead of the tuple `(price, load)`.
- `price_load` returns NaN for a total load < 1 MWh; here a location with weight 0 gets value and weight `0.0` (A-5, C6.13). A location with a weight between 0 and 1 MWh is evaluated normally.
- Snapshot weighting per C6.10/C6.12: `price_load` does not weight snapshots; identical for constant gₜ (C6.12).
- Formula: D9 (Load-weighted marginal price at the `naphtha for industry` bus) instead of `get_weighted_costs_links(["naphtha for industry"])` (owner decision 2026-11-05, D9). This is pypsa-de's formula for `Liquids|Efuel` (l.4037-4039).
- No upper cut-off: pypsa-de sets results ≥ 1e4 to NaN (l.3513); not ported.

## 5. Match type
- Match type: `semantic`
- Reasoning: Same variable name, different formula. pypsa-de reports the levelised cost of the `naphtha for industry` Links for `Liquids|Oil` and uses `price_load(n, "naphtha for industry", region)` (the D9 formula) for `Price|Final Energy|Industry|Liquids|Efuel` (l.4037-4039). Per #104 the price covers naphtha from fossil and non-fossil oil, i.e. the whole Load; the marginal price at the `naphtha for industry` bus is that mix price.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| `Load` | `naphtha for industry` | `naphtha for industry` | withdrawal (weight), withdrawal × bus marginal price (cost) | yes | `resources/carriers_bus_carriers_components.csv`; sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py l.3988-3990 |
| any other component at the `naphtha for industry` bus | – | `naphtha for industry` | – | no (they set the bus price, they are not priced demand) | D9 |

Measured (`resources/20261020_carbon_accounting_run/networks/solved_2040.nc`, 2026-11-05): 51 `naphtha for industry` Loads, one per location, on regional buses with unit `MWh_LHV`; yearly Load-weighted price over all locations 53.99 EUR/MWh (D9).

## 7. Accounting rule and sign convention
- Formula: `value(l) = P[naphtha for industry](l)`, `weight(l) = L[naphtha for industry](l)` (D9).
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
- `aggregate_per_year=True`: `pd.Series`, MultiIndex `[location, unit, quantity]`, `quantity ∈ {value, weight}`; value = weighted mean over snapshots, weight = weighted withdrawal in `MWh` (C6.12). Both rows carry the unit label `EUR/MWh`.
- `aggregate_per_year=False`: `pd.DataFrame`, same MultiIndex, columns = snapshots of `n`; value = `K_t / w_t` (0.0 where `w_t = 0`), weight = unweighted withdrawal per snapshot (C6.12).
- No country aggregation inside the function (C6, C8).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| location without a `naphtha for industry` Load | value and weight `0.0` (every snapshot with `aggregate_per_year=False`); the location is not dropped (C6.13, A-5) |
| carrier `naphtha for industry` not present in `n` | value and weight `0.0` for every location of `n.buses.location` (C6.13). The function MUST NOT return `None` or zero rows (C6.7) |
| Load present, withdrawal 0 in a snapshot / all year | value and weight `0.0` for that snapshot / location (D9 item 3) |
| negative marginal price | negative value, weight unchanged (section 7) |
| network without `n.buses_t.marginal_price` (not solved) | out of scope: C2 requires solved networks |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1, has an index level `quantity` with exactly `value` and `weight`, every value row has its weight row (C6.12), and every row has the unit label `EUR/MWh`.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2 and the `quantity` checks of AC1.
- AC3: Mock network, locations `A`, `B`; one `naphtha for industry` Load at `A` with `p = [10, 30]` MW, bus marginal price `λ = [50, 100]` EUR/MWh, 2 snapshots, weighting 1. Yearly: `(A, value) = 87.5` (= 3500 / 40), `(A, weight) = 40`. Snapshots: `(A, value) = [50, 100]`, `(A, weight) = [10, 30]`. `B`: value and weight `0.0`.
- AC3a: As AC3 with snapshot weighting 2: yearly `(A, value) = 87.5`, `(A, weight) = 80`; snapshot rows unchanged (C6.12).
- AC4: The `True` and `False` results are consistent per C6-AC3 (`intensive`).
- AC5: As AC3 with `λ = [−20, 100]`: yearly value `(−200 + 3000) / 40 = 70.0`; snapshot value `−20` for the first snapshot (negative prices pass).
- AC6: C6-AC6: a mock network without the carrier `naphtha for industry` returns value and weight `0.0` for every location, not `None`. A Load with `p = [0, 0]` at `A` gives value and weight `0.0` at `A`.
- AC7: Other components of the same carrier or at the same bus (e.g. a Link with carrier `naphtha for industry` and `capital_cost > 0`) do not change the result.

## 12. Open questions
- OQ-33: the variable is not in the definitions; it is evaluated only with `definitions_path: false` until it is added there.
- OQ-34: unit label, currency year and IAMC target unit.
- `industry methanol` (Load on bus carrier `industry methanol`, measured 121.13 EUR/MWh) is not part of this variable: #104 names naphtha only. pypsa-de counts it in `Price|Final Energy|Industry|Liquids` (l.4082-4085), and #76 lists methanol. Whether a separate variable is needed is OQ-35.

## 13. Sources
- #104, #76, milestone "Implement Infra-Enshure Coupling Variables"
- `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` l.3378-3402 (`price_load`), l.3988-3990 (commit `a5baa7e9`)
- PyPSA statistics accessor (`revenue`, `withdrawal`): https://docs.pypsa.org/latest/api/networks/statistics/
- `resources/carriers_bus_carriers_components.csv`; measurement on `resources/20261020_carbon_accounting_run/networks/solved_2040.nc` (D9)
- D1, D9 in [shared_definitions.md](shared_definitions.md); C4.5, C6.12, C6.13, C8 in [../contracts.md](../contracts.md); A-5, A-8 in [../open_questions.md](../open_questions.md)
