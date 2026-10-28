# `Final Energy [by Carrier]|Electricity`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Carrier]\|Electricity` |
| Function name | `Final_Energy_by_Carrier__Electricity` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #43 (implementation); definition text in #5 and #2 |
| Variable name | `Final Energy [by Carrier]\|Electricity` |
| Description | Energy consumption of electricity excluding transmission/distribution losses |
| Unit | TJ |
| Contained in a definitions folder? | `sister_packages/energy-scenarios-at-workflow/definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Electricity` in `tag_final_energy_carrier.yaml` |

```yaml
- Final Energy [by Carrier]|{Final Energy Carrier}:
    description: Energy consumption of {Final Energy Carrier}
      excluding transmission/distribution losses
    unit: TJ
# {Final Energy Carrier} = Electricity: "electricity"
```
Issue #43 has no description of its own; #5 and #2 give the same text as the definitions file.

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_el` | bus unit of `low voltage` and `AC` buses |
| Normalised unit | `MWh` | `utils.UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, factor 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy` |
| pypsa-de line range | `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py:L2113-L2119, L2278-L2302, L2437-L2439, L2553-L2555, L2591-L2616` |
| pypsa-de variable name | `Final Energy\|Electricity` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- No `.filter(like=region)` and no country aggregation; the result is per location (D1, C6.6).
- `MWh2TWh` scaling removed; units per section 3 (C6.10, C9).
- Missing locations filled with `0.0` (C6.13).
- `V2G` feed-in to `low voltage` is subtracted per snapshot, as in `Final Energy [by Sector]|Transportation` (owner decision 2026-10-28); pypsa-de does not subtract it. Reason: electricity stored in EVs and fed back to the grid is counted again where it is consumed (e.g. Load `electricity`, `industry electricity`). Without the subtraction it would be counted twice.

## 5. Match type
- Match type: `exact`.
- Reasoning: pypsa-de `Final Energy|Electricity` is the sum of the sector electricity demands, excluding the distribution grid (losses) and storage chargers. That is the IAMC definition "energy consumption of electricity excluding transmission/distribution losses".

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `agriculture electricity`, `agriculture machinery electric` | `low voltage` | withdrawal | yes | l.2553-2555 |
| Load / Link | every carrier withdrawing from `low voltage` whose name does **not** contain `urban central`, `industry`, `agriculture`, `charger`, `distribution` (e.g. Load `electricity`, or its split `electricity for residential`, `electricity for services`, `electricity for rail`, `electricity for road` in `20261020_carbon_accounting_run`; Links `rural air heat pump`, `rural ground heat pump`, `rural resistive heater`, `urban decentral air heat pump`, `urban decentral resistive heater`) | `low voltage` | withdrawal at the `low voltage` port (for heat pumps this is `bus1`: in PyPSA-AT they have `bus0` = heat bus, `bus1` = `low voltage`, measured AT11 2025) | yes (residential and commercial) | l.2278-2302 |
| Link | `BEV charger` | `low voltage` | withdrawal (bus0) | yes (transportation) | l.2437-2439 |
| Load | `electricity for road` (only in networks with the split base load, e.g. `20261020_carbon_accounting_run`; none in AT) | `low voltage` | withdrawal | yes: the Load is electricity demand of the network, although built from historic data (owner decision 2026-10-23, OQ-24). It is counted in no `Final Energy [by Sector]` variable, so the sector variables do not sum to this variable by this amount (37.525 TWh in total, every year) | OQ-24 |
| Load | `industry electricity` | `low voltage` | withdrawal | yes | l.2113-2119 |
| Link | `DAC` | `AC` | withdrawal | yes | l.2591-2603 |
| Link | `electricity distribution grid`, `home battery charger`, `urban central air heat pump`, `urban central resistive heater` | `low voltage` | – | **no** (losses, storage, district-heat supply) | substring pattern l.2293 |
| Link | `V2G` | `low voltage` | supply (bus1), subtracted | yes, **negative** (owner decision 2026-10-28, as in Transportation) | l.2279 (pypsa-de counts `withdrawal` only) |
| Link | `home battery discharger` | `low voltage` | supply | **no** (storage; the home battery charger is not counted either) | l.2279 (`withdrawal` only) |

All carriers exist in `resources/carriers_bus_carriers_components.csv` (local and not versioned, see `resources/README.md`). The list can be reproduced on `resources/AT_KN2040/networks/base_s_adm__none_2040.nc` with `n.statistics.withdrawal(bus_carrier="low voltage", groupby="carrier")`. Measured withdrawals from `low voltage` in 2040 (TWh): Load `electricity` 1578.22, `industry electricity` 1686.76, `BEV charger` 965.98, `urban decentral air heat pump` 347.01, `urban decentral resistive heater` 224.12, `rural ground heat pump` 194.93, `urban central air heat pump` 88.99 (excluded), `home battery charger` 7.05 (excluded).

## 7. Accounting rule and sign convention
- Formula, per location `l` (D1):
  `FE_el(l) = L[agriculture electricity](l) + L[agriculture machinery electric](l) + Σ W[low voltage, c](l) for c in the residential/commercial set + W[low voltage, BEV charger](l) − S[low voltage, V2G](l) + L[industry electricity](l) + W[AC, DAC](l)`
- Sign convention: withdrawals counted positive; the `V2G` feed-in is subtracted per snapshot, without clipping. Snapshot values MAY be negative (exception to G2); yearly values MUST be ≥ 0 (G2).
- Weighting: per C6.10.
- Special cases: `V2G` (above). The measured networks have no `V2G` Links (`20261020_carbon_accounting_run` 2040, `electricity_network_0p3` 2025).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | Series / DataFrame (C6) | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |

## 9. Return format
Per template / C6: `pd.Series` (`True`) or `pd.DataFrame` with snapshots as columns (`False`), MultiIndex `[location, unit]`, unit `MWh_el` (or normalised `MWh`). No country aggregation.

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| none of the carriers present in a location | `0.0` for this location (C6.13) |
| none of the carriers present in the network | `0.0` for every location of `n.buses.location` (C6.13) |
| `DAC` absent | contributes 0, no error |
| `V2G` absent | contributes 0, no error |
| yearly withdrawal of a location is 0 | row kept with `0.0` (C6.13) |

## 11. Acceptance criteria
- AC1: With `aggregate_per_year=True`, the result fulfils C6-AC1.
- AC2: With `aggregate_per_year=False`, the result fulfils C6-AC2.
- AC3: Mock network, one location `A`, constant loads per snapshot: `electricity` 10 MW, `industry electricity` 5, `agriculture electricity` 1, `agriculture machinery electric` 1; `BEV charger` withdrawal 2; `rural air heat pump` withdrawal 3; `DAC` AC withdrawal 1; `electricity distribution grid` withdrawal 4; `home battery charger` withdrawal 2; `urban central resistive heater` withdrawal 2. With 2 snapshots of weighting 1, the yearly result is `(A, MWh_el or MWh): 46`. The distribution grid, home battery and central heater flows are not counted. Adding a `V2G` feed-in of 1 per snapshot to `low voltage` at `A` gives `44`.
- AC4: The `True` and `False` results are consistent per C6-AC3 (`flow`).
- AC5: All values ≥ 0 for the mock network of AC3 (without `V2G`).
- AC7: Time series, 2 snapshots, weighting 1, only `BEV charger` withdrawal 4 / 0 and `V2G` feed-in 0 / 3 at `A`: snapshot values `4 / −3` (not clipped), yearly value `1`. The `V2G` term equals the one in `Final_Energy_by_Sector__Transportation` (AC8 there).
- AC6: C6-AC6 (zero-fill of a location without carriers, and of a network without carriers).

## 12. Open questions
None specific. OQ-17, OQ-24 resolved.

## 13. Sources
- #43, #5, #2
- `sister_packages/energy-scenarios-at-workflow/definitions/variable/energy-consumption.yaml`, `tag_final_energy_carrier.yaml` (commit `dec0978`)
- `export_ariadne_variables.py` l.2113-2119, 2278-2302, 2437-2439, 2553-2555, 2591-2616 (commit `a5baa7e9`)
- `resources/carriers_bus_carriers_components.csv`
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__Electricity` l.50-147 (commit `16bf37f`). Difference: SC-38
