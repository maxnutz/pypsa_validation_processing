# `Net Imports|Oil`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Net Imports\|Oil` |
| Function name | `Net_Imports__Oil` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #69 |
| Variable name | `Net Imports\|Oil` |
| Description | Net imports of oil (#69) |
| Unit | TJ, TWh |
| Contained in a definitions folder? | `definitions/variable/trade.yaml` (commit `dec0978`), tag `Oil` ("oil") |

```yaml
- Net Imports|{Final Energy Carrier}:
    description: Net imports of {Final Energy Carrier}
    unit: [ TJ, TWh ]
# {Final Energy Carrier} = Oil: "oil"
```
As for `Final Energy [by Carrier]|Oil`, "Oil" is fossil oil. `Net Imports|Biofuels` and `Net Imports|E-Fuels` are separate variables (#2, `tag_final_energy_carrier.yaml`).

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_th` | `EU oil` bus (measured in `AT_KN2040` 2040, `electricity_network_0p3` 2025 and `20261020_carbon_accounting_run` 2025–2050) |
| Normalised unit | `MWh` | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `pypsa.statistics` |
| pypsa-de function | – |
| pypsa-de line range | – |
| pypsa-de variable name | – |
| pypsa-de commit | `a5baa7e9` |

`export_ariadne_variables.py` was searched for `Oil`, `Trade|Primary Energy|Oil`, `Net Imports` and `get_export_import(…, ["oil"…])`. `get_trade` contains only the comment `# Trade|Primary Energy|Oil|Volume` without code (l.4958). No exact or semantic match exists, so P6 rule 3 applies. The fossil share is taken from D2 for consistency with `Final Energy [by Carrier]|Oil`.

## 5. Match type
- Match type: `none`.
- Reasoning: see section 4.

## 6. Components, carriers, bus carriers
In PyPSA-AT, oil is one copperplate bus `EU oil` (measured 2020, 2040). Fossil oil is supplied only by `oil refining` (from `oil primary`), located at `EU`. So every fossil oil withdrawal of a regional consumer is an import of that region.

| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Link | every carrier withdrawing from `oil` buses (e.g. `land transport oil`, `kerosene for aviation`, `shipping oil`, `naphtha for industry`, `agriculture machinery oil`, `rural oil boiler`, `urban decentral oil boiler`, `oil`, `urban central oil CHP`) | `oil` | withdrawal (bus0), location per D1 | yes, × `f_oil` | measured withdrawal 2040 |
| Link | `oil refining` | `oil` | supply (bus1) | yes, as domestic fossil production of its location | D2 |
| Store | `oil` | `oil` | – | **no** (storage) | D2 |
| Link | renewable oil producers (`C_oil` \ {`oil refining`}) | `oil` | – | **no** (not fossil; enter only via `f_oil`) | D2 |

## 7. Accounting rule and sign convention
- Formula: `NI_oil(l) = f_oil · Σ_c W[oil, c](l) − S[oil, oil refining](l)` (D1, D2)
- Sign convention: positive = net import. Values MAY be negative (e.g. the `EU` location, which holds the refining, OQ-17).
- Weighting: per C6.10; `f_oil` is a yearly scalar for every snapshot.
- Model note: domestic crude production is not modelled in PyPSA-AT (`oil primary` is a single Generator). So for a regional location, net imports equal its fossil oil consumption.

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
| location without oil consumers | `0.0` (C6.13) |
| no `oil` bus in `n` | `0.0` for every location |
| `f_oil = 0` (no fossil supply) | `0.0` for every regional location |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock: bus `EU oil` (location `EU`); `oil refining` at `EU` supplies 80, `Fischer-Tropsch` at `A` supplies 20 (`f_oil = 0.8`). `land transport oil` link withdraws 60 into `A`, `rural oil boiler` withdraws 40 into `B`; 1 snapshot. Result `A: 48`, `B: 32`, `EU: −80`.
- AC4: C6-AC3 (`flow`).
- AC5: Sum over all locations = 0 when every supply and withdrawal is attributed (no Store change).
- AC6: C6-AC6.

## 12. Open questions
- OQ-17 (`EU` location). OQ-23 resolved (`import oil` non-fossil, D2).

## 13. Sources
- #69, #2; definitions as in section 2
- `export_ariadne_variables.py::get_trade` l.4814-4993 (commit `a5baa7e9`), no oil trade
- Current implementation: `statistics_functions.py::Net_Imports__Oil` l.462-562 (commit `16bf37f`). Difference: SC-31
