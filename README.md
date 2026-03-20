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

## Variable Statistics

This section describes the conventions for adding new variable statistics functions to `pypsa_validation_processing/statistics_functions.py`.

### Naming Convention

Function names follow the IAMC variable name with these substitutions:

- Each `|` (pipe / hierarchy separator) is replaced by `__` (double underscore).
- Spaces are replaced by `_` (single underscore).

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

The returned `Series` must have a **multi-level index** that includes a level named `"unit"` (e.g. `"MWh"`, `"MW"`) so that the post-processing step can extract the unit information.

### Output Structure (fixed)

The `Series` returned by each function is post-processed by `Network_Processor._postprocess_statistics_result()` into a long-format `pandas.DataFrame` with the columns `variable`, `unit`, and `value`.  The investment year is added as a separate column by the calling code in `calculate_variables_values()`.

A minimal example of the expected output:

```python
import pandas as pd

index = pd.MultiIndex.from_tuples([("MWh",)], names=["unit"])
result = pd.Series([1234.5], index=index)
```

### Role of the Mapping File

`configs/mapping.default.yaml` maps each IAMC variable name to the corresponding function name in `statistics_functions.py`:

```yaml
Final Energy [by Carrier]|Electricity: Final_Energy_by_Carrier__Electricity
Final Energy [by Sector]|Transportation: Final_Energy_by_Sector__Transportation
```

At runtime, `Network_Processor` reads this mapping, looks up the function for each defined variable, and calls it for every network in the collection.  Variables without a mapping entry are silently skipped.  To register a new variable, add an entry to the mapping file and implement the corresponding function.