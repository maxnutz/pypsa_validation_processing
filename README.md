![Python](https://img.shields.io/badge/python-3.11-blue)  [![license](https://img.shields.io/badge/License-MIT-blue)](https://github.com/maxnutz/pypsa_validation_processing/blob/master/LICENSE) [![pyam](https://img.shields.io/badge/pyam-iamc-blue)](https://github.com/IAMconsortium/pyam) [![Tests](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml/badge.svg)](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml)

# PyPSA-network processing for validation
This repository is licensed under the [MIT License](https://github.com/maxnutz/pypsa_validation_processing/blob/main/LICENSE)

> [!NOTE]  
> This package is currently in an **early state of development**. Expect ongoing changes and updates. Documentation and Readme will be continuously updated with changes.

This package processes a PyPSA network for a given set of defined IAMC-Variables to build a structured timeseries output and data-output to be used for model validation against the Eurostat Energy Balance. 

> [!TIP]
> The corresponding package for Eurostat Energy Balance Evaluation is available [here](https://github.com/maxnutz/eurostat-energy-balance_processing/tree/main)

## Quick start

### Project environment 
- install pixi environment with `pixi install`. Manual installation is optional, pixi installes the environment before first execution itself.
- use pixi environment by adding `pixi run` before statements in cli 


### Installation

```bash
pip install .
```
### Run the workflow
Run the workflow with 
```bash
pixi run workflow
```
This statement runs `"python workflow.py"` 
### Run tests
Run tests with
```bash
pixi run test
```
This statement runs `"pytest tests/ -v"` 

## Project structure

```text
pypsa_validation_processing/
|-- workflow.py                         # CLI/entry script
|-- pypsa_validation_processing/
|   |-- workflow.py                     # package-level workflow orchestration
|   |-- class_definitions.py            # core processing classes
|   |-- statistics_functions.py         # pypsa statistics functions
|   |-- utils.py                        # static information and general utility functions
|   `-- configs/                        # package configuration files
        `-- config.default.yaml         # default configuration file
        `-- mapping.default.yaml        # mapping IAMC-variable - statistics-function 
|-- resources/                          # non-versioned resources
`-- tests/                              # test suite
```

## Variable's Statistics - Functions

This section describes the conventions for adding new variable statistics functions to `pypsa_validation_processing/statistics_functions.py`.

### Naming Convention

Function names follow the IAMC variable name with these substitutions:

- Each `|` (pipe / hierarchy separator) is replaced by `__` (double underscore).
- Spaces are replaced by `_` (single underscore)
- Other special characters are fully removed.

Examples:

| IAMC Variable | Function Name |
|---|---|
| `Final Energy [by Carrier]\|Electricity` | `Final_Energy_by_Carrier__Electricity` |
| `Final Energy [by Sector]\|Transportation` | `Final_Energy_by_Sector__Transportation` |

### Function Signature (fixed)

Every function receives exactly one argument – a single `pypsa.Network` object representing one investment year – and returns a `pandas.Series`:

```python
def <function_name>(n: pypsa.Network) -> pd.Series:
    ...
```

**The returned `Series` is of the structure of the direct outcome of a `pypsa.statistics` - Function.** It therefore must have a multi-level index that includes a level named `"unit"` and `"variable"`, so that the post-processing step can extract the unit information. It is possible to return multiple values with different units. Units are then converted to IAMC-valid units and summed over. Do not mix energy- and emissions- units in one statement!

#### Example output

- statistics-statement, grouped by country and unit:
```python
n.statistics.energy_balance(
    carrier = ["land transport EV", "land transport fuel cell", "kerosene for aviation", "shipping methanol"],
    components = "Load",
    groupby = ["carrier", "unit", "country"],
    direction = "withdrawal"
).groupby(["country", "unit"]).sum()
```

- returns a processable `pd.Series`:
```
country  unit
AL       MWh_LHV    1.073021e+06
         MWh_el     1.996662e+06
AT       MWh_LHV    1.319779e+07
         MWh_el     2.105799e+07
BA       MWh_LHV    3.214431e+05
                        ...
SI       MWh_el     5.576678e+06
SK       MWh_LHV    1.185324e+06
         MWh_el     8.633450e+06
XK       MWh_LHV    8.771836e+04
         MWh_el     1.081549e+06
Length: 68, dtype: float64
```

### Mapping File

`configs/mapping.default.yaml` maps each IAMC variable name to the corresponding function name in `statistics_functions.py`:

```yaml
Final Energy [by Carrier]|Electricity: Final_Energy_by_Carrier__Electricity
Final Energy [by Sector]|Transportation: Final_Energy_by_Sector__Transportation
```

At runtime, `Network_Processor` reads this mapping, looks up the function for each defined variable, and calls it for every network in the collection.  Variables without a mapping entry are silently skipped. 

### Register statistics for a new variable
To register a new variable
- add an entry to the mapping file
- implement the corresponding function
- add a corresponding test-function
- make shure, that the introduces variable is also part of your variable set to be executed.