# `Final Energy [by Carrier]|Coal`

Status: reviewed
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
- The coke fraction `κ` cannot be read from `industrial_energy_demand` (not an available input). Per D6 (OQ-18 resolved): physical method once the networks carry industry production data, otherwise `κ = 0` with a `WARNING` (C2.5).

## 5. Match type
- Match type: `semantic`.
- Reasoning: pypsa-de has no `Final Energy|Coal`. Its `Final Energy|Solids|Coal` is the only coal final energy, and it equals `Final Energy|Industry excl Non-Energy Use|Solids|Coal`. Residential/commercial coal is not modelled in pypsa-eur ("Not implemented", l.2394-2396). The IAMC carrier "coal" matches the pypsa-de sub-category `Solids|Coal`.

## 6. Components, carriers, bus carriers
| Component | Carrier(s) | Bus carrier | Port | Included? | Source |
|---|---|---|---|---|---|
| Load | `coal for industry` | `coal for industry` | withdrawal − `NE_coal` (D5) | yes, with coke correction (D6) | l.2220-2225 |
| Link | `coal`, `lignite` (power plants), `urban central coal CHP` | `coal` / `AC` | – | **no** (transformation, not final energy) | l.2629-2631 |

## 7. Accounting rule and sign convention
- Formula: `FE_coal(l) = (L[coal for industry](l) − NE_coal(l)) · (1 − κ(l)) + (L[coal for industry](l) − NE_coal(l)) · κ(l) / 1.366` (D5, D6)
- Sign convention: withdrawal positive; result MUST be ≥ 0.
- Weighting: per C6.10.
- Special cases: coke correction (D6); `0 ≤ NE_coal ≤ L` (D5), so the result stays ≥ 0 (G2).

## 8. Optional kwargs
| Kwarg | Used? | Purpose | Behaviour if unavailable |
|---|---|---|---|
| `aggregate_per_year` | always | Series / DataFrame (C6) | – |
| `config` | no | – | – |
| `energy_totals` | no | – | – |
| `industry_non_energy_shares` | yes | `NE_coal` (D5, Eurostat fallback, C2.5); Eurostat has no coke share, fallback `κ = 0` (D6) | variable skipped with `WARNING` (C2.5, A-7) |

## 9. Return format
Per C6, MultiIndex `[location, unit]`, unit `MWh_LHV` (or `MWh`).

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| carrier `coal for industry` not present in `n` | `0.0` for every location (C6.13). The function MUST NOT return `None` (C6.9, SC-25) |
| location with zero yearly coal withdrawal (e.g. `AT13` in 2040) | row kept with `0.0` for both values of `aggregate_per_year` (C6.13, SC-26) |

## 11. Acceptance criteria
- AC1 / AC2: C6-AC1 / C6-AC2.
- AC3: Mock network with `coal for industry` Load of 10 MW at `A` over 2 snapshots (weighting 1), `κ = 0`: the result is `(A, …): 20`. With `κ = 0.5` (injected, as from the physical method of D6): `20·0.5 + 20·0.5/1.366 ≈ 17.321`.
- AC3a: As AC3 with `S[AA, Coal] = 0.25` for location `A` (country `AA`), `κ = 0`: `NE_coal = 5`, result `20 − 5 = 15`. With `κ = 0.5` (injected): `15·0.5 + 15·0.5/1.366 ≈ 12.990`. Without `industry_non_energy_shares` the variable is skipped (C2-AC8).
- AC3b: With the fallback (network without industry production data), `κ = 0` and one `WARNING` naming the skipped coke correction is logged (`caplog`).
- AC4: C6-AC3 (`flow`).
- AC5: Values ≥ 0.
- AC6: C6-AC6. A network without the `coal for industry` carrier returns a Series/DataFrame with `0.0` for every location, not `None`.

## 12. Open questions
- OQ-18 resolved (D6, C2.5). OQ-28 resolved (D5: Eurostat non-energy use of coal subtracted).

## 13. Sources
- #44, #2; definitions as in section 2
- `export_ariadne_variables.py` l.2208-2228, 2394-2396, 2629-2631 (commit `a5baa7e9`)
- Current implementation: `statistics_functions.py::Final_Energy_by_Carrier__Coal` l.238-281 (commit `16bf37f`): returns `None` if the carrier is missing, no coke correction
