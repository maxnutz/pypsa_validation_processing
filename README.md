![Python](https://img.shields.io/badge/python-3.11-blue)  [![license](https://img.shields.io/badge/License-MIT-blue)](https://github.com/maxnutz/pypsa_validation_processing/blob/master/LICENSE) [![pyam](https://img.shields.io/badge/pyam-iamc-blue)](https://github.com/IAMconsortium/pyam) [![Tests](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml/badge.svg)](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml)

# PyPSA-network processing for validation
This repository is licensed under the [MIT License](https://github.com/maxnutz/pypsa_validation_processing/blob/main/LICENSE)

> [!NOTE]  
> This package is currently in an **early state of development**. Expect ongoing changes and updates. Documentation and Readme will be continuously updated with changes.

This package processes a PyPSA `NetworkCollection` for a given set of IAMC variable definitions and computes mapped PyPSA statistics per variable. The workflow returns IAMC-structured outputs for validation against the Eurostat Energy Balance and supports:
- investment-year aggregates (`aggregate_per_year: true`) and full time series exports (`aggregate_per_year: false`)
- region-level and country-level aggregation (`aggregation_level`)
- single-country runs (`country: AT`) and all-country processing (`country: all`)
- optional mapping of country/region codes to readable names (`map_country_codes_to_names`)
- optional conversion to units defined in the definitions folder (`convert_units`)

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
### Set the config parameters
The file `config.default.yaml` provides a guideline for the two config sections and current defaults:
```yaml
# General section
country: AT               # ISO 3166-1 alpha-2 country code (e.g. AT) or "all"
definitions_path: sister_packages/energy-scenarios-at-workflow/definitions      # path to the IAMC variable definitions folder
convert_units: true       # convert output units to units from definitions_path
# mapping_path:        # optional: path to mapping YAML; defaults to configs/mapping.default.yaml
output_path: resources            # path the outputfile should be written to
aggregation_level: "region"      # Options: "country" or "region"
aggregate_per_year: true          # true: one value per investment year; false: full time series per year
map_country_codes_to_names: true # true: map codes to names (AT -> Austria), false: keep codes

# Network
network_results_path: resources/AT_KN2040/ # path to the folder containing PyPSA network results
model_name: pypsa-at            # name of the PyPSA model
scenario_name: KN2040test        # name of the PyPSA scenario
```
Personalized config files can be specified with `--config <path-to-config-file>`.

### Run the workflow
Run the workflow with 
```bash
pixi run workflow
```
This statement runs `"python workflow.py"` and uses the packaged default config if no `--config` is given.

You can also run:
```bash
pixi run python workflow.py --config /absolute/path/to/config.yaml
```
### Run tests
Run tests with
```bash
pixi run test
```
This statement runs `"pytest tests/ -v"` 

### Output behavior

- `aggregate_per_year: true` writes one xlsx file.
- `aggregate_per_year: false` writes one folder with one xlsx file per investment year.
- Generated output file and folder names are sanitized (whitespace collapsed to `_`).
- Time-like columns are normalized to timezone-aware timestamps using a fixed `+01:00` offset before `pyam.IamDataFrame` creation.

## Project structure

```text
pypsa_validation_processing/
|-- workflow.py                         # CLI/entry script
|-- pypsa_validation_processing/
|   |-- __init__.py
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

**Each function in ``statistic_functions.py`` corresponds to one IAMC variable and extracts the relevant value from a given PyPSA Network.  The functions are looked up by name via the mapping defined in ``configs/mapping.default.yaml``.**

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

For statistics-functions, the fixed input is `n = pypsa.Network` (one network / investment year) and `aggregate_per_year: bool = True` to switch between yearly aggregation and full snapshot time series.

Each function therefore follows this signature:

```python
def <function_name>(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    <config: dict>,
) -> pd.Series | pd.DataFrame:
    ...
```

If a variable-specific function needs additional settings, an optional `config: dict` argument can be added and is passed automatically by the processor when present.

Return format rules:

- `aggregate_per_year=True`: return a `pandas.Series`
- `aggregate_per_year=False`: return a `pandas.DataFrame` with snapshots as columns
- In both cases, index levels must include at least `location` and `unit`

Post-processing behavior:

- The post-processing step extracts and maps units to IAMC-valid units and sums values where needed. Do not mix energy and emissions units in one statement.
- Depending on config value `aggregation_level`, post-processing groups to country level (`country`) or keeps regional granularity (`region`).

#### Example output

- Example statistics statement, grouped by location and unit:
```python
n.statistics.energy_balance(
    carrier = ["land transport EV", "land transport fuel cell", "kerosene for aviation", "shipping methanol"],
    components = "Load",
    groupby = ["carrier", "unit", "location"],
    direction = "withdrawal"
).groupby(["location", "unit"]).sum()
```

- Returns a processable `pd.Series`:
```
location  unit
AT1       MWh_LHV    4.073021e+06
          MWh_el     6.996662e+06
AT2       MWh_LHV    5.319779e+06
          MWh_el     7.105799e+06
AT3       MWh_LHV    3.214431e+06
                        ...
AT3       MWh_el     5.576678e+06
Length: 6, dtype: float64
```

### Mapping File

`configs/mapping.default.yaml` maps each IAMC variable name to the corresponding function name in `statistics_functions.py`:

```yaml
Final Energy [by Carrier]|Electricity: Final_Energy_by_Carrier__Electricity
Final Energy [by Sector]|Transportation: Final_Energy_by_Sector__Transportation
Final Energy [by Sector]|Industry: Final_Energy_by_Sector__Industry
Final Energy [by Sector]|Agriculture: Final_Energy_by_Sector__Agriculture
```

At runtime, `Network_Processor` reads this mapping, looks up the function for each defined variable, and calls it for every network in the collection.  Variables without a mapping entry are silently skipped. 

### Register statistics for a new variable
To register a new variable, please first open a new Issue and select Issue Template "New Variable Statistics". In this issue, the following steps are prepared: 
- Create a new branch linked to the respective issue
- Write your pypsa-statistics and add it as a separate function to [statistics_functions.py](https://github.com/maxnutz/pypsa_validation_processing/blob/main/pypsa_validation_processing/statistics_functions.py) (please note the [naming and structural conventions](https://github.com/maxnutz/pypsa_validation_processing/tree/main#variables-statistics---functions)!)
- add a comprehensive docstring to your function 
- add the mapping variable_name <> function_name to [mapping.default.yaml](https://github.com/maxnutz/pypsa_validation_processing/blob/main/pypsa_validation_processing/configs/mapping.default.yaml) (and your personal mapping-file)
- Add a testing routine for your Function to `tests/` - stick to the [testing-README](https://github.com/maxnutz/pypsa_validation_processing/blob/main/tests/README.md)
- make sure, that the newest version of main is merged into your feature Branch 
- open a pull request and assign @maxnutz as reviewer
