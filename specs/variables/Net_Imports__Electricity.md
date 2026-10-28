# `Net Imports|Electricity`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Net Imports\|Electricity` |
| Function name | `Net_Imports__Electricity` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #70 |
| Variable name | `Net Imports\|Electricity` |
| Description | Net imports of electricity (#70) |
| Unit | TJ, TWh |
| Contained in a definitions folder? | `definitions/variable/trade.yaml` (commit `dec0978`) |

```yaml
- Net Imports|{Final Energy Carrier}:
    description: Net imports of {Final Energy Carrier}
    unit: [ TJ, TWh ]
# {Final Energy Carrier} = Electricity: "electricity"
```

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_el` | `AC` buses |
| Normalised unit | `MWh` | `UNITS_MAPPING` |
| Target unit | `TJ` (first of the list, C9) | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_trade`, `get_export_import` |
| pypsa-de line range | `export_ariadne_variables.py:L4697-L4811, L4814-L4825` |
| pypsa-de variable name | `Trade\|Secondary Energy\|Electricity\|Volume` (= exports − imports) |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- Sign flipped: net imports = imports − exports = −`Volume`.
- Region = location instead of country prefix `bus.str[:2]`. Per-location net imports are summed by C8 to the country value. Flows between locations of the same country cancel up to the losses of the branches between them (section 7).
- Snapshot weighting per C6.10 instead of `snapshot_weightings.generators` (identical in PyPSA-AT, owner statement C6.12).

## 5. Match type
- Match type: `semantic`.
- Reasoning: the pypsa-de trade volume is the net cross-border flow over AC lines and DC links, i.e. the negative of net imports.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Line | `AC` | `AC` | both ends | yes | l.4807-4808 |
| Link | `DC` | `AC` (both ends) | bus0, bus1 | yes | l.4810 |
| Link | `electricity distribution grid`, any non-transmission link | – | – | **no** | l.4697-4711 (carrier filter) |

Measured 2040: 97 Lines and 138 `DC` Links; `DC` Links connect `AC` buses (e.g. `FR0` → `GB0`). There is no bus carrier `DC`.

## 7. Accounting rule and sign convention
- Formula: for location `l`, `NI_el(l) = Σ_branches Σ_ports at buses in l (−p_port)`, i.e. the energy fed into `l` by Lines/`DC` Links minus the energy withdrawn from `l` by them. For a link with losses, the import is counted at the receiving port and the export at the sending port (as `get_export_import`, which uses `p0` for outgoing and `p1` for incoming).
- Branches with both ends in `l` contribute 0.
- Sign convention: positive = net import, negative = net export. Values MAY be negative.
- Aggregation (owner decision 2026-10-28): the per-location values are summed by C8 (`flow`); no separate aggregation class. The losses of a branch between two locations of the same country stay in the country sum as negative net imports, so the country value equals its cross-border net imports minus its internal branch losses. Measured: `20261020_carbon_accounting_run` 2040, 15 AT-internal Lines with 0.98 TWh losses; `electricity_network_0p3` 2025, 47 Lines with 0.96 TWh; no AT-internal `DC` Links. The AT value is therefore about 3.5 PJ too low. This bias is accepted.
- Weighting: per C6.10.

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_el` (or `MWh`).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| location without lines/links | `0.0` (C6.13) |
| network without lines and `DC` links | `0.0` for every location |
| lossless line between A and B | `NI(A) = −NI(B)` |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock with locations `A`, `B`, `C`: a Line `A→B` with `p0 = 10`, and a `DC` link `C→A` with `p0 = 5`, `efficiency = 0.9`, over 1 snapshot. Result `A: −10 + 4.5 = −5.5`, `B: 10`, `C: −5`.
- AC4: C6-AC3 (`flow`).
- AC5: Sum over all locations = −(link losses), i.e. 0 for lossless branches.
- AC6: C6-AC6.
- AC7: An `electricity distribution grid` link does not change the result.

## 12. Open questions
None specific. #2 reports an AT value (−3.4) far from the energy balance (7900 TJ). The cause is not yet analysed (SC-30).

## 13. Sources
- #70, #2; definitions as in section 2
- `export_ariadne_variables.py` l.4697-4825 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Net_Imports__Electricity` l.150-235 (commit `16bf37f`). Difference: SC-30
