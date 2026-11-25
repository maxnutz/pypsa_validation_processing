# Variable specs

One spec per IAMC variable, written from [../templates/statistics_function.md](../templates/statistics_function.md). File name: `<function_name>.md` (see [../README.md](../README.md) "Naming of spec files").

Rules and quantities used by several variables (final energy measured at the consumer, final energy never negative, location attribution, fossil fuel shares, domestic transport shares, non-energy use, coke correction, unit of land transport, sector split of decentral heat input, demand-weighted price of industry Loads, electricity supply by source, district heat supply by source) are specified once in [shared_definitions.md](shared_definitions.md) (G1, G2, D1–D11).

## Index
| IAMC variable | Spec | Match type | Status |
|---|---|---|---|
| `Final Energy [by Carrier]\|Electricity` | [Final_Energy_by_Carrier__Electricity.md](Final_Energy_by_Carrier__Electricity.md) | exact | reviewed |
| `Final Energy [by Carrier]\|Coal` | [Final_Energy_by_Carrier__Coal.md](Final_Energy_by_Carrier__Coal.md) | semantic | reviewed |
| `Final Energy [by Carrier]\|Natural Gas` | [Final_Energy_by_Carrier__Natural_Gas.md](Final_Energy_by_Carrier__Natural_Gas.md) | semantic | reviewed |
| `Final Energy [by Carrier]\|Oil` | [Final_Energy_by_Carrier__Oil.md](Final_Energy_by_Carrier__Oil.md) | semantic | reviewed |
| `Final Energy [by Carrier]\|District Heat` | [Final_Energy_by_Carrier__District_Heat.md](Final_Energy_by_Carrier__District_Heat.md) | semantic (partial) | reviewed |
| `Net Imports\|Electricity` | [Net_Imports__Electricity.md](Net_Imports__Electricity.md) | semantic | reviewed |
| `Net Imports\|Oil` | [Net_Imports__Oil.md](Net_Imports__Oil.md) | none | reviewed |
| `Final Energy [by Sector]\|Transportation` | [Final_Energy_by_Sector__Transportation.md](Final_Energy_by_Sector__Transportation.md) | exact | reviewed |
| `Final Energy [by Sector]\|Industry` | [Final_Energy_by_Sector__Industry.md](Final_Energy_by_Sector__Industry.md) | semantic | reviewed |
| `Final Energy [by Sector]\|Agriculture` | [Final_Energy_by_Sector__Agriculture.md](Final_Energy_by_Sector__Agriculture.md) | exact | reviewed |
| `Final Energy [by Sector]\|Residential and Commercial` | [Final_Energy_by_Sector__Residential_and_Commercial.md](Final_Energy_by_Sector__Residential_and_Commercial.md) | exact | reviewed |
| `Price\|Final Energy\|Industry\|Electricity` | [Price__Final_Energy__Industry__Electricity.md](Price__Final_Energy__Industry__Electricity.md) | exact | reviewed |
| `Price\|Final Energy\|Industry\|Gases` | [Price__Final_Energy__Industry__Gases.md](Price__Final_Energy__Industry__Gases.md) | semantic | reviewed |
| `Price\|Final Energy\|Industry\|Hydrogen` | [Price__Final_Energy__Industry__Hydrogen.md](Price__Final_Energy__Industry__Hydrogen.md) | exact | reviewed |
| `Price\|Final Energy\|Industry\|Solids\|Biomass` | [Price__Final_Energy__Industry__Solids__Biomass.md](Price__Final_Energy__Industry__Solids__Biomass.md) | exact | reviewed |
| `Price\|Final Energy\|Industry\|Solids\|Coal` | [Price__Final_Energy__Industry__Solids__Coal.md](Price__Final_Energy__Industry__Solids__Coal.md) | exact | reviewed |
| `Price\|Final Energy\|Industry\|Liquids\|Oil` | [Price__Final_Energy__Industry__Liquids__Oil.md](Price__Final_Energy__Industry__Liquids__Oil.md) | semantic | reviewed |
| `Secondary Energy\|Electricity w/o CHP\|Coal` | [Secondary_Energy__Electricity_wo_CHP__Coal.md](Secondary_Energy__Electricity_wo_CHP__Coal.md) | semantic | draft |
| `Secondary Energy\|Electricity w/o CHP\|Oil` | [Secondary_Energy__Electricity_wo_CHP__Oil.md](Secondary_Energy__Electricity_wo_CHP__Oil.md) | semantic | draft |
| `Secondary Energy\|Electricity w/o CHP\|Gas Grid Mix` | [Secondary_Energy__Electricity_wo_CHP__Gas_Grid_Mix.md](Secondary_Energy__Electricity_wo_CHP__Gas_Grid_Mix.md) | semantic | draft |
| `Secondary Energy\|Electricity\|Solar` | [Secondary_Energy__Electricity__Solar.md](Secondary_Energy__Electricity__Solar.md) | exact | draft |
| `Secondary Energy\|Electricity\|Wind` | [Secondary_Energy__Electricity__Wind.md](Secondary_Energy__Electricity__Wind.md) | exact | draft |
| `Secondary Energy\|Electricity\|Hydro` | [Secondary_Energy__Electricity__Hydro.md](Secondary_Energy__Electricity__Hydro.md) | exact | draft |
| `Secondary Energy\|Electricity w/o CHP\|Biomass` | [Secondary_Energy__Electricity_wo_CHP__Biomass.md](Secondary_Energy__Electricity_wo_CHP__Biomass.md) | semantic | draft |
| `Secondary Energy\|Electricity w/o CHP\|Waste` | [Secondary_Energy__Electricity_wo_CHP__Waste.md](Secondary_Energy__Electricity_wo_CHP__Waste.md) | semantic | draft |
| `Secondary Energy\|Electricity w/o CHP\|Other` | [Secondary_Energy__Electricity_wo_CHP__Other.md](Secondary_Energy__Electricity_wo_CHP__Other.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Coal` | [Secondary_Energy__Electricity__CHP__Coal.md](Secondary_Energy__Electricity__CHP__Coal.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Oil` | [Secondary_Energy__Electricity__CHP__Oil.md](Secondary_Energy__Electricity__CHP__Oil.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Gas Grid Mix` | [Secondary_Energy__Electricity__CHP__Gas_Grid_Mix.md](Secondary_Energy__Electricity__CHP__Gas_Grid_Mix.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Waste` | [Secondary_Energy__Electricity__CHP__Waste.md](Secondary_Energy__Electricity__CHP__Waste.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Biomass` | [Secondary_Energy__Electricity__CHP__Biomass.md](Secondary_Energy__Electricity__CHP__Biomass.md) | semantic | draft |
| `Secondary Energy\|Electricity\|CHP\|Other` | [Secondary_Energy__Electricity__CHP__Other.md](Secondary_Energy__Electricity__CHP__Other.md) | semantic | draft |

Not yet specified: the 11 `Secondary Energy|District Heating|…`, `Secondary Energy|District Heating w/o CHP|…` and `Secondary Energy|District Heating|CHP|…` variables (#202–#212, WP8; shared definition D11); `Investment|…` (#106, OQ-36); further industry prices from #76: `industry methanol` price (#172, name to be fixed in its spec) and the aggregates `…|Liquids`, `…|Solids` (#173); `low-temperature heat for industry` out of scope (OQ-35, owner 2026-11-11).
