# `Secondary Energy|Electricity|Solar`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Secondary Energy\|Electricity\|Solar` |
| Function name | `Secondary_Energy__Electricity__Solar` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml`, short form `Secondary Energy\|Electricity\|Solar: Secondary_Energy__Electricity__Solar` (C4.1) |
| Aggregation class | `flow` (C4.5, default) |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed (`w/o` → `wo`).

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #190 (milestone "Implement Infra-Enshure Coupling Variables") |
| Variable name | `Secondary Energy\|Electricity\|Solar` |
| Description | Total net generation of electricity from solar photovoltaics (PV) |
| Unit | `TWh` |
| Contained in a definitions folder? | `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`). Also in the common definitions `sister_packages/energy-scenarios-at-workflow/definitions/variable/electricity-generation.yaml`, template `Secondary Energy\|Electricity\|{Electricity Generation by Source}`, tag `Solar`; same meaning (no CHPs involved), so runs with either definitions folder evaluate this variable with this spec. |

```yaml
- Secondary Energy|Electricity|Solar:
    description: Total net generation of electricity from solar photovoltaics (PV)
    unit: TWh
```

The issue cites commit `97bcf66`; the entry above is from commit `30202ec` (names changed in PR #9).

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
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L1548-L1558` (supply), `:L1631-L1633` (variable) |
| pypsa-de variable name | `Secondary Energy\|Electricity\|Solar` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as far as needed for the function contract:
- Region = location (D10, D1.2: location of the `AC`/`low voltage` bus at the supplying port; Generators and StorageUnits: location of their bus) instead of `.filter(like=region)` on the component name; per-location values are aggregated to the country by C8.
- Carrier lists from the shared D10 table in `utils.py` instead of `filter(like=…)` on carrier names (D10, P4).
- Time series for `aggregate_per_year=False` (`groupby_time=False`, C6.10); pypsa-de reports yearly values only.
- Unclassified carriers give a `WARNING` (D10 rule 4, OQ-39); pypsa-de checks completeness with an `isclose` assertion (l.1744-1751).

Deviations decided by the owner (P6.1):
- Carrier list `solar`, `solar rooftop`, `solar-hsat` instead of `filter(like="solar")` (D10 table); same carriers on all 13 networks (D10).

P6.4 (switch to `pypsa.statistics`): not applicable (owner, 2026-11-25). pypsa-de already evaluates the variable with `n.statistics.supply(bus_carrier=["low voltage", "AC"], …)` (l.1548-1558); the port and a `pypsa.statistics` implementation are the same expression, so there is nothing to prove or shorten. The function is built on the D10 helper.

## 5. Match type
- Match type: `exact`
- Reasoning: Same variable name and the same carriers: `filter(like="solar")` on the supply to `AC`/`low voltage` (l.1631-1633) gives `solar`, `solar rooftop`, `solar-hsat`; `urban central solar thermal` and other solar thermal Generators supply heat buses and are not in the electricity supply. No CHPs.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| Generator | `solar`, `solar-hsat` | `AC` | supply | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Generator | `solar rooftop` | `low voltage` | supply | yes | D10 table; measured on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` |
| Line, Link, StorageUnit, Load | D10 excluded row (transport, storage, `electricity` Load) | `AC`, `low voltage` | – | no | D10 |

Measured with the D10 classification (`resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc`, pypsa 1.1.2, 2026-11-25; yearly supply, snapshot weighting applied):

| | AT 2025 | AT 2040 | all locations 2025 | all locations 2040 |
|---|---|---|---|---|
| `Secondary Energy\|Electricity\|Solar` [TWh] | 34.778 | 39.669 | 668.19 | 1599.41 |

AT 2025: `solar` 4.153, `solar rooftop` 30.160, `solar-hsat` 0.465 TWh; 2040: 9.045, 30.160, 0.465 TWh. No unclassified carrier on either network (D10 rule 4). These values are a plausibility check for the implementing PR, not acceptance criteria.

Plausibility against official data (owner, PR #214 review 2026-11-25): model AT 2025 vs. the Eurostat energy balance `nrg_bal_c`, AT, 2024, unit `GWH` (latest published year: 2025 is not published, Eurostat API checked 2026-11-25, dataset updated 2026-08-27). Balance: `GEP` (all plants); SIEC: `RA420` (solar photovoltaic).

| | Model AT 2025 | Eurostat AT 2024 | Deviation |
|---|---|---|---|
| `Secondary Energy\|Electricity\|Solar` [TWh] | 34.778 | 8.143 | +327 % |

Model result, flagged for PyPSA-AT: the optimisation builds 27.65 GW `solar rooftop` in AT 2025 (`p_nom_min` 3.87 GW) and 3.73 GW `solar` (2.58 GW), on 24 snapshots of 365 h. The evaluation is consistent: full-load hours about 1100 h, supply equals the weighted `n.generators_t.p` of these Generators (checked 2026-11-25). Eurostat reports gross production (incl. the plants' own use), the model net supply (D10); the difference is a few percent for thermal plants and negligible for wind and PV. A comparison of one model year with the previous calendar year is a plausibility check only, not an acceptance criterion.

## 7. Accounting rule and sign convention
- Formula: `value(l) = E[Solar](l) = Σ_{c ∈ C_el} S[{AC, low voltage}, c](l)` with `C_el` = `solar`, `solar-hsat`, `solar rooftop` (D10).
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
| time series and yearly results disagree | must not happen (C6-AC3) |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1 (Series, MultiIndex with `location` and `unit`, ≥ 1 row, numeric dtype, valid units, locations in `n.buses.location`). All-zero values are valid.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2 (DataFrame, not Series; exactly the snapshots of `n` as columns; otherwise as AC1).
- AC3: Mock network, locations `A`, `B`, buses `A AC` (carrier `AC`), `A low voltage` (carrier `low voltage`), `B AC`; Generator `solar` at `A AC`, `p = [10, 0]` MW; Generator `solar rooftop` at `A low voltage`, `p = [4, 0]` MW; Generator `solar-hsat` at `B AC`, `p = [6, 2]` MW; Generator `onwind` at `B AC`, `p = [5, 5]` MW; 2 snapshots, weighting 1. Yearly: `A` = 14, `B` = 8 (`MWh_el`). Snapshots: `A` = `[14, 0]`, `B` = `[6, 2]`.
- AC3a: As AC3 with snapshot weighting 2: yearly values doubled, snapshot values unchanged (C6.10).
- AC4: The `True` and `False` results are consistent per C6-AC3 (`flow`); every value is `≥ 0` (D10 rule 5).
- AC5: C6-AC6: in AC3, a location without any of the carriers (e.g. add location `C` with bus `C AC` only) is present with `0.0`; a mock network without any of the carriers returns `0.0` for every location of `n.buses.location`, not `None` and not zero rows.
- AC6 (excluded carriers): adding a `PHS` StorageUnit, a `battery discharger` Link, an `AC` Line and an `electricity` Load with negative `p_set` at `A` does not change the result (D10 excluded row, OQ-38).
- AC7 (unclassified carrier): adding a Generator with an unknown carrier (e.g. `geothermal`) at `A AC` does not change the result and logs one `WARNING` naming `geothermal` and its yearly supply in TWh (D10 rule 4, OQ-39).

## 12. Open questions
None.

## 13. Sources
- #190, milestone "Implement Infra-Enshure Coupling Variables"; infra-ensure/coupling-variables#8 (rename, PR #9)
- `sister_packages/coupling-variables/definitions/variable/secondary-energy.yaml` (commit `30202ec`); `sister_packages/energy-scenarios-at-workflow/definitions/variable/electricity-generation.yaml`, `tag_electricity-generation-source.yaml`
- `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py` l.1548-1558, l.1631-1633 (commit `a5baa7e9`)
- Eurostat `nrg_bal_c` (AT, 2024, `GWH`), local copy `eurostat-energy-balance_processing/resources/estat_nrg_bal_c.tsv`; `nrg_bal_peh` (`RA130`) via the Eurostat API (2026-11-25)
- PyPSA statistics accessor (`supply`): https://docs.pypsa.org/latest/api/networks/statistics/
- measurement on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2040}.nc` (2026-11-25)
- D1, D10 in [shared_definitions.md](shared_definitions.md); C4.5, C6.10, C6.13, C8, C9 in [../contracts.md](../contracts.md); OQ-37–OQ-40 in [../open_questions.md](../open_questions.md)
