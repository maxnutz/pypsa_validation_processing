# Variable specs

One spec per IAMC variable, written from [../templates/statistics_function.md](../templates/statistics_function.md). File name: `<function_name>.md` (see [../README.md](../README.md) "Naming of spec files").

Rules and quantities used by several variables (final energy measured at the consumer, final energy never negative, location attribution, fossil fuel shares, domestic transport shares, non-energy use, coke correction, unit of land transport, sector split of decentral heat input) are specified once in [shared_definitions.md](shared_definitions.md) (G1, G2, D1–D8).

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

Not yet specified: `Prices|Final Energy|Electricity` (#99; mapped only in `mapping.prices_ie.yaml`, no working implementation).
