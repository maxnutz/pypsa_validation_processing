# `Final Energy [by Sector]|Transportation`

Status: reviewed
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Sector]\|Transportation` |
| Function name | `Final_Energy_by_Sector__Transportation` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #15; rework #19 ("using pypsa-de logic", incl. comments) |
| Variable name | `Final Energy [by Sector]\|Transportation` |
| Description | Energy consumption by the transportation sector excluding transmission/distribution losses (#5) |
| Unit | TJ |
| Contained in a definitions folder? | `definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Transportation` ("transportation sector") |

```yaml
- Final Energy [by Sector]|{Sector}:
    description: Energy consumption by the {Sector}
      excluding transmission/distribution losses
    unit: TJ
# {Sector} = Transportation: "transportation sector"
```

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_el` (BEV charger), `MWh_LHV` (H2, liquids; `land transport` relabelled, D7) | bus units |
| Normalised unit | `MWh` (the function MUST normalise, because carriers with different units are summed; C6.5) | `UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy` |
| pypsa-de line range | `export_ariadne_variables.py:L2437-L2481, L2547-L2551` |
| pypsa-de variable name | `Final Energy\|Transportation` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- Domestic shares per country (D4).
- `electricity for rail` is counted, `electricity for road` is not (OQ-24 resolved; both Loads exist only in networks with the split base load, e.g. `20261020_carbon_accounting_run`; pypsa-de has neither).
- `V2G` feed-in to `low voltage` is subtracted per snapshot (owner decision 2026-10-28); pypsa-de does not subtract it. Reason: electricity stored in EVs and fed back to the grid is used by other sectors (e.g. Residential and Commercial, Industry) and counted there. Without the subtraction it would also count in Transportation. The measured networks have no `V2G` Links (`20261020_carbon_accounting_run` 2040, `electricity_network_0p3` 2025).
- Per location (D1); no `MWh2TWh`; zero-fill (C6.13).

## 5. Match type
- Match type: `exact`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Link | `BEV charger` | `low voltage` | withdrawal (bus0) | yes, **not** divided by the charger efficiency | l.2437-2439 |
| Load | `land transport fuel cell` | `H2` | withdrawal | yes | l.2448-2450 |
| Load | `land transport oil` | `land transport oil` | withdrawal, unit D7 | yes, **not** divided by an engine efficiency (D7, OQ-19 resolved) | l.2476-2477 |
| Load | `kerosene for aviation` | `kerosene for aviation` | × `d_aviation` (D4) | yes | l.2463-2467 |
| Load | `shipping oil` | `shipping oil` | × `d_navigation` (D4) | yes | l.2468-2470 |
| Load | `shipping methanol` | `shipping methanol` | × `d_navigation` (D4) | yes | l.2472-2474 |
| Load | `land transport EV` | `EV battery` | – | **no** (the BEV charger withdrawal already counts it, incl. charging losses) | l.2437 |
| Link | `V2G` | `low voltage` | supply (bus1), subtracted | yes, **negative** (owner decision 2026-10-28) | l.2437-2439 (pypsa-de does not subtract it) |
| Load | `electricity for rail` | `low voltage` | withdrawal | yes | OQ-24 |
| Load | `electricity for road` | `low voltage` | – | **no**: historic road electricity, already contained in the land transport demand served by the `BEV charger` chain (double count) | OQ-24 |

## 7. Accounting rule and sign convention
- Formula: `FE_tr(l) = W[low voltage, BEV charger](l) − S[low voltage, V2G](l) + L[electricity for rail](l) + L[land transport fuel cell](l) + L[land transport oil](l) + d_aviation(c)·L[kerosene for aviation](l) + d_navigation(c)·( L[shipping oil](l) + L[shipping methanol](l) )`
- Sign convention: withdrawals positive; the `V2G` feed-in is subtracted per snapshot, without clipping. Snapshot values MAY be negative (exception to G2); yearly values MUST be ≥ 0 (G2).
- Weighting: per C6.10; `d_k` are scalars.
- Special cases: D4, D7. The `BEV charger` withdrawal at bus0 is the electricity taken from the grid, i.e. it already includes charging losses. Dividing it by the efficiency (current code, l.851-871) counts the losses twice (SC-32).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | – | – |
| `config` | no | – | – |
| `energy_totals` | yes | D4 | variable skipped with `WARNING` (C2.4, SC-7) |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh` (normalised). No `land transport` unit (C9.1, SC-9).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| no transport loads in a location / in `n` | `0.0` (C6.13) |
| `shipping methanol` absent (e.g. 2020) | contributes 0 |
| several `BEV charger` efficiencies | irrelevant (no efficiency is used) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock at `A` (country `AA`, `d_aviation = 0.5`, `d_navigation = 0.2`): `BEV charger` withdrawal 10 (efficiency 0.9), `land transport fuel cell` 5, `land transport oil` 40 (bus unit `land transport`), kerosene 20, shipping oil 10, shipping methanol 5; 1 snapshot. Result `(A, MWh): 10 + 5 + 40 + 10 + 3 = 68`. Adding `electricity for rail` 2 and `electricity for road` 4 gives `70` (road not counted). Adding a `V2G` feed-in of 3 to `low voltage` at `A` gives `67`.
- AC4: C6-AC3 (`flow`).
- AC5: Yearly values ≥ 0; unit is `MWh`; no `land transport` unit.
- AC8: Time series, 2 snapshots, weighting 1, only `BEV charger` withdrawal 4 / 0 and `V2G` feed-in 0 / 3 at `A`: snapshot values `4 / −3` (not clipped), yearly value `1`.
- AC6: C6-AC6.
- AC7: Without `energy_totals`, the variable is skipped with a `WARNING` (C2-AC6).

## 12. Open questions
- None specific. OQ-1, OQ-19 (D7), OQ-24, OQ-27 resolved.

## 13. Sources
- #15, #19 (incl. comments), #5; definitions as in section 2
- `export_ariadne_variables.py` l.2437-2481, 2547-2551 (commit `a5baa7e9`)
- `prepare_sector_network.py::add_ice_cars` l.2730-2765
- Current implementation: `statistics_functions.py::Final_Energy_by_Sector__Transportation` l.790-922 (commit `16bf37f`). Differences: SC-7, SC-9, SC-32
