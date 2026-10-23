# `Final Energy [by Sector]|Industry`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Sector]\|Industry` |
| Function name | `Final_Energy_by_Sector__Industry` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #12; enhancement #74 |
| Variable name | `Final Energy [by Sector]\|Industry` |
| Description | Energy consumption by the industrial sector excluding non-energy use (e.g.feedstocks) excluding transmission/distribution losses (#2) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Industry` in `tag_sector.yaml` |

```yaml
- Final Energy [by Sector]|{Sector}:
    description: Energy consumption by the {Sector}
      excluding transmission/distribution losses
    unit: TJ
# {Sector} = Industry: "industrial sector excluding non-energy use (e.g.feedstocks)"
```
#74: "distinguish between energy use and non energy use in industry sector … stick to the implementation in export_adriane_variables."

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
| pypsa-de line range | `export_ariadne_variables.py:L2034-L2093, L2113-L2276` |
| pypsa-de variable name | `Final Energy\|Industry excl Non-Energy Use` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- `NE_x` and `κ` cannot be computed from the pypsa-de inputs (D5, D6); method open (OQ-18).
- Decentral `low-temperature heat for industry` (on `urban decentral heat`) is not counted as heat. Instead, the industrial share of the decentral heat input is counted (D8, owner decision 2026-10-22, OQ-22 resolved). The Load on `urban central heat` stays counted as delivered heat (district heat is a final energy carrier).
- Per location; no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `semantic`.
- Reasoning: the IAMC sector "Industry" excludes non-energy use. That equals pypsa-de `Final Energy|Industry excl Non-Energy Use`, not `Final Energy|Industry` (which includes it).

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `industry electricity` | `low voltage` | withdrawal | yes | l.2113-2119 |
| Load | `low-temperature heat for industry` on `urban central heat` | `urban central heat` | withdrawal (heat) | yes | l.2121-2127 |
| Load | `low-temperature heat for industry` on `urban decentral heat` | `urban decentral heat` | used only as heat demand for `σ_urban decentral,ind(l)` (D8) | **no** (as heat) | l.2121-2127 |
| Links / Generators | decentral heat supply of `urban decentral heat` (D8) | input carriers | input × `σ_urban decentral,ind(l)` | yes | D8 |
| Load | `gas for industry` | `gas for industry` | withdrawal − `NE_gas` | yes | l.2135-2146 |
| Load | `H2 for industry` | `H2` (`AT_KN2040`) or `H2 for industry` (`electricity_network_0p3`, `20261020_carbon_accounting_run`; supplied by the Links `H2 for industry` and `methane pyrolysis plasma`) | withdrawal − `NE_H2`; identified by the Load carrier, not by the bus carrier | yes | l.2157-2162 |
| Load | `naphtha for industry` | `naphtha for industry` | withdrawal − `NE_naphtha` | yes | l.2192-2197 |
| Load | `solid biomass for industry` | `solid biomass for industry` | withdrawal | yes | l.2201-2206 |
| Load | `coal for industry` | `coal for industry` | withdrawal with coke correction (D6) | yes | l.2208-2228 |
| Load | `industry methanol` | `industry methanol` | – | **no** (not counted in pypsa-de; chemical feedstock) | l.2253-2262 |
| Link | `… for industry CC`, `… for industry` (supply links) | – | – | **no** (efficiency losses of supply links are not final energy; the Load is counted) | l.2253-2262 |

## 7. Accounting rule and sign convention
- Formula: `FE_ind(l) = L[industry electricity](l) + L[low-temperature heat for industry @ urban central heat](l) + D8_ind(l) + L[gas for industry](l) − NE_gas(l) + L[H2 for industry](l) − NE_H2(l) + L[naphtha for industry](l) − NE_naphtha(l) + L[solid biomass for industry](l) + FE_coal_industry(l)` (D5, D6)
- Sign convention: withdrawals positive; result MUST be ≥ 0.
- Weighting: per C6.10.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | open | pypsa-de reads `config["sector"]["ammonia"]` and `config_industry` for ammonia (l.2034-2058); depends on OQ-18 | per OQ-6 |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh`.

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no industry loads in a location / in `n` | `0.0` (C6.13) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A`, 1 snapshot, all `NE = 0`, `κ = 0`: Loads `industry electricity` 10, `low-temperature heat for industry` 5 on `urban central heat`, `gas for industry` 8, `H2 for industry` 2, `naphtha for industry` 6, `solid biomass for industry` 3, `coal for industry` 4, `industry methanol` 7; `gas for industry CC` link with input 10 and output 9. Result `(A, MWh): 38`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6.
- AC7: With `NE_gas = 3` injected (OQ-18 method), the result decreases by exactly 3.
- AC8: Mock at `B` without `urban central heat` bus: `low-temperature heat for industry` 1 and `urban decentral heat` Load 3 on `urban decentral heat` (`σ = 0.25`), `urban decentral gas boiler` gas input 6. The decentral heat contribution to the result is `0.25·6 = 1.5`, not 1.

## 12. Open questions
- OQ-18.

## 13. Sources
- #12, #74, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2034-2093, 2113-2276 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Industry` l.925-1008 (commit `16bf37f`). Difference: SC-33
