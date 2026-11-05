# Shared definitions for variable specs

Status: reviewed (G1, G2, D1–D8); draft (D9)

Rules and quantities used by more than one variable spec. Variable specs reference them as G1, G2 and D1–D9 instead of repeating them, so that copies cannot diverge (same reasoning as for [../constitution/principles.md](../constitution/principles.md), see [../README.md](../README.md)). Code that implements a shared quantity MUST live in `pypsa_validation_processing/utils.py` (P4).

Measurements cited below were made on 2026-10-22 with pypsa 1.1.2 on `resources/AT_KN2040/networks/base_s_adm__none_2020.nc` and `…_2040.nc` (54 locations, 1460 snapshots, snapshot weighting 6 h).

Checked on 2026-10-23 against `resources/20261020_carbon_accounting_run/networks/solved_{2025,2030,2040,2050}.nc` (52 locations, 24 snapshots, weighting 365 h): D1 (single `EU oil`, `EU coal` buses; 51 regional `gas` buses), D7 (`land transport oil` bus unit `land transport`; Load absent in 2050) and the D8 port convention of heat pumps (`bus0` heat, `bus1` `low voltage`) hold. Deviations: OQ-23 (D2, D3; resolved), OQ-25 (D8; resolved), OQ-26 (kerosene in `Final Energy [by Carrier]|Oil`; resolved).

Notation: `L[c](l)` = withdrawal of the Loads with carrier `c` at location `l`; `W[bc, c](l)` = withdrawal of components with carrier `c` from buses with bus carrier `bc`; `S[bc, c]` = supply to buses with bus carrier `bc`. All flows are `flow` quantities in the sense of C6.10: weighted sum over snapshots for `aggregate_per_year=True`, unweighted per-snapshot values for `aggregate_per_year=False`.

## G1 Final energy is measured at the consumer
Owner decision 2026-10-23. Every `Final Energy` variable measures energy where the consumer receives it:
- withdrawals of Loads (e.g. `industry electricity`, `land transport oil`);
- inputs of end-use technologies at the consumer (decentral boilers and heat pumps, `BEV charger`, …; D8);
- heat received by consumers from heat networks: from `urban central heat` (Loads, `Final Energy [by Carrier]|District Heat`) and, in D8, the heat that consumers on a decentral heat bus receive from heat-only sources without an input at the consumer (decentral solar thermal) and from CHPs.

Outputs of conversion technologies (power plants, CHPs, refineries, fuel-supply Links, solar thermal, …) never count as final energy. Where D8 uses the heat supply of a CHP or a solar thermal Generator at a decentral bus, this is only because that bus has no losses, so the heat received by its consumers equals that supply; the quantity measured is still the heat received at the consumer. Production-side variables (e.g. `Secondary Energy|…`, not yet specified) count outputs: CHP heat output counts towards heat variables, CHP electricity output towards electricity variables, and a variable that combines both counts both. Supply flows used only to compute shares or imports (D2, D3, `Net Imports|Oil`) are not final energy and are not affected.

## G2 Final energy is never negative
Owner decision 2026-10-28 (on #97: "Final Energy - variables must stay positive or equal to Zero (= must NOT become negative. Never). Ever."). Every `Final Energy` variable MUST be `≥ 0` at every location: the yearly value for `aggregate_per_year=True` and every snapshot column for `aggregate_per_year=False`. Subtracted corrections (non-energy use D5, coke D6, distribution losses) MUST NOT make a location negative. Results are not clipped; a negative value is a spec or implementation error.

Exception: `Final Energy [by Sector]|Transportation` and `Final Energy [by Carrier]|Electricity` subtract the `V2G` feed-in per snapshot. Their snapshot values MAY be negative; its yearly values MUST be `≥ 0` (owner decision 2026-10-28).

## D1 Location attribution
1. A Load flow is attributed to `n.buses.location` of the Load's bus.
2. A Link flow is attributed to `n.buses.location` of the bus at the evaluated port.
3. Exception for copperplate buses: if that bus is a copperplate bus (its location is `EU`), the flow MUST be attributed to `n.buses.location` of the Link's `bus1` (the bus that receives the converted energy, e.g. `AT11 rural heat` for a `rural oil boiler` fed from `EU oil`).
4. If `bus1` is a copperplate bus as well, the flow stays at the pseudo-location `EU`. Statistics functions return it (C6.13); `Network_Processor` drops it from the output (C8.7, OQ-17). The pseudo-location `EU` is the copperplate, not the European Union (`country: EU`, C8.8).

Reason: in PyPSA-AT, oil and coal are single copperplate buses (`EU oil`, `EU coal`; measured: 1 bus each), so withdrawals from them carry no regional information. Gas has regional buses (53 `… gas` buses), so the exception does not apply. pypsa-de achieves the same with `.filter(like=region)` on the component name (`export_ariadne_variables.py::get_final_energy`, e.g. l.2372-2381). Implemented by `utils.attribute_locations` (PR #132, 2026-11-04). It needs the index levels `component`, `name` and `location` (pass `components` as a list, C11) and does not regroup rows. Low-level helper: `utils.create_location_index_from_copperplate`.

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

Implemented by `utils.fossil_oil_share` (PR #133, 2026-11-04); carrier lists `OIL_FOSSIL_CARRIERS`, `OIL_NON_FOSSIL_CARRIERS`. The internal `_fossil_share` works only for bus carriers whose supplying carriers are classified here (D2, D3), e.g. not for `urban central heat` (owner, PR #133 review 2026-11-04).

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

Implemented by `utils.fossil_gas_share` (PR #134, 2026-11-04); carrier lists `GAS_FOSSIL_CARRIERS`, `GAS_NON_FOSSIL_CARRIERS`, `GAS_TRANSPORT_CARRIERS`. A Link counts as gas transport if its carrier is in `GAS_TRANSPORT_CARRIERS` or its `bus0` and `bus1` are both `gas` buses.

## D4 Domestic share of aviation and navigation `d_k(c)`
For `k ∈ {aviation, navigation}` and country `c` = the first two characters of the location (e.g. `AT11 → AT`):

```
d_k(c) = total domestic k / (total domestic k + total international k)
```

- The values are read from the `energy_totals` table (C2.4: from `n.meta`, else from `energy_totals.csv`), columns `total domestic aviation`, `total international aviation`, `total domestic navigation`, `total international navigation`, row `country == c`.
- The share MUST be determined per country, not one value for all locations (the old `utils.get_energy_totals_domestic_share` uses `AT` for all, OQ-1; it is removed in the WP4 PRs of Transportation and Oil, which use D4).
- The year is the energy totals year of the model run (`n.meta["energy"]["energy_totals_year"]` or `config["energy"]["energy_totals_year"]`, C2.4; OQ-1 resolved). The table passed holds that year only.
- The lookup is made only for locations with non-zero demand in a term weighted by `d_k`. A location whose weighted terms are all 0 (e.g. the pseudo-location `EU`, C6.13) gets 0 for them without a lookup.
- A location with non-zero weighted demand whose country has no row → `ValueError` naming the country. Measured: the `energy_totals` tables hold all 34 countries of the networks, and aviation and navigation Loads exist only at country locations, none at `EU` (`20261020_carbon_accounting_run` 2040, `electricity_network_0p3` 2025).
- A denominator of 0 → `d_k(c) = 0`.
- Energy totals not available → the variable is skipped per C2.4 / P5.

Source: `export_ariadne_variables.py::get_final_energy` l.2453-2474 (`international_*_fraction`; `d_k = 1 − international fraction`); `resources/AT_KN2040/resources/energy_totals.csv`.

Implemented by `utils.apply_domestic_share(energy_stats, energy_totals, kind)` (PR #135, 2026-11-04): multiplies each row by `d_k` of its country; rows that are 0 in every snapshot get no lookup.

## D5 Non-energy use `NE_x(l)`
Non-energy use of carrier `x ∈ {gas, naphtha, H2, coal}` in industry at location `l`. The sector definition excludes non-energy use: "industrial sector excluding non-energy use (e.g.feedstocks)" (`definitions/variable/tag_sector.yaml`). So final energy variables that contain industry demand of these carriers MUST subtract `NE_x(l)`.

Owner decision 2026-10-28 (OQ-18 resolved, option C): physical method if the network provides the data, Eurostat shares otherwise (C2.5). Coal added by owner decision 2026-10-29 (OQ-28): the Eurostat non-energy use of coal is excluded; blast-furnace use is not affected (Eurostat books it as transformation).

- **Physical method.** pypsa-de derives `NE_x` from `industry_production` and `industry_sector_ratios` (and, for ammonia, `config_industry`) (`get_final_energy` l.2034-2093). No PyPSA-AT network stores these tables yet; the method is specified in a follow-up spec once it does (C2.5). pypsa-de has no coal non-energy use ("no solids used for non-energy purposes", `export_ariadne_variables.py` l.2234); the follow-up spec MUST state how `NE_coal` is obtained then.
- **Eurostat fallback.** With the table `S = industry_non_energy_shares` (C2.5) and `c` = the first two characters of `l`:
  ```
  NE_gas(l)     = S[c, Natural Gas] · L[gas for industry](l)
  NE_naphtha(l) = S[c, Oil]         · L[naphtha for industry](l)
  NE_coal(l)    = S[c, Coal]        · L[coal for industry](l)
  NE_H2(l)      = 0
  ```
  - `naphtha for industry` uses the share of all oil products (`O4000XBIO`), not of naphtha alone: pypsa-eur's `naphtha for industry` holds the whole industrial oil demand, while Eurostat books naphtha as 100 % non-energy (AT 2024: `FC_IND_E` naphtha 0 GWh).
  - `NE_coal` uses the share of solid fossil fuels (`C0000X0350-0370`) with the non-energy use of **all sectors**, `FC_NE / (FC_IND_E + FC_NE)`: Eurostat leaves `FC_IND_NE` empty for solids in all 40 countries (measured 2026-10-29), so all non-energy use of coal is assumed to be industrial (owner decision 2026-10-29, OQ-28). `NE_coal` is taken from the `coal for industry` Load before the coke correction (D6). The PyPSA-AT `industrial_demand_overrides` behind this Load contain the non-energy use (owner statement 2026-10-29), so nothing is subtracted twice. Measured (`latest`): AT 0.134, DE 0.123, CZ 0.340, PL 0.026, GB 0.042 (2019); mean of 39 countries 0.102.
  - `NE_H2 = 0`: Eurostat has no hydrogen; H2 non-energy use is skipped (owner decision 2026-10-28), with one `WARNING` per call (C2.5).
  - `S` holds ISO 3166-1 alpha-2 codes (`GR`, `GB`), the same codes as the location prefixes (C2.5).
  - A country without a row for the carrier (e.g. `CH`, which is not in the Eurostat energy balance) → `S[c, x]` is the arithmetic mean (unweighted) of `S[·, x]` over all countries in the table for that carrier (owner decision 2026-10-29), with one `WARNING` per call naming country and carrier. No `WARNING` is logged for the copperplate `EU` (dropped from the output, C8.7). Measured (`latest`, 2026-10-29): Oil 0.526 (mean of 40 countries), Natural Gas 0.150 (35 countries); the mean includes countries outside the model (e.g. `UA`, `TR`). Since `0 ≤ S ≤ 1` for every row and every carrier has at least one row (both checked at initialisation, C2.5), the mean is defined and in `[0, 1]`.
  - The share is constant over snapshots; for time series output it is applied to every snapshot.
  - Measured (eurostat-energy-balance_processing#8, 2024): AT gas 0.104, AT oil 0.807; DE gas 0.103, DE oil 0.910; EU27_2020 gas 0.138. The current code uses one EU-27 gas factor of 0.060 (#61).
- Functions that use D5 MUST declare `industry_non_energy_shares` (C5); without the table they are skipped (C2.5).
- Every method MUST guarantee `0 ≤ NE_x(l) ≤` industry demand of `x` at `l` at every location and in every snapshot, so that the energy part stays ≥ 0 (G2). `NE_x(l)` is computed from the demand at `l` itself, never from a country or system total. With the fallback this follows from `0 ≤ S ≤ 1` (checked at initialisation, C2.5; also holds for the mean). As a safeguard for shares adapted after the check, the helper clips a share outside `[0, 1]` to `[0, 1]`, with one `WARNING` per call naming carrier and countries (owner, PR #136 review 2026-11-04). This clips a share, not a result, so G2 ("results are not clipped") still holds.

Implemented by `utils.non_energy_use(demand, shares, carrier)` (PR #136, 2026-11-04), `carrier ∈ {Natural Gas, Oil, Coal, H2}`, Eurostat fallback only. The shares file is written by `eurostat-energy-balance_processing` (C2.5, C11).

## D6 Coke correction for industrial coal `κ(l)`
pypsa-de counts the coke part of `coal for industry` as secondary energy and converts it back with `mwh_coal_per_mwh_coke = 1.366`:

```
FE_coal_industry = (L[coal for industry] − NE_coal)·(1 − κ) + (L[coal for industry] − NE_coal)·κ / 1.366
κ = coke·1.366 / (coke·1.366 + coal)      from industrial_energy_demand
```

(`get_final_energy` l.2208-2225; pypsa-de has no `NE_coal`, added by owner decision 2026-10-29, OQ-28: non-energy use first, the coke correction applies to the energy part only.) Owner decision 2026-10-28 (OQ-18 resolved, option C):

- **Physical method.** `κ` from the industry production data, once the networks carry it (C2.5, follow-up spec).
- **Eurostat fallback.** `κ(l) = 0`, with one `WARNING` per call (C2.5). Eurostat gives no usable value: it books blast-furnace coke as transformation, not as industrial final consumption, and reports no non-energy coke for AT (`FC_IND_NE` `C0311`: `: m`). `n.meta["resources"]["industrial_demand_overrides"]` splits `coal` and `coke` per region, but only for 2025 (measured in `20261020_carbon_accounting_run`), so it is not used.
- `κ = 0` overestimates coal final energy by at most the factor `1.366` on the coke part.

Implemented by `utils.apply_coke_correction(coal_energy, kappa=None)` (PR #137, 2026-11-04): `κ` is one scalar per call; `None` = Eurostat fallback `κ = 0` with one `WARNING`; `κ` outside `[0, 1]` → `ValueError`. The physical method needs `κ(l)` per location; the follow-up spec (C2.5) decides whether the helper then takes a per-location `κ`. The factor `1.366` (`MWH_COAL_PER_MWH_COKE`) is checked against the PyPSA industry preprocessing in the spec review after WP4 (owner, PR #137 review 2026-11-04; `TODO.md` WP4).

## D7 Unit of `land transport oil`
`land transport oil` Loads sit on buses with `unit = "land transport"` (measured: `AT11 land transport oil`, unit `land transport`). This is the bus unit label that pypsa-eur assigns (`add_ice_cars` l.2751-2757: `unit="land transport"`); it is a unit of the network, not the name of a physical unit. It is a permanent key of `UNITS_MAPPING` (→ `MWh`; owner, PR #123 review 2026-11-02; C9.1), so it passes result validation. The Load is fuel energy (LHV): pypsa-eur builds it as `profile = ice_share * p_set.div(efficiency)` (`sister_packages/pypsa-de/scripts/prepare_sector_network.py::add_ice_cars`, l.2730-2765). Measured for AT 2020: 65.39 TWh = 235 PJ, of the same order as the Austrian transport final energy of 314 PJ in #2.

A statistics function MAY report this flow with its raw unit label `land transport`; a relabelling to `MWh_LHV` is not required (owner, PR #127 review 2026-11-03, OQ-29 resolved). It MUST NOT divide the flow by a vehicle efficiency (owner decision 2026-10-22, OQ-19 resolved: the hint in #19 applies only to networks whose Load is not yet fuel energy). Check on AT 2025 (`resources/electricity_network_0p3`): 65.10 TWh = 234.4 PJ, against 267.4 PJ `Final Energy [by Sector]|Transportation|Oil` in the Eurostat energy balance 2024.

Boundary between function and post-processing: the results of `Final Energy [by Carrier]|Oil` and `Final Energy [by Sector]|Transportation` MAY contain the raw unit `land transport` (one row per location and raw unit). `Network_Processor` normalises it to `MWh` via `UNITS_MAPPING` after the function (C8 step 2, C9.1) and sums the rows of one location (C8 step 3). Only the post-processed output is in `MWh` (or the definition unit, C9.2). A function that sums flows of different units within one row MUST normalise them first (C6.5).

No helper (PR #137, 2026-11-04): the comment at `UNITS_MAPPING` and tests only (SC-9 resolved).

## D8 Split of decentral heat input between sectors `D8_sec(l)`
Owner decision 2026-10-22 (OQ-22 resolved): for decentral heat, the `Final Energy [by Sector]` variables measure the **energy input** to decentral heat supply, not the delivered heat. The input is split between sectors per location, in proportion to their heat demands. District heat (`urban central heat`) is not affected; there the delivered heat is counted (`Final Energy [by Carrier]|District Heat`).

For each decentral bus type `b ∈ {rural heat, urban decentral heat}` and location `l`:

1. **Input `I_b(l)`**: energy entering the decentral heat supply of `b` at `l`, kept per input carrier:
   - Every Link with positive yearly heat supply to a `b` bus that is not a CHP (in PyPSA-AT: `rural|urban decentral` `gas boiler`, `oil boiler`, `biomass boiler`, `resistive heater`, `air heat pump`, `ground heat pump`): withdrawal at the input port, i.e. at the bus that is not the heat bus. For heat pumps in PyPSA-AT this is `bus1` = `low voltage`, because `bus0` is the heat bus (measured AT11 2025). Location per D1 (e.g. `rural oil boiler` from `EU oil` → location of its heat bus).
   - Every Generator with positive yearly heat supply to a `b` bus (in PyPSA-AT: `rural solar thermal`, `urban decentral solar thermal`): the heat that consumers on `b` receive from them, measured at the consumer (G1); numerically equal to their heat supply at the `b` bus (as pypsa-de, l.2349-2350: "for solar thermal secondary energy == Final energy").
   - CHPs, i.e. Links with a heat output to a `b` bus and a further non-heat output (e.g. `biogas CHP`: bus0 `biogas`, bus1 `AC`, bus2 `rural heat`): the heat that consumers on `b` receive from them, measured at the consumer (G1); numerically equal to the CHP heat supply at the `b` port. Neither the CHP input nor its electricity output is part of `I_b` (the electricity is counted where it is consumed). This treats CHP heat on decentral buses like CHP heat on `urban central heat` buses, where the heat received by consumers is counted (`Final Energy [by Carrier]|District Heat`). Owner decision 2026-10-23 (OQ-25, G1).
   - The carrier lists above describe PyPSA-AT; they are not exhaustive. A new heat technology on a `b` bus is counted by the same rules without a spec change (owner, 2026-11-04, WP3 spec review).
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

Implemented by `utils.decentral_heat_split(n, aggregate_per_year)` (PR #138, 2026-11-04). Implementation rules, decided by the owner in the PR #138 review (2026-11-04):
- **Result.** Index levels `sector` (`rc`, `agr`, `ind`, `other`), `location`, `carrier`, `unit` (normalised to `MWh`). `carrier` is the bus carrier of the input port (e.g. `low voltage`, `gas`, `oil`, `solid biomass`), not the Link carrier; for heat received from Generators and CHPs it is `b` itself, so solar thermal and CHP heat are not told apart (the sector variables do not need it); to be reviewed after WP4, CHP and solar thermal heat need to be told apart (owner, PR #141 review 2026-11-04, see TODO.md). A network without a supplied decentral heat bus gives a result with zero rows; the calling statistics function turns it into `0.0` per location (C6.13).
- **Selection.** Heat suppliers are the Links and Generators with positive yearly supply to `b`; flows are selected by `(component, name)`, since a Generator and a Link MAY have the same name. A CHP is such a Link with positive yearly supply to a further bus carrier that is neither `b` nor a CO2 carrier.
- **CO2 ports.** Bus carriers whose name contains `co2` are neither an input nor a CHP output. CO2 bus carriers are always named `co2…`; a check of the bus unit (`t_co2`) is not required.
- **Storage.** Components whose carrier matches `water tanks`, `water pits` or `heat vent` are neither input nor demand; `Store` and `StorageUnit` are never demand. PyPSA-AT has no `StorageUnit` on decentral heat buses, but the code is prepared for it.
- **Input without demand.** A location with `I_b(l) > 0` and no heat demand on `b` gets `σ_b,x(l) = 0` (step 3), so its input is in no sector. This does not occur in valid networks (heat supply follows heat demand), so no `WARNING` is logged.

## D9 Demand-weighted price of an industry Load `P[c](l)`
Owner decision 2026-11-05 (spec session for milestone 2 "Implement Infra-Enshure Coupling Variables"): the `Price|Final Energy|Industry|…` variables are the **marginal price at the bus of the industry Load, weighted by the Load's withdrawal**. This is the price the industry demand pays in the model; it is the formula of pypsa-de `price_load` (`export_ariadne_variables.py` l.3378-3402, commit `a5baa7e9`). Cost-based prices (`costs_gen_links`, `get_weighted_costs_links`, l.3442-3516) are not used, also where pypsa-de uses them for the same variable (deviation recorded in the variable spec).

For a Load carrier `c` and location `l` (Loads attributed per D1.1):

1. **Weight** `w[c](l)` = `L[c](l)`, the withdrawal of the Loads with carrier `c` at `l` (C6.12 `weight` row).
2. **Cost** `K[c](l)` = Σ over these Loads of `p·λ`, with `p` the Load withdrawal and `λ` = `n.buses_t.marginal_price` of the Load's bus. Same time convention as `w` (C6.10, C6.12).
3. **Value** `P[c](l) = K[c](l) / w[c](l)`; if `w[c](l) = 0`, value and weight are `0.0` (A-5). With `aggregate_per_year=False` this holds per snapshot: `P_t = K_t / w_t`, so a snapshot without withdrawal has the value `0.0`.

Consistency with C6.12: the yearly value equals `Σₜ vₜ·wₜ·gₜ / Σₜ wₜ·gₜ` of the snapshot values, because `vₜ·wₜ = K_t`.

`pypsa.statistics` route (checked 2026-11-05, pypsa 1.1.2, `resources/20261020_carbon_accounting_run/networks/solved_2040.nc`, carrier `gas for industry`): `K = −n.statistics.revenue(components=["Load"], carrier=c, groupby=["location", "unit"], nice_names=False)` and `w = n.statistics.withdrawal(…)` with the same arguments; `−Σ revenue / Σ withdrawal` = 85.0805 EUR/MWh, identical to the manual `Σ p·λ·g / Σ p·g`. `revenue` labels its rows with the **bus unit** (e.g. `MWh_LHV`), not a currency: the function MUST set the `unit` label of value and weight rows to the price unit itself (C6.12: weight rows carry the unit label of their value row; OQ-34).

Measured on the same network (yearly, all 51 locations): `industry electricity` 100.61, `gas for industry` 85.08, `H2 for industry` 72.06, `solid biomass for industry` 68.14, `coal for industry` 111.94, `naphtha for industry` 53.99, `industry methanol` 121.13 EUR/MWh. All seven Load carriers have one Load on a regional bus per location (no copperplate bus), bus units `MWh_el` (`industry electricity`) and `MWh_LHV` (the others).

The marginal price of a bus fed by a Link includes every cost the optimisation assigns to that supply, e.g. a CO2 price through the `co2 atmosphere` port of `gas for industry` Links when the CO2 constraint binds (assumption A-8, not verified).

Code that implements `P[c](l)` MUST live in `utils.py` (P4); each `Price|Final Energy|Industry|…` function calls it with its carrier(s). With several carriers (e.g. `c ∈ {coal for industry, …}` later), `K` and `w` are summed over the carriers before dividing.
