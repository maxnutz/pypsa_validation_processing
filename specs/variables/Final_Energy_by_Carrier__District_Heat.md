# `Final Energy [by Carrier]|District Heat`

Status: reviewed
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Carrier]\|District Heat` |
| Function name | `Final_Energy_by_Carrier__District_Heat` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #63; enhancement #73 |
| Variable name | `Final Energy [by Carrier]\|District Heat` |
| Description | Energy consumption of heat delivered from district heating grids excluding transmission/distribution losses (#63) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `District Heat` ("heat delivered from district heating grids") |

```yaml
- Final Energy [by Carrier]|{Final Energy Carrier}:
    description: Energy consumption of {Final Energy Carrier}
      excluding transmission/distribution losses
    unit: TJ
# {Final Energy Carrier} = District Heat: "heat delivered from district heating grids"
```

Owner decision (2026-10-22): the variable measures what its definition says, **heat delivered from district heating grids to consumers**, without distribution losses. This replaces the reading in the #63 comment ("Energy Demand for District Heat … accounting on bus0", i.e. the fuel input of district heating plants). It resolves #73, because only heat (`MWh_th`) is summed.

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_th` | `urban central heat` buses (measured) |
| Normalised unit | `MWh` | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` (partial) |
| pypsa-de function | `get_final_energy` |
| pypsa-de line range | `export_ariadne_variables.py:L2121-L2127, L2345-L2350, L2575-L2589` |
| pypsa-de variable name | none for district heat alone; components of `Final Energy\|Heat` (l.2661-2666) |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, with reason:
- Only the parts delivered from `urban central heat` buses are taken (definition).
- The `urban central heat` Load is divided by `1 + λ` to exclude distribution losses (definition). pypsa-de counts the Load including losses. Owner decision 2026-10-22 (OQ-21 resolved): consistency with the definition takes precedence; the correction is applied and checked against real data during implementation.

## 5. Match type
- Match type: `semantic` (partial).
- Reasoning: pypsa-de `Final Energy|Heat` also contains agriculture heat (on `rural heat`), decentral solar thermal and decentral industry heat. These are not "delivered from district heating grids". So only the `urban central heat` components are ported.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `urban central heat` | `urban central heat` | withdrawal ÷ (1 + λ) | yes | l.2345-2348; losses: `prepare_sector_network.py` l.3153-3160 |
| Load | `low-temperature heat for industry` on `urban central heat` buses | `urban central heat` | withdrawal | yes (no loss factor is applied to this Load in pypsa-eur) | l.2121-2123; `prepare_sector_network.py` l.5280-5294 |
| Link | `DAC` | `urban central heat` | withdrawal only (heat port `bus1`, `efficiency` < 0) | yes, as heat consumer (CDR heat demand, l.2575-2589); **never** as heat producer | l.2587-2589 |
| Link | `urban central water pits charger`, `urban central water tanks charger` | `urban central heat` | – | **no** (storage) | l.2316-2321 (decentral analogue) |
| Generator | `urban central heat vent` | `urban central heat` | – | **no** (dumped heat, not consumed) | #73 |
| Links | supplying links (CHP, boilers, heat pumps, …) | – | – | **no** (supply side; counted in the current code at bus0, SC-29) | #63 comment, #73 |

Measured withdrawals from `urban central heat` in 2040 (TWh): Load `urban central heat` 503.11, `low-temperature heat for industry` 96.99, `water pits charger` 145.99, `water tanks charger` 0.04, `heat vent` 20.79, `DAC` 0.00.

## 7. Accounting rule and sign convention
- Formula: `FE_dh(l) = L[urban central heat](l) / (1 + λ) + L[low-temperature heat for industry @ urban central heat](l) + W[urban central heat, DAC](l)`
- `λ = config["sector"]["district_heating"]["district_heating_loss"]` (measured: 0.15 in `config.base_s_adm__none_2040.yaml` l.1807).
- `DAC` is counted only as a heat consumer. A `DAC` Link whose port at an `urban central heat` bus supplies heat (`efficiency` at that port > 0, or a negative withdrawal in any snapshot) → `ValueError` naming the Link (P5). Measured (`20261020_carbon_accounting_run` 2030–2050): every `DAC` Link has `bus1` = `… urban central heat` with `efficiency` = −2.545 and `p1 ≥ 0` in every snapshot (2050: 0.333 TWh withdrawal).
- Any other component that withdraws from `urban central heat` buses with a carrier not listed in section 6 → `ValueError` naming the carrier (P5).
- Sign convention: withdrawals positive; result MUST be ≥ 0.
- Weighting: per C6.10.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | yes | `config["sector"]["district_heating"]["district_heating_loss"]` | taken from `n.meta` if present (C2.3, OQ-27); `config=None` (no `n.meta`, no config file) → variable skipped with `WARNING` (C2.3); missing key → the function raises `utils.MissingInputError`, variable skipped with `WARNING`; no default value (OQ-6) |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_th` (or `MWh`).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| location without `urban central heat` bus (e.g. 2020 `progress = 0`) | `0.0` (C6.13) |
| `low-temperature heat for industry` on `urban decentral heat` bus | not counted |
| no district heating in `n` | `0.0` for every location |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A`: `urban central heat` Load 115, `low-temperature heat for industry` on the central bus 10 and on a decentral bus 7, `DAC` heat withdrawal 5, water-pit charger 20, heat vent 3. `λ = 0.15`, 1 snapshot. Result `(A, …): 100 + 10 + 5 = 115`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6.
- AC7: The result does not depend on the efficiencies of the heat-supplying links (changing a CHP efficiency in the mock leaves the result unchanged).
- AC8: An unknown withdrawing carrier on `urban central heat` raises `ValueError`.
- AC9: A `DAC` Link with a positive `efficiency` at its `urban central heat` port (heat supply) raises `ValueError`; it is never counted as heat.

## 12. Open questions
- None specific. OQ-6, OQ-21 resolved.

## 13. Sources
- #63 (incl. comment), #73; definitions as in section 2
- `export_ariadne_variables.py` l.2121-2127, 2345-2350, 2575-2589, 2661-2666 (commit `a5baa7e9`)
- `sister_packages/pypsa-de/scripts/prepare_sector_network.py` l.3134-3170, 5280-5294
- `resources/AT_KN2040/configs/config.base_s_adm__none_2040.yaml` l.1795-1807
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__District_Heat` l.697-787 (commit `16bf37f`). Difference: SC-29
