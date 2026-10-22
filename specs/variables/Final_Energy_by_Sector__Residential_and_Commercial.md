# `Final Energy [by Sector]|Residential and Commercial`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Sector]\|Residential and Commercial` |
| Function name | `Final_Energy_by_Sector__Residential_and_Commercial` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #14 |
| Variable name | `Final Energy [by Sector]\|Residential and Commercial` |
| Description | Energy consumption by the commercial (services) and residential sector (buildings and households) excluding transmission/distribution losses (#2) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Residential and Commercial` in `tag_sector.yaml` |

```yaml
- Final Energy [by Sector]|{Sector}:
    description: Energy consumption by the {Sector}
      excluding transmission/distribution losses
    unit: TJ
# {Sector} = Residential and Commercial: "commercial (services) and residential sector (buildings and households)"
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
| pypsa-de line range | `export_ariadne_variables.py:L2278-L2419` |
| pypsa-de variable name | `Final Energy\|Residential and Commercial` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, with reason:
- The `urban central heat` Load is divided by `1 + λ` (distribution losses), as in `Final Energy [by Carrier]|District Heat` (owner decision 2026-10-22, OQ-21 resolved).
- Per location (D1); no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `exact`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load / Link | every carrier withdrawing from `low voltage` whose name does **not** contain `urban central`, `industry`, `agriculture`, `charger`, `distribution` | `low voltage` | withdrawal | yes (electricity) | l.2278-2302 |
| Load | `urban central heat` | `urban central heat` | withdrawal ÷ (1 + λ) | yes (heat) | l.2345-2348 |
| Generator | `rural solar thermal`, `urban decentral solar thermal` | `rural heat`, `urban decentral heat` | supply × `s(l)` | yes (heat) | l.2305-2350 |
| Link | `rural gas boiler`, `urban decentral gas boiler` | `gas` | withdrawal (bus0) | yes | l.2352-2362 |
| Link | `rural oil boiler`, `urban decentral oil boiler` | `oil` | withdrawal (bus0), location D1 | yes | l.2372-2381 |
| Link | `rural biomass boiler`, `urban decentral biomass boiler` | `solid biomass` | withdrawal (bus0) | yes | l.2398-2409 |
| Link | `home battery charger`/`discharger`, `BEV charger`, `DAC`, water-tank/pit chargers | – | – | **no** | l.2293, 2316-2321 |

`s(l)` = residential/commercial fraction of decentral heat = `(L[rural heat](l) + L[urban decentral heat](l)) / Σ W[{rural heat, urban decentral heat}, c](l)` over all withdrawing carriers except the water-tank/pit chargers (l.2305-2329). If the denominator is 0, then `s(l) = 0`.

## 7. Accounting rule and sign convention
- Formula: `FE_rc(l) = Σ W[low voltage, c](l) (set above) + L[urban central heat](l)/(1 + λ) + s(l)·S[decentral heat, solar thermal](l) + W[gas, gas boilers](l) + W[oil, oil boilers](l) + W[solid biomass, biomass boilers](l)`
- `λ` as in the District Heat spec (`config["sector"]["district_heating"]["district_heating_loss"]`).
- Sign convention: all terms positive (withdrawals and supply counted as positive amounts); result MUST be ≥ 0.
- Weighting: per C6.10. `s(l)` is computed from yearly values and applied to every snapshot.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | yes | `λ` | per OQ-6 (proposal: skip with `WARNING`) |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh`.

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no carriers in a location / in `n` | `0.0` (C6.13) |
| no decentral heat withdrawal | `s(l) = 0` |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A`, 1 snapshot, `λ = 0.15`: LV Load `electricity` 10, `rural air heat pump` withdrawal 2, `home battery charger` 1, `BEV charger` 3; `urban central heat` Load 23; `rural gas boiler` gas withdrawal 4; `rural oil boiler` oil withdrawal 2 from `EU oil` with bus1 at `A`; `rural biomass boiler` 1; rural solar thermal supply 2, with `rural heat` Load 6 and `agriculture heat` 2 the only decentral withdrawals (`s = 0.75`). Result `(A, MWh): 10 + 2 + 20 + 1.5 + 4 + 2 + 1 = 40.5`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0 (regression: gas, oil and biomass boiler terms are positive).
- AC6: C6-AC6.

## 12. Open questions
- OQ-22 (double counting with agriculture/industry decentral heat), OQ-6.

## 13. Sources
- #14, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2278-2419 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Residential_and_Commercial` l.1092-1226 (commit `16bf37f`). Difference: SC-35
