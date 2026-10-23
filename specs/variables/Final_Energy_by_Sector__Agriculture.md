# `Final Energy [by Sector]|Agriculture`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Sector]\|Agriculture` |
| Function name | `Final_Energy_by_Sector__Agriculture` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #13 |
| Variable name | `Final Energy [by Sector]\|Agriculture` |
| Description | Energy consumption by the agriculture sector including forestry excluding transmission/distribution losses (#2) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Agriculture` in `tag_sector.yaml` |

```yaml
- Final Energy [by Sector]|{Sector}:
    description: Energy consumption by the {Sector}
      excluding transmission/distribution losses
    unit: TJ
# {Sector} = Agriculture: "agriculture sector including forestry"
```

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_el`, `MWh_th`, `MWh_LHV` | bus units |
| Normalised unit | `MWh` (function MUST normalise, C6.5) | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy` |
| pypsa-de line range | `export_ariadne_variables.py:L2553-L2565` |
| pypsa-de variable name | `Final Energy\|Agriculture` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, with reason:
- `agriculture heat` is not counted as heat. Instead, the agricultural share of the decentral heat input of the `rural heat` bus is counted (D8, owner decision 2026-10-22, OQ-22 resolved). Reason: the delivered heat and the fuel producing it were counted in two sectors.
- Per location; no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `exact`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `agriculture electricity`, `agriculture machinery electric` | `low voltage` | withdrawal | yes | l.2553-2555 |
| Load | `agriculture heat` | `rural heat` | used only as heat demand for the share `σ_rural,agr(l)` (D8) | **no** (as heat) | l.2556 |
| Links / Generators | decentral heat supply of `rural heat` (D8) | input carriers | input × `σ_rural,agr(l)` | yes | D8 |
| Load | `agriculture machinery oil` | `agriculture machinery oil` | withdrawal | yes | l.2557-2559 |
| Link | `agriculture machinery oil` (supply), `agriculture machinery oil CC` | – | – | **no** (supply-link losses are not final energy) | l.2553-2565 |

## 7. Accounting rule and sign convention
- Formula: `FE_agr(l) = L[agriculture electricity](l) + L[agriculture machinery electric](l) + L[agriculture machinery oil](l) + D8_agr(l)`
- Sign convention: withdrawals positive; result MUST be ≥ 0.
- Weighting: per C6.10.
- `σ_rural,agr(l)` is computed from yearly values and applied to every snapshot (D8).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh`.

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no agriculture loads in a location (e.g. `CH`, SC-26) / in `n` | `0.0` (C6.13) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A`, 1 snapshot: Loads `agriculture electricity` 2, `agriculture machinery electric` 1, `agriculture machinery oil` 4; `agriculture heat` 3 and `rural heat` 9 on the `rural heat` bus (`σ_rural,agr = 0.25`); rural heat inputs `rural biomass boiler` 8 and `rural ground heat pump` electricity 4 (`I_rural = 12`); an `agriculture machinery oil CC` link with input 5 and output 4. Result `(A, MWh): 2 + 1 + 4 + 0.25·12 = 10`.
- AC3b: As AC3, plus a `biogas CHP` with biogas input 10, electricity output 2 to `AC` and heat output 4 to `rural heat` (`rural heat` Load 13, so `σ_rural,agr = 3/16`). `I_rural = 12 + 4 = 16` (heat output, not input). Result `(A, MWh): 2 + 1 + 4 + 3/16·16 = 10`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6 (incl. a location without agriculture loads).

## 12. Open questions
None specific. OQ-22, OQ-25 resolved (D8).

## 13. Sources
- #13, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2553-2565 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Agriculture` l.1011-1089 (commit `16bf37f`). Difference: SC-34
