# Shared definitions for variable specs

Status: draft

Rules and quantities used by more than one variable spec. Variable specs reference them as D1–D7 instead of repeating them, so that copies cannot diverge (same reasoning as for [../constitution/principles.md](../constitution/principles.md), see [../README.md](../README.md)). Code that implements a shared quantity MUST live in `pypsa_validation_processing/utils.py` (P4).

Measurements cited below were made on 2026-10-22 with pypsa 1.1.2 on `resources/AT_KN2040/networks/base_s_adm__none_2020.nc` and `…_2040.nc` (54 locations, 1460 snapshots, snapshot weighting 6 h).

Notation: `L[c](l)` = withdrawal of the Loads with carrier `c` at location `l`; `W[bc, c](l)` = withdrawal of components with carrier `c` from buses with bus carrier `bc`; `S[bc, c]` = supply to buses with bus carrier `bc`. All flows are `flow` quantities in the sense of C6.10: weighted sum over snapshots for `aggregate_per_year=True`, unweighted per-snapshot values for `aggregate_per_year=False`.

## D1 Location attribution
1. A Load flow is attributed to `n.buses.location` of the Load's bus.
2. A Link flow is attributed to `n.buses.location` of the bus at the evaluated port.
3. Exception for copperplate buses: if that bus is a copperplate bus (its location is `EU`), the flow MUST be attributed to `n.buses.location` of the Link's `bus1` (the bus that receives the converted energy, e.g. `AT11 rural heat` for a `rural oil boiler` fed from `EU oil`).
4. If `bus1` is a copperplate bus as well, the flow stays at `EU` (handling of `EU` per OQ-17).

Reason: in PyPSA-AT, oil and coal are single copperplate buses (`EU oil`, `EU coal`; measured: 1 bus each), so withdrawals from them carry no regional information. Gas has regional buses (53 `… gas` buses), so the exception does not apply. pypsa-de achieves the same with `.filter(like=region)` on the component name (`export_ariadne_variables.py::get_final_energy`, e.g. l.2372-2381). Existing helper: `utils.create_location_index_from_copperplate`.

## D2 Fossil share of oil `f_oil`
One yearly value for the whole network (owner decision, 2026-10-22: system-wide, pypsa-de approach):

```
f_oil = S[oil, "oil refining"] / Σ_c S[oil, c]     for c ∈ C_oil
C_oil = {"oil refining", "Fischer-Tropsch", "biomass to liquid", "biomass to liquid CC",
         "electrobiofuels", "unsustainable bioliquids"}
```

- Supply is counted at the Link port that feeds the oil bus (`bus1`), weighted over the year (`groupby_time=True`), summed over all locations.
- Stores (`oil` Store) are excluded: they shift energy in time and do not produce it.
- `f_oil` is the same scalar for every location and every snapshot. With `aggregate_per_year=False` the yearly `f_oil` MUST be applied to every snapshot column, so that the `flow` consistency of C6-AC3 holds (avoids SC-23).
- If `Σ_c S[oil, c] = 0`, then `f_oil = 0` (no oil supplied, so no fossil oil).
- A component other than a Store that supplies energy to an `oil` bus with a carrier outside `C_oil` MUST raise `ValueError` naming the carrier (P5; the spec does not cover such a network).
- By construction `0 ≤ f_oil ≤ 1`. No clipping is needed, so no renewable production is "lost" (resolves the problem of #53).

Sources: `export_ariadne_variables.py::_get_fuel_fractions` l.109-242 (pypsa-de commit `a5baa7e9`). Adaptation: pypsa-de distinguishes `DE oil`/`EU oil` and `renewable oil` buses. PyPSA-AT networks have neither `renewable oil` nor `renewable gas` buses (measured 2020 and 2040), but have a single `EU oil` bus. Supplying carriers measured: 2020 `oil refining` 5873.20 TWh, `unsustainable bioliquids` 192.16, `biomass to liquid` 15.90, `biomass to liquid CC` 0.01, `electrobiofuels` 0.01, `Fischer-Tropsch` 0.00, `oil` Store 0.04; 2040 `oil refining` 1662.45, `electrobiofuels` 599.68, `Fischer-Tropsch` 182.11. `unsustainable bioliquids` is non-fossil as in pypsa-de (`fuel_fractions["Biomass"] = renewable_fuel_balance.filter(like="bio")`, l.226).

## D3 Fossil share of gas `f_gas`
One yearly value for the whole network, as D2:

```
f_gas = Σ_g S[gas, g] / (Σ_g S[gas, g] + Σ_r S[gas, r])
g ∈ G_fossil    = {"lng gas", "pipeline gas", "production gas"}   (Generators)
r ∈ G_renewable = {"Sabatier", "biogas to gas", "biogas to gas CC", "BioSNG", "BioSNG CC"}   (Links, port bus1)
```

- Excluded: gas transport (`gas pipeline`, `gas pipeline new`, Links between gas buses) and Stores (`gas`).
- Same rules as D2 for time series, zero denominator (`f_gas = 0`), and unknown supplying carriers (`ValueError`).

Sources: `_get_fuel_fractions` l.109-242 (`fuel_fractions["Natural Gas"]` = gas compressing share; `"Efuel"` = Sabatier; `"Biomass"` = `bio*`). Supplying carriers measured: 2020 Generators `pipeline gas` 2006.07 TWh, `production gas` 1714.52, `lng gas` 158.43; Links `biogas to gas` 196.11, `Sabatier` 19.44, `biogas to gas CC` 1.72, `BioSNG` 0.01, `BioSNG CC` 0.00; transport `gas pipeline` 1024.75, `gas pipeline new` 6390.43; Store `gas` 667.35.

## D4 Domestic share of aviation and navigation `d_k(c)`
For `k ∈ {aviation, navigation}` and country `c` = the first two characters of the location (e.g. `AT11 → AT`):

```
d_k(c) = total domestic k / (total domestic k + total international k)
```

- The values are read from `energy_totals.csv` (C2.4), columns `total domestic aviation`, `total international aviation`, `total domestic navigation`, `total international navigation`, row `country == c`.
- The share MUST be determined per country, not one value for all locations (current `utils.get_energy_totals_domestic_share` uses `AT` for all, OQ-1).
- Which `year` row is used is open (OQ-1). The file holds the years 1990–2024 for 34 countries (measured).
- A location whose country has no row → `ValueError` naming the country.
- A denominator of 0 → `d_k(c) = 0`.
- `energy_totals.csv` not available → the variable is skipped per C2.4 / P5.

Source: `export_ariadne_variables.py::get_final_energy` l.2453-2474 (`international_*_fraction`; `d_k = 1 − international fraction`); `resources/AT_KN2040/resources/energy_totals.csv`.

## D5 Non-energy use `NE_x(l)`
Non-energy use of carrier `x ∈ {gas, naphtha, H2}` in industry at location `l`. The sector definition excludes non-energy use: "industrial sector excluding non-energy use (e.g.feedstocks)" (`definitions/variable/tag_sector.yaml`). So final energy variables that contain industry demand of these carriers MUST subtract `NE_x(l)`.

- pypsa-de derives `NE_x` from `industry_production` and `industry_sector_ratios` (and, for ammonia, `config_industry`) (`get_final_energy` l.2034-2093). These inputs are not part of the results folder (`resources/AT_KN2040/resources/` contains only `energy_totals.csv`), and they are not inputs of a statistics function (C5).
- **The method to determine `NE_x(l)` is open (OQ-18; owner decision 2026-10-22: require exclusion, method open; related #61, #74).** Until it is resolved, a spec that uses D5 cannot reach status `implemented`.
- Every method MUST guarantee `0 ≤ NE_x(l) ≤` industry demand of `x` at `l`, so that results stay ≥ 0.

## D6 Coke correction for industrial coal `κ(l)`
pypsa-de counts the coke part of `coal for industry` as secondary energy and converts it back with `mwh_coal_per_mwh_coke = 1.366`:

```
FE_coal_industry = L[coal for industry]·(1 − κ) + L[coal for industry]·κ / 1.366
κ = coke·1.366 / (coke·1.366 + coal)      from industrial_energy_demand
```

(`get_final_energy` l.2208-2225.) The input `industrial_energy_demand` is not available (as D5). **The method to determine `κ(l)` is open (OQ-18).** Until it is resolved, a spec that uses D6 cannot reach status `implemented`.

## D7 Unit of `land transport oil`
`land transport oil` Loads sit on buses with `unit = "land transport"` (measured: `AT11 land transport oil`, unit `land transport`). This is a bus label, not a physical unit (C9.1, SC-9). The Load is fuel energy (LHV): pypsa-eur builds it as `profile = ice_share * p_set.div(efficiency)` (`sister_packages/pypsa-de/scripts/prepare_sector_network.py::add_ice_cars`, l.2730-2765). Measured for AT 2020: 65.39 TWh = 235 PJ, of the same order as the Austrian transport final energy of 314 PJ in #2.

A statistics function MUST therefore report this flow with unit `MWh_LHV` and MUST NOT divide it by a vehicle efficiency (see OQ-19 for the contrary hint in #19).
