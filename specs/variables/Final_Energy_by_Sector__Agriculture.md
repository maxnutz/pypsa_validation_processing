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

Changes to the ported logic, only as needed for the function contract: per location; no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `exact`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `agriculture electricity`, `agriculture machinery electric` | `low voltage` | withdrawal | yes | l.2553-2555 |
| Load | `agriculture heat` | `rural heat` | withdrawal (heat, `MWh_th`) | yes | l.2556 |
| Load | `agriculture machinery oil` | `agriculture machinery oil` | withdrawal | yes | l.2557-2559 |
| Link | `agriculture machinery oil` (supply), `agriculture machinery oil CC` | – | – | **no** (supply-link losses are not final energy) | l.2553-2565 |

## 7. Accounting rule and sign convention
- Formula: `FE_agr(l) = L[agriculture electricity](l) + L[agriculture machinery electric](l) + L[agriculture heat](l) + L[agriculture machinery oil](l)`
- Sign convention: withdrawals positive; result MUST be ≥ 0.
- Weighting: per C6.10.
- Note: `agriculture heat` is counted as heat, while the fuels of the decentral boilers and heat pumps that supply the `rural heat` bus are counted in `Final Energy [by Sector]|Residential and Commercial` (pypsa-de l.2352-2409). Across both sectors this can double count (OQ-22).

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
- AC3: Mock at `A`, 1 snapshot: Loads 2 + 1 + 3 + 4, plus an `agriculture machinery oil CC` link with input 5 and output 4. Result `(A, MWh): 10`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6 (incl. a location without agriculture loads).

## 12. Open questions
- OQ-22 (double counting of decentral heat across sectors).

## 13. Sources
- #13, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2553-2565 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Agriculture` l.1011-1089 (commit `16bf37f`). Difference: SC-34
