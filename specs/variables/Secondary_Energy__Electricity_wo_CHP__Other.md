# `Secondary Energy|Electricity w/o CHP|Other`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Secondary Energy\|Electricity w/o CHP\|Other` |
| Function name | `Secondary_Energy__Electricity_wo_CHP__Other` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml`, short form `Secondary Energy\|Electricity w/o CHP\|Other: Secondary_Energy__Electricity_wo_CHP__Other` (C4.1) |
| Aggregation class | `flow` (C4.5, default) |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed (`w/o` → `wo`).

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #195 (milestone "Implement Infra-Enshure Coupling Variables"; renamed 2026-11-25, infra-ensure/coupling-variables#8) |
| Variable name | `Secondary Energy\|Electricity w/o CHP\|Other` |
| Description | Total net generation of electricity from sources not reported under coal, oil, gas grid mix, solar, wind, hydro, solid biomass or waste (e.g. biogas), excluding electricity storage, excluding combined heat and power plants (CHPs) |
| Unit | `TWh` |
| Contained in a definitions folder? | `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`). Not in the common definitions; the common `Secondary Energy\|Electricity\|Other` does not exist. |

```yaml
- Secondary Energy|Electricity w/o CHP|Other:
    description: Total net generation of electricity from sources not reported under coal, oil, gas grid mix,
      solar, wind, hydro, solid biomass or waste (e.g. biogas), excluding electricity storage,
      excluding combined heat and power plants (CHPs)
    unit: TWh
```

The issue cites commit `97bcf66`; the entry above is from commit `30202ec` (names changed in PR #9, `Other` wording in PR #7 and PR #9).

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) returned by the function | `MWh_el` (unit of the `AC` and `low voltage` buses) | `n.statistics.supply(bus_carrier=["AC", "low voltage"], groupby=[…, "unit"])`; D10 |
| Normalised unit (`utils.UNITS_MAPPING`) | `MWh` (key `MWh_el`) | `utils.py::UNITS_MAPPING` |
| Target unit | `TWh` (definition) | C9 |
| Conversion | `MWh` → `TWh`, factor `1e-6`, in `Network_Processor` (C9), not in the function | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` (via the D10 helper in `utils.py`) |
| pypsa-de function | `get_secondary_energy` |
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L1548-L1558` (supply), `:L1612-L1659` (variable) |
| pypsa-de variable name | `Secondary Energy\|Electricity\|Nuclear` (l.1628-1630) + `…\|Hydrogen` without `urban central H2 CHP`, `urban central H2 retrofit CHP` (l.1648-1659) + `…\|Biomass\|Gaseous and Liquid` (`biogas`, l.1612-1614) |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as far as needed for the function contract:
- Region = location (D10, D1.2: location of the `AC`/`low voltage` bus at the supplying port; Generators and StorageUnits: location of their bus) instead of `.filter(like=region)` on the component name; per-location values are aggregated to the country by C8.
- Carrier lists from the shared D10 table in `utils.py` instead of `filter(like=…)` on carrier names (D10, P4).
- Time series for `aggregate_per_year=False` (`groupby_time=False`, C6.10); pypsa-de reports yearly values only.
- Unclassified carriers give a `WARNING` (D10 rule 4, OQ-39); pypsa-de checks completeness with an `isclose` assertion (l.1744-1751).

Deviations decided by the owner (P6.1):
- CHPs excluded: `urban central H2 CHP`, `urban central H2 retrofit CHP`, `biogas CHP` are not counted (definition; owner 2026-11-11/16; D10). They are in `Secondary Energy|Electricity|CHP|Other`.
- `H2 turbine` added: pypsa-de lists it as a to-do (l.1659 comment "Add H2 Turbines if they get implemented"); it occurs in the networks (D10).
- Methanol plants `CCGT methanol`, `CCGT methanol CC`, `OCGT methanol`, `allam methanol` added: not evaluated by pypsa-de; they are sources not reported elsewhere (definition; D10, PR #213).
- `H2 Fuel Cell` electricity counted here, not as CHP (OQ-37, owner 2026-11-25), as in pypsa-de `…|Hydrogen`.

## 5. Match type
- Match type: `semantic`
- Reasoning: pypsa-de has no `Other` electricity variable; the definition defines `Other` as the rest of the classified sources. Its carriers are those of three pypsa-de variables (Nuclear, Hydrogen, Biomass|Gaseous and Liquid) without the H2 CHPs, plus carriers pypsa-de does not evaluate. Semantic match (P6.2) of the sum, with the deviations below.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| Link | `nuclear` | `AC` | bus1 (output), supply | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Link | `biogas` | `AC` | bus1 (output), supply | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Link | `H2 CCGT`, `H2 OCGT`, `H2 retrofit CCGT`, `H2 retrofit OCGT`, `H2 turbine`, `H2 Fuel Cell` | `AC` | supply at the `AC` port; `H2 Fuel Cell` is not a CHP (OQ-37), its heat port is not evaluated here | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Link | `CCGT methanol`, `CCGT methanol CC`, `OCGT methanol`, `allam methanol` | `AC` | supply at the `AC` port | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Link | CHPs of this fuel (D10 table, `Electricity\|CHP\|Other`) | `AC`, `low voltage` | any port | no (definition) | D10 rule 1 |
| Line, Link, StorageUnit, Load | D10 excluded row (transport, storage, `electricity` Load) | `AC`, `low voltage` | – | no | D10 |

Measured with the D10 classification (`resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc`, pypsa 1.1.2, 2026-11-25; yearly supply, snapshot weighting applied):

| | AT 2025 | AT 2040 | all locations 2025 | all locations 2040 |
|---|---|---|---|---|
| `Secondary Energy\|Electricity w/o CHP\|Other` [TWh] | 0.000 | 0.906 | 547.17 | 756.70 |

AT 2040: `H2 Fuel Cell` 0.906 TWh; all other carriers 0.000 in AT (no nuclear in AT; `nuclear` 544.68 TWh at all locations in 2025). No unclassified carrier on either network (D10 rule 4). These values are a plausibility check for the implementing PR, not acceptance criteria.

## 7. Accounting rule and sign convention
- Formula: `value(l) = E[w/o CHP|Other](l) = Σ_{c ∈ C_el} S[{AC, low voltage}, c](l)` with `C_el` = `nuclear`, `biogas`, `H2 CCGT`, `H2 OCGT`, `H2 retrofit CCGT`, `H2 retrofit OCGT`, `H2 turbine`, `H2 Fuel Cell`, `CCGT methanol`, `CCGT methanol CC`, `OCGT methanol`, `allam methanol` (D10).
- Sign convention: supply, `≥ 0` at every location and snapshot (D10 rule 5); no negative per-snapshot supply measured on either network (the negative `electricity` Loads are excluded, OQ-38).
- Weighting: `flow` per C6.10 (yearly: weighted sum over snapshots; time series: unweighted per-snapshot values).
- Special cases ported from pypsa-de: none beyond section 4.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | switch Series / DataFrame (C6) | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |
| `industry_non_energy_shares` | no | – | – |

## 9. Return format
- `aggregate_per_year=True`: `pd.Series`, MultiIndex `[location, unit]`, values = weighted sum over snapshots in `MWh_el` (C6.10).
- `aggregate_per_year=False`: `pd.DataFrame`, MultiIndex `[location, unit]`, columns = snapshots of `n`, values as returned by `n.statistics.supply(…, groupby_time=False)`, not multiplied by the snapshot weighting (C6.10).
- No country aggregation inside the function (C6, C8).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| none of the carriers present in a location | `0.0` for this location (every snapshot with `aggregate_per_year=False`), unit `MWh_el`; the location is not dropped (C6.13) |
| none of the carriers present in the network | `0.0` for every location of `n.buses.location` (C6.13); `n.statistics.supply` returns an empty `pd.Series` in this case, which the function MUST turn into `0.0` rows |
| only some carriers present in a location | absent carriers contribute `0.0` |
| copperplate pseudo-location `EU` | returned like any location (C6.13), dropped by `Network_Processor` (C8.7) |
| special case | Storage (`PHS`, `PHS discharger`, `battery discharger`, `home battery discharger`, `V2G`) and transport carriers are excluded (D10, definition "excluding electricity storage"). |
| time series and yearly results disagree | must not happen (C6-AC3) |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1 (Series, MultiIndex with `location` and `unit`, ≥ 1 row, numeric dtype, valid units, locations in `n.buses.location`). All-zero values are valid.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2 (DataFrame, not Series; exactly the snapshots of `n` as columns; otherwise as AC1).
- AC3: Mock network, locations `A`, `B`, buses `A AC`, `B AC`, `A H2`, `A biogas`, `EU uranium`; Link `nuclear` from `EU uranium` to `B AC`, `efficiency = 0.33`, `p0 = [30, 30]` MW; Link `H2 Fuel Cell` from `A H2` to `A AC` (`bus1`, `efficiency = 0.5`) and an `urban central heat` bus (`bus2`, `efficiency2 = 0.4`), `p0 = [10, 0]` MW; Link `biogas` from `A biogas` to `A AC`, `efficiency = 0.4`, `p0 = [0, 10]` MW; Link `urban central H2 CHP` from `A H2` to `A AC`, `p0 = [10, 10]` MW; StorageUnit `PHS` and Link `battery discharger` at `A AC` with dispatch `[1, 1]` MW; 2 snapshots, weighting 1. Yearly: `A` = 9, `B` = 19.8. Snapshots: `A` = `[5, 4]`, `B` = `[9.9, 9.9]` (CHP and storage not counted; heat of `H2 Fuel Cell` not counted).
- AC3a: As AC3 with snapshot weighting 2: yearly values doubled, snapshot values unchanged (C6.10).
- AC4: The `True` and `False` results are consistent per C6-AC3 (`flow`); every value is `≥ 0` (D10 rule 5).
- AC5: C6-AC6: in AC3, a location without any of the carriers (e.g. add location `C` with bus `C AC` only) is present with `0.0`; a mock network without any of the carriers returns `0.0` for every location of `n.buses.location`, not `None` and not zero rows.
- AC6 (CHPs excluded, any port order): adding to the AC3 network a CHP Link of this fuel (D10 table, `Electricity|CHP|Other`) with `AC` at `bus1` and `urban central heat` at `bus2`, and a second one with heat at `bus1` and `AC` at `bus2`, does not change the result (D10 rule 1).
- AC7 (excluded carriers): adding a `PHS` StorageUnit, a `battery discharger` Link, an `AC` Line and an `electricity` Load with negative `p_set` at `A` does not change the result (D10 excluded row, OQ-38).
- AC8 (unclassified carrier): adding a Generator with an unknown carrier (e.g. `geothermal`) at `A AC` does not change the result and logs one `WARNING` naming `geothermal` and its yearly supply in TWh (D10 rule 4, OQ-39).

## 12. Open questions
None.

## 13. Sources
- #195, milestone "Implement Infra-Enshure Coupling Variables"; infra-ensure/coupling-variables#8 (rename, PR #9)
- `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`)
- `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` l.1548-1558, l.1612-1659 (commit `a5baa7e9`)
- PyPSA statistics accessor (`supply`): https://docs.pypsa.org/latest/api/networks/statistics/
- measurement on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` (2026-11-25)
- D1, D10 in [shared_definitions.md](shared_definitions.md); C4.5, C6.10, C6.13, C8, C9 in [../contracts.md](../contracts.md); OQ-37–OQ-40 in [../open_questions.md](../open_questions.md)
