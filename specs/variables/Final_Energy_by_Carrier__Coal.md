# `Final Energy [by Carrier]|Coal`

Status: draft
Implementing PR: –

## 1. Variable and function name
| Item | Value |
|---|---|
| IAMC variable | `Final Energy [by Carrier]\|Coal` |
| Function name | `Final_Energy_by_Carrier__Coal` |
| Mapping file(s) | `pypsa_validation_processing/configs/mapping.default.yaml` |
| Aggregation class | `flow` (C4.5) |

## 2. Definition source
| Item | Value |
|---|---|
| GitHub issue | #44 (implementation); definition text in #2 |
| Variable name | `Final Energy [by Carrier]\|Coal` |
| Description | Energy consumption of coal excluding transmission/distribution losses |
| Unit | TJ |
| Contained in a definitions folder? | `sister_packages/energy-scenarios-at-workflow/definitions/variable/energy-consumption.yaml` (commit `dec0978`), tag `Coal` ("coal") in `tag_final_energy_carrier.yaml` |

```yaml
- Final Energy [by Carrier]|{Final Energy Carrier}:
    description: Energy consumption of {Final Energy Carrier}
      excluding transmission/distribution losses
    unit: TJ
# {Final Energy Carrier} = Coal: "coal"
```

## 3. Unit
| Item | Value | Source |
|---|---|---|
| PyPSA unit(s) | `MWh_LHV` | bus unit of `… coal for industry` buses (measured) |
| Normalised unit | `MWh` | `utils.UNITS_MAPPING` |
| Target unit | `TJ` | definitions file |
| Conversion | MWh → TJ, factor 0.0036 | C9 |

## 4. Implementation source
| Item | Value |
|---|---|
| Source | `export_ariadne_variables.py` |
| pypsa-de function | `get_final_energy` |
| pypsa-de line range | `export_ariadne_variables.py:L2208-L2228, L2629-L2631` |
| pypsa-de variable name | `Final Energy\|Solids\|Coal` |
| pypsa-de commit | `a5baa7e9` |

Changes to the ported logic, only as needed for the function contract:
- Per location instead of `.filter(like=region)`; no `MWh2TWh` scaling; zero-fill (C6.13).
- Deviation from pypsa-de (owner decision 2026-10-29, OQ-28): the Eurostat non-energy use `NE_coal` (D5) is subtracted; pypsa-de assumes none (l.2234).
- The coke correction depends on the location (D6, owner decision 2026-11-06):
  - At locations with Eurostat-valid `industrial_demand_overrides` (AT), the Load already excludes blast-furnace use, so the coke correction is not applied (deviation from pypsa-de).
  - At all other locations the correction is skipped (`κ = 0`, `WARNING`). This is a known limitation, since the result there contains the blast-furnace input; work item OQ-37.

## 5. Match type
- Match type: `semantic`.
- Reasoning: pypsa-de has no `Final Energy|Coal`. Its `Final Energy|Solids|Coal` is the only coal final energy, and it equals `Final Energy|Industry excl Non-Energy Use|Solids|Coal`. Residential/commercial coal is not modelled in pypsa-eur ("Not implemented", l.2394-2396). The IAMC carrier "coal" matches the pypsa-de sub-category `Solids|Coal`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `coal for industry` | `coal for industry` | withdrawal − `NE_coal` (D5) | yes, with coke correction (D6) | l.2220-2225 |
| Link | `coal`, `lignite` (power plants), `urban central coal CHP` | `coal` / `AC` | – | **no** (transformation, not final energy) | l.2629-2631 |

## 7. Accounting rule and sign convention
- Formula: `FE_coal(l) = (L[coal for industry](l) − NE_coal(l)) · (1 − κ(l)) + (L[coal for industry](l) − NE_coal(l)) · κ(l) / 1.366` (D5, D6), with `κ(l) = 0` at every location: by definition at locations with `industrial_demand_overrides`, as fallback (known limitation, OQ-37) at all others. So today `FE_coal(l) = L[coal for industry](l) − NE_coal(l)`.
- Sign convention: withdrawal positive; result MUST be ≥ 0.
- Weighting: per C6.10.
- Special cases: coke correction per location (D6); `0 ≤ NE_coal ≤ L` (D5), so the result stays ≥ 0 (G2).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | Series / DataFrame (C6) | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |
| `industry_non_energy_shares` | yes | `NE_coal` (D5, Eurostat fallback, C2.5); Eurostat has no coke share; `κ = 0` (D6) | variable skipped with `WARNING` (C2.5, A-7) |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_LHV` (or `MWh`).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| carrier `coal for industry` not present in `n` | `0.0` for every location (C6.13). The function MUST NOT return `None` (C6.9, SC-25) |
| location with zero yearly coal withdrawal (e.g. `AT13` in 2040) | row kept with `0.0` for both values of `aggregate_per_year` (C6.13, SC-26) |
| no `industrial_demand_overrides` in `n.meta["resources"]` (e.g. `electricity_network_0p3`) | every location counts as "without overrides" (D6): `κ = 0`, `WARNING` naming every country with a non-zero Load |
| location with overrides but zero coal and coke rows | counts as covered (D6); no `WARNING` for it |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock network with `coal for industry` Load of 10 MW at `A` over 2 snapshots (weighting 1), `κ = 0`: the result is `(A, …): 20`. With `κ = 0.5` (injected, as from the physical method of D6): `20·0.5 + 20·0.5/1.366 ≈ 17.321`.
- AC3a: As AC3 with `S[AA, Coal] = 0.25` for location `A` (country `AA`), `κ = 0`: `NE_coal = 5`, result `20 − 5 = 15`. With `κ = 0.5` (injected): `15·0.5 + 15·0.5/1.366 ≈ 12.990`. Without `industry_non_energy_shares` the variable is skipped (C2-AC8).
- AC3b: Mock with `coal for industry` Loads of 10 MW at `A` (country `AA`) and at `B` (country `BB`), 2 snapshots, `NE_coal = 0`. `n.meta["resources"]["industrial_demand_overrides"]` holds the row `region = A`, `sector = industry`, `carrier = coal`. Result: `(A, …): 20`, `(B, …): 20`. Exactly one `WARNING` naming the skipped coke correction is logged (`caplog`); it names `BB` and not `AA`.
- AC3c: As AC3b with an override row for `B` as well: same values, no coke-correction `WARNING`. Without the `industrial_demand_overrides` entry: same values, one `WARNING` naming `AA` and `BB`.
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6. A network without the `coal for industry` carrier returns a Series/DataFrame with `0.0` for every location, not `None`.

## 12. Open questions
- OQ-18 resolved (D6, C2.5). OQ-28 resolved (D5: Eurostat non-energy use of coal subtracted).
- OQ-37 open: coke/blast-furnace correction for locations without `industrial_demand_overrides` (known limitation, D6).

## 13. Sources
- #44, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2208-2228, 2394-2396, 2629-2631 (commit `a5baa7e9`)
- Eurostat check 2026-11-06 (AT, 2025 networks vs. Eurostat 2024, `IAMC_eurostat_eb_2026.xlsx`; PR #151 description): with overrides 9.5 PJ vs. 9.4 PJ, without overrides (`electricity_network_0p3`) 59.1 PJ
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__Coal` l.238-281 (commit `16bf37f`): returns `None` if the carrier is missing, no coke correction
