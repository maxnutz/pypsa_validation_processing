# `<IAMC variable>`

<!--
Template for one IAMC variable = one statistics function.
Copy to specs/variables/<function_name>.md, replace every <…>, delete these comments.
Rules: specs/constitution/principles.md (P2 cite sources, P5 fail early and loud, P6 implementation source rule).
Every factual claim cites file path + symbol/line, definition file or doc URL.
Mark unknowns as "> **Open question:** …" and assumptions as "> **Assumption:** …".
-->

Status: draft
Implementing PR: <link, once implemented>

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `<Final Energy [by Carrier]\|Electricity>` |
| Function name | `<Final_Energy_by_Carrier__Electricity>` |
| Mapping file(s) | `<pypsa_validation_processing/configs/mapping.default.yaml>` |
| Aggregation class | `<flow \| stock \| intensive>` (C4.5); for `intensive`: weight used = `<e.g. withdrawn energy in MWh>` |

Function name derived per `README.md` "Naming Convention": `|` → `__`, space → `_`, other special characters removed.

## 2. Definition source
The name and definition of the variable to implement are given by its GitHub issue. The variable MAY additionally be contained in a definitions folder in IAMC-valid format (readable by `nomenclature.DataStructureDefinition`, as used with pyam), e.g. the default `sister_packages/energy-scenarios-at-workflow/definitions/`.

| Item | Value |
|---|---|
| GitHub issue | `<#nnn, link>` (required) |
| Variable name | `<as given in the issue>` |
| Description | `<as given in the issue>` |
| Unit | `<as given in the issue>` |
| Contained in a definitions folder? | `<no>` or `<path to folder + file, e.g. sister_packages/energy-scenarios-at-workflow/definitions/variable/energy-consumption.yaml>` |

If the variable is contained in a definitions folder, copy the entry verbatim (incl. tags such as `{Final Energy Carrier}` and their expansion):
```yaml
<copied definition entry, or "n/a">
```

> If issue and definitions differ (name, description or unit), record it under "Open questions"; do not resolve it silently.

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) returned by the function | `<MWh_el, MWh_LHV, …>` | <statistics call / pypsa-de line> |
| Normalised unit (`utils.UNITS_MAPPING`) | `<MWh>` | `utils.py::UNITS_MAPPING` |
| Target unit (first if several) | `<TJ>` | <issue; definitions file if contained> |
| Conversion | `<MWh → TJ, factor 0.0036>` | C9 |

All returned units MUST normalise to one single unit (C9).

## 4. Implementation source
Per [principles.md](../constitution/principles.md) P6.

| Item | Value |
|---|---|
| Source | `<export_ariadne_variables.py>` or `<pypsa.statistics>` |
| pypsa-de function | `<get_final_energy>` |
| pypsa-de line range | `<sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L<from>-L<to>>` |
| pypsa-de variable name | `<Final Energy\|Electricity>` |
| pypsa-de commit | `<git -C sister_packages/pypsa-de log -1 --format=%h>` |

Changes to the ported logic, only as far as needed for the function contract (one bullet each, with reason):
- <e.g. country aggregation removed; returns locations (C6.5)>

If the source is `pypsa.statistics`: state that `export_ariadne_variables.py` was searched and no exact or semantic match exists (search terms, functions checked).

## 5. Match type
- Match type: `<exact | semantic | none>`
- Reasoning: <for semantic: why the pypsa-de variable has the same meaning despite a different name or hierarchy; compare definitions and accounting>

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier(s) | Port / direction | Included? | Source |
|---|---|---|---|---|---|
| `<Load>` | `<electricity>` | `<low voltage>` | `<withdrawal>` | yes | <pypsa-de line / resources/carriers_bus_carriers_components.csv> |

Every carrier, bus carrier and component MUST exist in `resources/carriers_bus_carriers_components.csv` or be justified by a source.

## 7. Accounting rule and sign convention
- Formula: `<value = Σ … − Σ …>`
- Sign convention: <e.g. withdrawal from bus counted positive; result MUST be ≥ 0>
- Weighting: <snapshot weightings applied / not applied>
- Special cases ported from pypsa-de: <e.g. domestic share of aviation, CHP split, V2G>

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | switch Series / DataFrame (C6) | – |
| `config` | `<yes/no>` | <keys read, e.g. `config["sector"][…]`> | <see OQ-6> |
| `energy_totals` | `<yes/no>` | <columns read> | variable skipped with `WARNING` (C2.4) |

## 9. Return format
- `aggregate_per_year=True`: `pd.Series`, MultiIndex `[location, unit<, quantity><, …>]`, values = <`flow`: total over snapshots, weighted \| `stock`: end-of-year value \| `intensive`: weighted mean over snapshots, plus `weight` rows> (C6.10–12).
- `aggregate_per_year=False`: `pd.DataFrame`, MultiIndex `[location, unit<, …>]`, columns = snapshots of `n`; for `flow`: values and units as returned by `n.statistics(…, groupby_time=False)`, not multiplied by the snapshot weighting (C6.10).
- No country aggregation inside the function (C6, C8).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| none of the carriers present in a location | `0.0` for this location (every snapshot with `aggregate_per_year=False`), unit as in section 3; the location is not dropped (C6.13) |
| none of the carriers present in the network | `0.0` for every location of `n.buses.location` (C6.13) |
| <only some carriers present in a location> | <e.g. absent carriers contribute 0> |
| <time series and yearly results disagree> | <must not happen; C6-AC3> |

## 11. Acceptance criteria
Concrete enough to become tests in `tests/test_statistics_functions.py`.
- AC1: With `aggregate_per_year=True`, the result fulfils all checks of C6-AC1 (Series, MultiIndex with `location` and `unit`, ≥ 1 row, numeric dtype, valid units, locations in `n.buses.location`). All-zero or all-NaN values are valid.
- AC2: With `aggregate_per_year=False`, the result fulfils all checks of C6-AC2 (DataFrame, not Series; snapshots of `n` as columns; otherwise as AC1).
- AC3: <numeric check on a mock network: input values → expected output per location and unit>
- AC4: The `True` and `False` results are consistent per the aggregation class (C6-AC3).
- AC4: <sign convention check>
- AC5: On a mock network with a location without any of the carriers, that location is present with `0.0`; on a mock network without any of the carriers, every location is present with `0.0` (C6-AC6).
- AC6: <special case check>

## 12. Open questions
> **Open question:** <…>

## 13. Sources
- <GitHub issue>
- <definitions file, if contained>
- <pypsa-de file + lines + commit>
- <PyPSA docs URL>
- <resources/carriers_bus_carriers_components.csv>
