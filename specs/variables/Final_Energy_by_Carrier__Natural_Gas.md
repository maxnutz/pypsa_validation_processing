# `Final Energy [by Carrier]|Natural Gas`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Carrier]\|Natural Gas` |
| Function name | `Final_Energy_by_Carrier__Natural_Gas` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #45; enhancements #61, #74; bug #97 |
| Variable name | `Final Energy [by Carrier]\|Natural Gas` |
| Description | Energy consumption of fossil methane excluding transmission/distribution losses (#45) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Natural Gas` ("fossil methane") |

```yaml
- Final Energy [by Carrier]|{Final Energy Carrier}:
    description: Energy consumption of {Final Energy Carrier}
      excluding transmission/distribution losses
    unit: TJ
# {Final Energy Carrier} = Natural Gas: "fossil methane"
```
Issue #97 (owner): "Final Energy - variables must stay positive. Ever."

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_LHV` | gas and `gas for industry` buses |
| Normalised unit | `MWh` | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy`, `_get_fuel_fractions` |
| pypsa-de line range | `export_ariadne_variables.py:L2135-L2152, L2352-L2368, L2633-L2640; L109-L242` |
| pypsa-de variable name | `Final Energy\|Gases\|Natural Gas` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- The fossil share `f_gas` is adapted to the PyPSA-AT gas topology (D3). It is system-wide, as in pypsa-de (owner decision 2026-10-22), and replaces the current regional, clipped production/usage ratio.
- Non-energy use is subtracted per D5, method open (OQ-18). It replaces the static EU-27 Eurostat factor of the current code (#61).
- Per location (D1); no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `semantic`.
- Reasoning: pypsa-de `Final Energy|Gases|Natural Gas` = `Final Energy|Gases` × natural-gas fraction. `Final Energy|Gases` covers residential/commercial gas boilers and industry gas excluding non-energy use. "Natural Gas" = fossil methane (tag definition) = the non-biogenic, non-synthetic share.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Link | `rural gas boiler`, `urban decentral gas boiler` | `gas` | withdrawal (bus0) | yes | l.2352-2362 |
| Load | `gas for industry` | `gas for industry` | withdrawal | yes, minus `NE_gas` (D5) | l.2135-2146 |
| Link | `gas for industry`, `gas for industry CC` | `gas` → `gas for industry` | – | **no** (delivery to the Load bus; counting it would double count the Load) | carriers table |
| Link | `urban central gas boiler`, `urban central gas CHP*`, `CCGT`, `OCGT`, `SMR*` | `gas` | – | **no** (transformation) | l.2633-2636 |
| Generators / Links for `f_gas` | see D3 | `gas` | supply | share only | D3 |

## 7. Accounting rule and sign convention
- Formula: `FE_ng(l) = f_gas · ( W[gas, rural gas boiler](l) + W[gas, urban decentral gas boiler](l) + L[gas for industry](l) − NE_gas(l) )`
- Sign convention: withdrawals counted **positive**. The boiler flow is a withdrawal at bus0 and MUST enter with a positive sign. Result MUST be ≥ 0 (#97).
- Weighting: per C6.10; `f_gas` is the yearly scalar for every snapshot (D3).
- Special cases: non-energy use (D5).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_LHV` (or `MWh`).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no gas boilers and no `gas for industry` in a location / in `n` | `0.0` per location (C6.13); never a zero-row Series (SC-25) |
| no fossil gas supply (`f_gas = 0`) | `0.0` for all locations |
| total gas supply 0 | `f_gas = 0` (D3) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock: `production gas` Generator supplies 60, `biogas to gas` supplies 40 (`f_gas = 0.6`). At `A`, `rural gas boiler` withdraws 10 and the `gas for industry` Load is 20, with `NE_gas = 0`. Over 1 snapshot, weighting 1: result `(A, …): 18`.
- AC4: C6-AC3 (`flow`), on a network with weighting ≠ 1 and time-varying gas supply (regression for SC-23).
- AC5: The result is ≥ 0 for every location, also when the renewable gas supply of one location exceeds its demand (regression for #97).
- AC6: C6-AC6.
- AC7: `gas pipeline` flows and the `gas` Store do not change `f_gas`.
- AC8: An unknown carrier with non-zero yearly supply to a gas bus raises `ValueError` naming the carrier (D3); an unknown carrier with zero supply is ignored. An `import gas` Link supplying 40 instead of `biogas to gas` in the mock of AC3 gives the same result (`f_gas = 0.6`).

## 12. Open questions
- OQ-18 (method for `NE_gas`). OQ-23 resolved (`import gas` non-fossil, D3).

## 13. Sources
- #45, #61, #74, #97; definitions as in section 2
- `export_ariadne_variables.py` l.109-242, 2135-2152, 2352-2368, 2633-2640 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__Natural_Gas` l.565-694 (commit `16bf37f`). Differences: SC-23, SC-25, SC-27
