# `Secondary Energy|Electricity w/o CHP|Waste`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Secondary Energy\|Electricity w/o CHP\|Waste` |
| Function name | `Secondary_Energy__Electricity_wo_CHP__Waste` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml`, short form `Secondary Energy\|Electricity w/o CHP\|Waste: Secondary_Energy__Electricity_wo_CHP__Waste` (C4.1) |
| Aggregation class | `flow` (C4.5, default) |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed (`w/o` → `wo`).

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #194 (milestone "Implement Infra-Enshure Coupling Variables"; renamed 2026-11-25, infra-ensure/coupling-variables#8) |
| Variable name | `Secondary Energy\|Electricity w/o CHP\|Waste` |
| Description | Total net generation of electricity from burning of waste, excluding combined heat and power plants (CHPs) |
| Unit | `TWh` |
| Contained in a definitions folder? | `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`). Not in the common definitions; the common `Secondary Energy\|Electricity\|Waste` includes CHPs and is a different variable (not specified, not mapped). |

```yaml
- Secondary Energy|Electricity w/o CHP|Waste:
    description: Total net generation of electricity from burning of waste, excluding combined heat and power
      plants (CHPs)
    unit: TWh
```

The issue cites commit `97bcf66`; the entry above is from commit `30202ec` (names changed in PR #9).

> **Scope note:** this variable is structurally `0.0`: every waste-fired plant in PyPSA-AT is a CHP (D10, OQ-40). A result of `0.0` is correct and MUST NOT be taken for an evaluation error.

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
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L1548-L1558` (supply), `:L1661-L1663` (variable) |
| pypsa-de variable name | `Secondary Energy\|Electricity\|Waste` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as far as needed for the function contract:
- Region = location (D10, D1.2: location of the `AC`/`low voltage` bus at the supplying port; Generators and StorageUnits: location of their bus) instead of `.filter(like=region)` on the component name; per-location values are aggregated to the country by C8.
- Carrier lists from the shared D10 table in `utils.py` instead of `filter(like=…)` on carrier names (D10, P4).
- Time series for `aggregate_per_year=False` (`groupby_time=False`, C6.10); pypsa-de reports yearly values only.
- Unclassified carriers give a `WARNING` (D10 rule 4, OQ-39); pypsa-de checks completeness with an `isclose` assertion (l.1744-1751).

Deviations decided by the owner (P6.1):
- CHPs excluded: `waste CHP`, `waste CHP CC` are not counted (definition; owner 2026-11-11/16; D10). They are in `Secondary Energy|Electricity|CHP|Waste`.
- Structurally zero: empty carrier list, `0.0` at every location (OQ-40, owner 2026-11-25).

## 5. Match type
- Match type: `semantic`
- Reasoning: pypsa-de `Secondary Energy|Electricity|Waste` = `filter(like="waste CHP")` (l.1661-1663), i.e. only CHPs. Without CHPs nothing remains: every waste-fired plant in PyPSA-AT is a `waste CHP` or `waste CHP CC` (all 13 networks, D10; OQ-40). Semantic match (P6.2): different name, pypsa-de quantity minus the CHPs, which go to `Electricity|CHP|Waste` (#199).

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| – | none (empty carrier list) | `AC`, `low voltage` | – | – | D10 table, OQ-40 |
| Link | CHPs of this fuel (D10 table, `Electricity\|CHP\|Waste`) | `AC`, `low voltage` | any port | no (definition) | D10 rule 1 |
| Line, Link, StorageUnit, Load | D10 excluded row (transport, storage, `electricity` Load) | `AC`, `low voltage` | – | no | D10 |

Measured with the D10 classification (`resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc`, pypsa 1.1.2, 2026-11-25; yearly supply, snapshot weighting applied):

| | AT 2025 | AT 2040 | all locations 2025 | all locations 2040 |
|---|---|---|---|---|
| `Secondary Energy\|Electricity w/o CHP\|Waste` [TWh] | 0.000 | 0.000 | 0.00 | 0.00 |

Structurally zero (OQ-40). For reference: `waste CHP CC` supplies 0.051 TWh (2025) and 0.474 TWh (2040) of electricity in AT, reported in `Electricity|CHP|Waste`. No unclassified carrier on either network (D10 rule 4). These values are a plausibility check for the implementing PR, not acceptance criteria.

Plausibility against official data (owner, PR #214 review 2026-11-25): model AT 2025 vs. the Eurostat energy balance `nrg_bal_c`, AT, 2024, unit `GWH` (latest published year: 2025 is not published, Eurostat API checked 2026-11-25, dataset updated 2026-08-27). Balance: `GEP_MAPE` + `GEP_APE` (electricity-only plants, main activity and autoproducer); SIEC: `W6100_6220` (industrial and non-renewable municipal waste), `W6210` (renewable municipal waste).

| | Model AT 2025 | Eurostat AT 2024 | Deviation |
|---|---|---|---|
| `Secondary Energy\|Electricity w/o CHP\|Waste` [TWh] | 0.000 | 0.546 | -100 % |

Model limitation: Eurostat reports 0.546 TWh from waste plants classified as electricity-only; PyPSA-AT models every waste plant as CHP, so this variable is structurally zero (OQ-40). Waste electricity in total: Eurostat 1.103 TWh, model 0.052 TWh (`Electricity|CHP|Waste`). Eurostat reports gross production (incl. the plants' own use), the model net supply (D10); the difference is a few percent for thermal plants and negligible for wind and PV. A comparison of one model year with the previous calendar year is a plausibility check only, not an acceptance criterion.

## 7. Accounting rule and sign convention
- Formula: `value(l) = E[w/o CHP|Waste](l) = Σ_{c ∈ C_el} S[{AC, low voltage}, c](l)` with `C_el` = ∅ (empty) (D10).
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
| any network | `0.0` at every location of `n.buses.location`, unit `MWh_el`; never `None` or zero rows (C6.7, C6.13, OQ-40) |
| a waste-fired plant that is not a CHP appears in `n` | not counted; D10 rule 4 warns about its carrier (OQ-39) |
| time series and yearly results disagree | must not happen (C6-AC3) |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1 (Series, MultiIndex with `location` and `unit`, ≥ 1 row, numeric dtype, valid units, locations in `n.buses.location`). All-zero values are valid.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2 (DataFrame, not Series; exactly the snapshots of `n` as columns; otherwise as AC1).
- AC3: Mock network, locations `A`, `B`, buses `A AC`, `B AC`, `A non-sequestered HVC` (location `A`); Link `waste CHP` from `A non-sequestered HVC` to `A AC` (`bus1`, `efficiency = 0.2`) and an `urban central heat` bus (`bus2`), `p0 = [10, 10]` MW: yearly `A` = 0.0, `B` = 0.0; snapshots all `0.0`; unit `MWh_el`.
- AC3a: As AC3 with snapshot weighting 2: yearly values doubled, snapshot values unchanged (C6.10).
- AC4: The `True` and `False` results are consistent per C6-AC3 (`flow`); every value is `≥ 0` (D10 rule 5).
- AC5: C6-AC6: on any mock network the result is `0.0` at every location of `n.buses.location`, with both values of `aggregate_per_year`; never `None` or zero rows.
- AC6 (CHPs excluded, any port order): adding to the AC3 network a CHP Link of this fuel (D10 table, `Electricity|CHP|Waste`) with `AC` at `bus1` and `urban central heat` at `bus2`, and a second one with heat at `bus1` and `AC` at `bus2`, does not change the result (D10 rule 1).
- AC7 (excluded carriers): adding a `PHS` StorageUnit, a `battery discharger` Link, an `AC` Line and an `electricity` Load with negative `p_set` at `A` does not change the result (D10 excluded row, OQ-38).
- AC8 (unclassified carrier): adding a Generator with an unknown carrier (e.g. `geothermal`) at `A AC` does not change the result and logs one `WARNING` naming `geothermal` and its yearly supply in TWh (D10 rule 4, OQ-39).

## 12. Open questions
None.

## 13. Sources
- #194, milestone "Implement Infra-Enshure Coupling Variables"; infra-ensure/coupling-variables#8 (rename, PR #9)
- `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`)
- `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` l.1548-1558, l.1661-1663 (commit `a5baa7e9`)
- Eurostat `nrg_bal_c` (AT, 2024, `GWH`), local copy `eurostat-energy-balance_processing/resources/estat_nrg_bal_c.tsv`; `nrg_bal_peh` (`RA130`) via the Eurostat API (2026-11-25)
- PyPSA statistics accessor (`supply`): https://docs.pypsa.org/latest/api/networks/statistics/
- measurement on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` (2026-11-25)
- D1, D10 in [shared_definitions.md](shared_definitions.md); C4.5, C6.10, C6.13, C8, C9 in [../contracts.md](../contracts.md); OQ-37–OQ-40 in [../open_questions.md](../open_questions.md)
