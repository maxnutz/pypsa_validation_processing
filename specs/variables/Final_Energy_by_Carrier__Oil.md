# `Final Energy [by Carrier]|Oil`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Carrier]\|Oil` |
| Function name | `Final_Energy_by_Carrier__Oil` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #46; enhancement #53 |
| Variable name | `Final Energy [by Carrier]\|Oil` |
| Description | Energy consumption of oil excluding transmission/distribution losses (#2) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Oil` ("oil") |

```yaml
- Final Energy [by Carrier]|{Final Energy Carrier}:
    description: Energy consumption of {Final Energy Carrier}
      excluding transmission/distribution losses
    unit: TJ
# {Final Energy Carrier} = Oil: "oil"
```
"Oil" means fossil oil: `tag_final_energy_carrier.yaml` defines `Biofuels` and `E-Fuels` as separate carriers, and #53 states "only includes fossil oil".

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_LHV`; `land transport` relabelled to `MWh_LHV` (D7) | bus units |
| Normalised unit | `MWh` | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy`, `_get_fuel_fractions` |
| pypsa-de line range | `export_ariadne_variables.py:L2164-L2197, L2372-L2392, L2453-L2481, L2557-L2559, L2642-L2651; L109-L242` |
| pypsa-de variable name | `Final Energy\|Liquids\|Petroleum` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- The fossil share `f_oil` is adapted to the single `EU oil` bus (D2). It is system-wide (owner decision 2026-10-22) and replaces the regional clipped ratio (#53).
- `shipping methanol` is not counted (pypsa-de counts it in `Liquids` and therefore partly in `Petroleum`). Reason: methanol is not oil and is not supplied by the oil bus (OQ-20).
- Domestic shares per country (D4) instead of one value per region.
- Per location (D1); no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `semantic`.
- Reasoning: pypsa-de `Final Energy|Liquids|Petroleum` = liquid final energy of all sectors (industry excluding non-energy use) × fossil oil fraction. That is "energy consumption of (fossil) oil".

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `agriculture machinery oil` | `agriculture machinery oil` | withdrawal | yes | l.2557-2559 |
| Link | `rural oil boiler`, `urban decentral oil boiler` | `oil` | withdrawal (bus0), location per D1 | yes | l.2372-2381 |
| Load | `land transport oil` | `land transport oil` | withdrawal, unit D7 | yes | l.2476-2477 |
| Load | `kerosene for aviation` | `kerosene for aviation` | withdrawal × `d_aviation` (D4) | yes | l.2463-2467 |
| Load | `shipping oil` | `shipping oil` | withdrawal × `d_navigation` (D4) | yes | l.2468-2470 |
| Load | `naphtha for industry` | `naphtha for industry` | withdrawal − `NE_naphtha` (D5) | yes | l.2192-2197 |
| Load | `shipping methanol` | `shipping methanol` | – | **no** (OQ-20) | l.2472-2474 |
| Link | `oil` (power plant), `urban central oil CHP` | `oil` | – | **no** (transformation) | l.2642-2647 |
| Link | `agriculture machinery oil`, `land transport oil`, `kerosene for aviation`, `shipping oil`, `naphtha for industry` (oil → demand bus) | `oil` | – | **no** (delivery to the Load bus; the Load is counted) | carriers table |

## 7. Accounting rule and sign convention
- Formula: `FE_oil(l) = f_oil · ( L[agriculture machinery oil](l) + W[oil, rural oil boiler](l) + W[oil, urban decentral oil boiler](l) + L[land transport oil](l) + d_aviation(c)·L[kerosene for aviation](l) + d_navigation(c)·L[shipping oil](l) + L[naphtha for industry](l) − NE_naphtha(l) )`, with `c` = country of `l`
- Sign convention: withdrawals positive; result MUST be ≥ 0.
- Weighting: per C6.10; `f_oil` and `d_k` are scalars applied to every snapshot.
- Special cases: domestic aviation/navigation (D4), non-energy use (D5), unit of land transport (D7).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | no | – | – |
| `energy_totals` | yes | domestic shares (D4) | variable skipped with `WARNING` (C2.4) |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_LHV` (or `MWh`). No `land transport` unit in the result (C9.1).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no oil demand in a location / in `n` | `0.0` (C6.13) |
| renewable oil supply > demand of a region | no effect on the share; `f_oil` is system-wide (D2) |
| no `rural oil boiler` links (e.g. 2040 network) | contributes 0 |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock: `oil refining` supplies 75, `Fischer-Tropsch` supplies 25 (`f_oil = 0.75`). At `A` (country `AA`): `land transport oil` Load 40 (bus unit `land transport`), `kerosene for aviation` Load 20, `d_aviation(AA) = 0.5`, `agriculture machinery oil` Load 4, `NE_naphtha = 0`, 1 snapshot. Result `(A, MWh_LHV or MWh): 0.75·(40 + 10 + 4) = 40.5`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0; no unit `land transport` in the result.
- AC6: C6-AC6.
- AC7: The domestic share is taken per country: two locations of different countries with different `energy_totals` rows get different shares.
- AC8: Without `energy_totals`, the variable is skipped with a `WARNING` (C2-AC6).

## 12. Open questions
- OQ-18 (`NE_naphtha`), OQ-20 (shipping methanol), OQ-1 (year of `energy_totals`).

## 13. Sources
- #46, #53, #2; definitions as in section 2
- `export_ariadne_variables.py` l.109-242, 2164-2197, 2372-2392, 2453-2481, 2557-2559, 2642-2651 (commit `a5baa7e9`)
- `prepare_sector_network.py::add_ice_cars` l.2730-2765 (D7)
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__Oil` l.284-459 (commit `16bf37f`). Differences: SC-28
