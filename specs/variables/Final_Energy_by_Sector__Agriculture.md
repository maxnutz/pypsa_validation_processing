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
- `agriculture heat` is not counted as heat, because final energy is measured at the consumer (G1). In PyPSA-AT the `agriculture heat` Load sits only on `rural heat` buses (measured: 51 of 51 Loads in `20261020_carbon_accounting_run` 2040, 76 of 76 in `electricity_network_0p3` 2025). It is met by decentral supply at the consumer, not by a heat network. Its final energy is therefore the input of that supply (electricity of heat pumps and resistive heaters, gas, oil, biomass) plus the heat received from decentral CHPs and solar thermal, i.e. the agricultural share of the `rural heat` input (D8; owner decision 2026-10-22, OQ-22 resolved). pypsa-de counts `agriculture heat` as heat and the same input again in Residential and Commercial (double count, D8).
- Per location; no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `exact`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `agriculture electricity`, `agriculture machinery electric` | `low voltage` | withdrawal | yes | l.2553-2555 |
| Load | `agriculture heat` | `rural heat` | used only as heat demand for the share `σ_rural,agr(l)` (D8) | **no** (as heat; decentral bus, its final energy is the D8 input, G1) | l.2556 |
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
| `agriculture heat` Load on an `urban central heat` bus | `ValueError` naming the Load (P5). Not in the measured networks; delivered district heat would count as heat (G1), which needs a spec change (loss factor, consistency with `Final Energy [by Carrier]\|District Heat`) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A`, 1 snapshot: Loads `agriculture electricity` 2, `agriculture machinery electric` 1, `agriculture machinery oil` 4; `agriculture heat` 3 and `rural heat` 9 on the `rural heat` bus (`σ_rural,agr = 0.25`); rural heat inputs `rural biomass boiler` 8 and `rural ground heat pump` electricity 4 (`I_rural = 12`); an `agriculture machinery oil CC` link with input 5 and output 4. Result `(A, MWh): 2 + 1 + 4 + 0.25·12 = 10`.
- AC3b: As AC3, plus a `biogas CHP` with biogas input 10, electricity output 2 to `AC` and heat output 4 to `rural heat` (`rural heat` Load 13, so `σ_rural,agr = 3/16`). `I_rural = 12 + 4 = 16` (heat received by consumers from the CHP, G1; neither the biogas input 10 nor the electricity 2). Result `(A, MWh): 2 + 1 + 4 + 3/16·16 = 10`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6 (incl. a location without agriculture loads).

## 12. Open questions
None specific. OQ-22, OQ-25 resolved (D8).

## 13. Sources
- #13, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2553-2565 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Agriculture` l.1011-1089 (commit `16bf37f`). Difference: SC-34
