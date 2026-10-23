# Shared definitions for variable specs

Status: draft

Rules and quantities used by more than one variable spec. Variable specs reference them as G1 and D1–D8 instead of repeating them, so that copies cannot diverge (same reasoning as for [../constitution/principles.md](../constitution/principles.md), see [../README.md](../README.md)). Code that implements a shared quantity MUST live in `pypsa_validation_processing/utils.py` (P4).

Measurements cited below were made on 2026-10-22 with pypsa 1.1.2 on `resources/AT_KN2040/networks/base_s_adm__none_2020.nc` and `…_2040.nc` (54 locations, 1460 snapshots, snapshot weighting 6 h).

Checked on 2026-10-23 against `resources/20261020_carbon_accounting_run/networks/solved_{2025,2030,2040,2050}.nc` (52 locations, 24 snapshots, weighting 365 h): D1 (single `EU oil`, `EU coal` buses; 51 regional `gas` buses), D7 (`land transport oil` bus unit `land transport`; Load absent in 2050) and the D8 port convention of heat pumps (`bus0` heat, `bus1` `low voltage`) hold. Deviations: OQ-23 (D2, D3; resolved), OQ-25 (D8; resolved), OQ-26 (kerosene in `Final Energy [by Carrier]|Oil`; resolved).

Notation: `L[c](l)` = withdrawal of the Loads with carrier `c` at location `l`; `W[bc, c](l)` = withdrawal of components with carrier `c` from buses with bus carrier `bc`; `S[bc, c]` = supply to buses with bus carrier `bc`. All flows are `flow` quantities in the sense of C6.10: weighted sum over snapshots for `aggregate_per_year=True`, unweighted per-snapshot values for `aggregate_per_year=False`.

## G1 Final energy is measured at the consumer
Owner decision 2026-10-23. Every `Final Energy` variable measures energy where the consumer receives it:
- withdrawals of Loads (e.g. `industry electricity`, `land transport oil`);
- inputs of end-use technologies at the consumer (decentral boilers and heat pumps, `BEV charger`, …; D8);
- heat received by consumers from heat networks: from `urban central heat` (Loads, `Final Energy [by Carrier]|District Heat`) and, in D8, the heat that consumers on a decentral heat bus receive from heat-only sources without an input at the consumer (decentral solar thermal) and from CHPs.

Outputs of conversion technologies (power plants, CHPs, refineries, fuel-supply Links, solar thermal, …) never count as final energy. Where D8 uses the heat supply of a CHP or a solar thermal Generator at a decentral bus, this is only because that bus has no losses, so the heat received by its consumers equals that supply; the quantity measured is still the heat received at the consumer. Production-side variables (e.g. `Secondary Energy|…`, not yet specified) count outputs: CHP heat output counts towards heat variables, CHP electricity output towards electricity variables, and a variable that combines both counts both. Supply flows used only to compute shares or imports (D2, D3, `Net Imports|Oil`) are not final energy and are not affected.

## D1 Location attribution
1. A Load flow is attributed to `n.buses.location` of the Load's bus.
2. A Link flow is attributed to `n.buses.location` of the bus at the evaluated port.
3. Exception for copperplate buses: if that bus is a copperplate bus (its location is `EU`), the flow MUST be attributed to `n.buses.location` of the Link's `bus1` (the bus that receives the converted energy, e.g. `AT11 rural heat` for a `rural oil boiler` fed from `EU oil`).
4. If `bus1` is a copperplate bus as well, the flow stays at the pseudo-location `EU`. Statistics functions return it (C6.13); `Network_Processor` drops it from the output (C8.7, OQ-17). The pseudo-location `EU` is the copperplate, not the European Union (`country: EU`, C8.8).

Reason: in PyPSA-AT, oil and coal are single copperplate buses (`EU oil`, `EU coal`; measured: 1 bus each), so withdrawals from them carry no regional information. Gas has regional buses (53 `… gas` buses), so the exception does not apply. pypsa-de achieves the same with `.filter(like=region)` on the component name (`export_ariadne_variables.py::get_final_energy`, e.g. l.2372-2381). Existing helper: `utils.create_location_index_from_copperplate`.

## D2 Fossil share of oil `f_oil`
One yearly value for the whole network (owner decision, 2026-10-22: system-wide, pypsa-de approach):

```
f_oil = S[oil, "oil refining"] / Σ_c S[oil, c]     for c ∈ C_oil
C_oil = {"oil refining", "Fischer-Tropsch", "biomass to liquid", "biomass to liquid CC",
         "electrobiofuels", "unsustainable bioliquids", "import oil"}
```

- Supply is counted at the Link port that feeds the oil bus (`bus1`), weighted over the year (`groupby_time=True`), summed over all locations.
- Stores (`oil` Store) are excluded: they shift energy in time and do not produce it.
- `f_oil` is the same scalar for every location and every snapshot. With `aggregate_per_year=False` the yearly `f_oil` MUST be applied to every snapshot column, so that the `flow` consistency of C6-AC3 holds (avoids SC-23).
- If `Σ_c S[oil, c] = 0`, then `f_oil = 0` (no oil supplied, so no fossil oil).
- `import oil` is non-fossil (OQ-23 resolved; see the classification below).
- A component other than a Store whose **yearly supply** to an `oil` bus is non-zero and whose carrier is outside `C_oil` MUST raise `ValueError` naming the carrier (P5; the spec does not cover such a network). A component of such a carrier with zero yearly supply (e.g. an unused import Link) is ignored.
- By construction `0 ≤ f_oil ≤ 1`. No clipping is needed, so no renewable production is "lost" (resolves the problem of #53).

Sources: `export_ariadne_variables.py::_get_fuel_fractions` l.109-242 (pypsa-de commit `a5baa7e9`). Adaptation: pypsa-de distinguishes `DE oil`/`EU oil` and `renewable oil` buses. PyPSA-AT networks have neither `renewable oil` nor `renewable gas` buses (measured 2020 and 2040), but have a single `EU oil` bus. Supplying carriers measured: 2020 `oil refining` 5873.20 TWh, `unsustainable bioliquids` 192.16, `biomass to liquid` 15.90, `biomass to liquid CC` 0.01, `electrobiofuels` 0.01, `Fischer-Tropsch` 0.00, `oil` Store 0.04; 2040 `oil refining` 1662.45, `electrobiofuels` 599.68, `Fischer-Tropsch` 182.11. `unsustainable bioliquids` is non-fossil as in pypsa-de (`fuel_fractions["Biomass"] = renewable_fuel_balance.filter(like="bio")`, l.226).

Classification of supplying carriers (owner decision 2026-10-23, OQ-23): a supplying carrier is non-fossil if it takes CO2 from `co2 atmosphere` (or from biomass, e.g. `bio*`, `unsustainable bioliquids`) in the amount that its fuel emits when burned, so that its net emissions are zero. A fossil carrier has no such offset. New carriers are added to the lists of D2/D3 by a spec change according to this criterion.

Evidence for `import oil` / `import gas` (measured 2026-10-23 on `resources/20261020_carbon_accounting_run/networks/solved_{2025,2030,2040,2050}.nc`): both are Links `co2 atmosphere` (bus0) → `EU oil` / regional `gas` (bus1), built by pypsa-eur `add_import_options` ("Add green energy import options", `prepare_sector_network.py` l.6445-6515). They withdraw 1/`efficiency` = 0.2571 t CO2 per MWh oil and 0.198 t CO2 per MWh gas from `co2 atmosphere`, equal to `efficiency2` (emission to `co2 atmosphere`) of the oil consumers (`kerosene for aviation`, `land transport oil`, `rural oil boiler`) and gas consumers (`rural gas boiler`, `gas for industry`, `CCGT`). `p0 ≥ 0` in every snapshot (only removal). Atmosphere balance 2025/2030/2040/2050: `import oil` 0/0/−129.30/0 Mt (2040: 502.91 TWh, `f_oil` = 0.697), `import gas` −0.24/−0.28/0/0 Mt. Fossil supply (`oil primary` → `oil refining`, gas Generators) has no such offset.

## D3 Fossil share of gas `f_gas`
One yearly value for the whole network, as D2:

```
f_gas = Σ_g S[gas, g] / (Σ_g S[gas, g] + Σ_r S[gas, r])
g ∈ G_fossil    = {"lng gas", "pipeline gas", "production gas"}   (Generators)
r ∈ G_renewable = {"Sabatier", "biogas to gas", "biogas to gas CC", "BioSNG", "BioSNG CC", "import gas"}   (Links, port bus1)
```

- Excluded: gas transport (`gas pipeline`, `gas pipeline new`, Links between gas buses) and Stores (`gas`).
- Same rules as D2 for time series, zero denominator (`f_gas = 0`), unknown supplying carriers (`ValueError` only for non-zero yearly supply), and classification of supplying carriers.
- `import gas` is non-fossil (OQ-23 resolved; evidence in D2).

Sources: `_get_fuel_fractions` l.109-242 (`fuel_fractions["Natural Gas"]` = gas compressing share; `"Efuel"` = Sabatier; `"Biomass"` = `bio*`). Supplying carriers measured: 2020 Generators `pipeline gas` 2006.07 TWh, `production gas` 1714.52, `lng gas` 158.43; Links `biogas to gas` 196.11, `Sabatier` 19.44, `biogas to gas CC` 1.72, `BioSNG` 0.01, `BioSNG CC` 0.00; transport `gas pipeline` 1024.75, `gas pipeline new` 6390.43; Store `gas` 667.35.

## D4 Domestic share of aviation and navigation `d_k(c)`
For `k ∈ {aviation, navigation}` and country `c` = the first two characters of the location (e.g. `AT11 → AT`):

```
d_k(c) = total domestic k / (total domestic k + total international k)
```

- The values are read from the `energy_totals` table (C2.4: from `n.meta`, else from `energy_totals.csv`), columns `total domestic aviation`, `total international aviation`, `total domestic navigation`, `total international navigation`, row `country == c`.
- The share MUST be determined per country, not one value for all locations (current `utils.get_energy_totals_domestic_share` uses `AT` for all, OQ-1).
- The year is the energy totals year of the model run (`n.meta["energy"]["energy_totals_year"]` or `config["energy"]["energy_totals_year"]`, C2.4; OQ-1 resolved). The table passed holds that year only.
- A location whose country has no row → `ValueError` naming the country.
- A denominator of 0 → `d_k(c) = 0`.
- Energy totals not available → the variable is skipped per C2.4 / P5.

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

A statistics function MUST therefore report this flow with unit `MWh_LHV` and MUST NOT divide it by a vehicle efficiency (owner decision 2026-10-22, OQ-19 resolved: the hint in #19 applies only to networks whose Load is not yet fuel energy). Check on AT 2025 (`resources/electricity_network_0p3`): 65.10 TWh = 234.4 PJ, against 267.4 PJ `Final Energy [by Sector]|Transportation|Oil` in the Eurostat energy balance 2024.

## D8 Split of decentral heat input between sectors `D8_sec(l)`
Owner decision 2026-10-22 (OQ-22 resolved): for decentral heat, the `Final Energy [by Sector]` variables measure the **energy input** to decentral heat supply, not the delivered heat. The input is split between sectors per location, in proportion to their heat demands. District heat (`urban central heat`) is not affected; there the delivered heat is counted (`Final Energy [by Carrier]|District Heat`).

For each decentral bus type `b ∈ {rural heat, urban decentral heat}` and location `l`:

1. **Input `I_b(l)`**: energy entering the decentral heat supply of `b` at `l`, kept per input carrier:
   - Links whose heat output goes to a `b` bus (`rural|urban decentral` `gas boiler`, `oil boiler`, `biomass boiler`, `resistive heater`, `air heat pump`, `ground heat pump`): withdrawal at the input port, i.e. at the bus that is not the heat bus. For heat pumps in PyPSA-AT this is `bus1` = `low voltage`, because `bus0` is the heat bus (measured AT11 2025). Location per D1 (e.g. `rural oil boiler` from `EU oil` → location of its heat bus).
   - Generators `rural solar thermal`, `urban decentral solar thermal`: the heat that consumers on `b` receive from them, measured at the consumer (G1); numerically equal to their heat supply at the `b` bus (as pypsa-de, l.2349-2350: "for solar thermal secondary energy == Final energy").
   - CHPs, i.e. Links with a heat output to a `b` bus and a further non-heat output (e.g. `biogas CHP`: bus0 `biogas`, bus1 `AC`, bus2 `rural heat`): the heat that consumers on `b` receive from them, measured at the consumer (G1); numerically equal to the CHP heat supply at the `b` port. Neither the CHP input nor its electricity output is part of `I_b` (the electricity is counted where it is consumed). This treats CHP heat on decentral buses like CHP heat on `urban central heat` buses, where the heat received by consumers is counted (`Final Energy [by Carrier]|District Heat`). Owner decision 2026-10-23 (OQ-25, G1).
   - Excluded: water-tank/pit chargers and dischargers (storage), heat vents (dumped heat). Ambient heat drawn by heat pumps is not part of `I_b` (`Final Energy [by Carrier]|Ambient Heat`, #75).
2. **Heat demands `H_b,x(l)`** (yearly, withdrawals from `b` buses at `l`):
   - `x = rc`: Load `rural heat` (on `rural heat`), Load `urban decentral heat` (on `urban decentral heat`);
   - `x = agr`: Load `agriculture heat` (on `rural heat`);
   - `x = ind`: Load `low-temperature heat for industry` (on `urban decentral heat`; pypsa-eur places it there only in nodes without an `urban central heat` bus, `prepare_sector_network.py` l.5280-5294);
   - `x = other`: any other withdrawal except storage chargers and heat vents (e.g. `DAC` on `urban decentral heat`). Its share is not assigned to any of the three sectors.
3. **Share** `σ_b,x(l) = H_b,x(l) / Σ_x H_b,x(l)`. If the denominator is 0, then `σ_b,x(l) = 0`. Shares are computed from yearly values and applied to every snapshot, so that C6-AC3 holds.
4. **Sector value** `D8_x(l) = Σ_b σ_b,x(l) · I_b(l)`. Values are normalised to `MWh` before summing over input carriers (C6.5).

Consistency: for every `l` and `b`, `Σ_x σ_b,x(l) · I_b(l) = I_b(l)` (no energy is counted twice or lost). `Final Energy [by Carrier]|*` variables are not split by sector and keep counting the full input of their carrier (e.g. all `rural oil boiler` oil in `Final Energy [by Carrier]|Oil`).

Deviation from pypsa-de: pypsa-de assigns the full decentral input to Residential and Commercial (l.2297-2409) and counts `agriculture heat` (l.2556) and decentral `low-temperature heat for industry` (l.2121-2123) as heat. This double counts; AT 2025 (`electricity_network_0p3`): `rural heat` 2.60 TWh, `urban decentral heat` 0.09 TWh, total ≈ 9.7 PJ (OQ-22). Shares vary per location (`rural heat`, agriculture share 4.9–100 %), so a per-location split is required.
