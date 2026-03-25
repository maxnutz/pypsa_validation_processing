# Copilot Instructions

## Project Overview
This repository implements a reusable Python module (`pypsa_validation_processing`) that:
- Takes a definitions folder holding IAMC-formatted variable definitions
- Executes the corresponding function (if available) to extract the value of the respective variable from a given PyPSA NetworkCollection
- Saves the result as IAMC-formatted xlsx-file.

## Code Structure

```mermaid
classDiagram
    class Network_Processor {
        +path_config: pathlib_Path
        +config: dict
        +country: str
        +definition_path: pathlib_Path
        +mapping_path: pathlib_Path
        +output_path: pathlib_Path
        +network_results_path: pathlib_Path
        +model_name: str
        +scenario_name: str
        +network_collection: pypsa_NetworkCollection
        +dsd: nomenclature_DataStructureDefinition
        +functions_dict: dict
        +dsd_with_values: pyam_IamDataFrame
        +path_dsd_with_values: pathlib_Path
        +__init__(path_config: pathlib_Path)
        +_read_config() dict
        +_read_mappings() dict
        +_read_pypsa_network_collection() pypsa_NetworkCollection
        +read_definitions() nomenclature_DataStructureDefinition
        +_execute_function_for_variable(variable: str, n: pypsa_Network) pd_Series
        +_postprocess_statistics_result(variable: str, result: pd_Series) pd_DataFrame
        +structure_pyam_from_pandas(df: pd_DataFrame) pyam_IamDataFrame
        +calculate_variables_values() None
        +write_output_to_xlsx() None
    }

    class statistics_functions_py {
        +Final_Energy_by_Carrier__Electricity(n: pypsa_Network) pd_DataFrame
        +Final_Energy_by_Sector__Transportation(n: pypsa_Network) pd_DataFrame
    }

    class utils_py {
        +EU27_COUNTRY_CODES: dict~str,str~
        +UNITS_MAPPING: dict~str,str~
    }

    class config_default_yaml {
        +country: str
        +definitions_path: str
        +output_path: str
        +network_results_path: str
        +model_name: str
        +scenario_name: str
    }

    class mapping_default_yaml {
        +Final_Energy_by_Carrier__Electricity: str
        +Final_Energy_by_Sector__Transportation: str
    }

    class pypsa_NetworkCollection
    class pypsa_Network {
        +name: str
        +statistics: pypsa_StatisticsAccessor
    }
    class pypsa_StatisticsAccessor {
        +energy_balance(components: list, carrier: str, groupby: list) pd_Series
    }

    class nomenclature_DataStructureDefinition {
        +variable: pd_Series
    }

    class pyam_IamDataFrame
    class pd_DataFrame
    class pd_Series

    Network_Processor --> pypsa_NetworkCollection : owns
    Network_Processor --> nomenclature_DataStructureDefinition : uses
    Network_Processor --> pyam_IamDataFrame : creates
    Network_Processor --> statistics_functions_py : calls
    Network_Processor --> utils_py : imports
    Network_Processor --> config_default_yaml : reads
    Network_Processor --> mapping_default_yaml : reads
    pypsa_NetworkCollection --> pypsa_Network : contains
    pypsa_Network --> pypsa_StatisticsAccessor : has
```

## Folder Structure

```
.gitignore
|- .github
|  `- copilot-instructions.md
|- pixi.toml
|- pyproject.toml
|- pypsa_validation_processing
|  |- configs
|  |  |- config.default.yaml
|  |  `- mapping.default.yaml
|  |- class_definitions.py
|  |- statistics_functions.py
|  `- utils.py
|  `- workflow.py
|- workflow.py
|- resources
|- sister_packages
|- tests
|- README.md
`- LICENSE
```

## Key Conventions
- The main processing class `Network_Processor` lives in `pypsa_validation_processing/class_definitions.py`
- Statistics functions (one per IAMC variable) live in `pypsa_validation_processing/statistics_functions.py`
- `mapping.default.yaml` (or another mapping-file provided by the config-file) holds the mapping of IAMC variable to the respective function in `pypsa_validation_processing/statistics_functions.py`
- The package workflow entrypoint is `pypsa_validation_processing/workflow.py`; the root `workflow.py` is a thin compatibility wrapper
- Default configs are packaged inside `pypsa_validation_processing/configs/`
- Pixi is used as environment package manager. Use `pixi run` before your statement in cli to use the intended pixi-environment.
- The `resources/` directory holds non-versioned resources
- The `sister_packages/` directory holds related packages for background information
- The `tests/` directory holds unit and integration tests

## Task Completion Criteria
A task is complete when:
- Code runs without syntax errors.
- Tests pass or new tests are added and pass.
- New variables follow IAMC naming conventions.
- Changes are integrated into existing folder structure.
- A short summary of changes is provided.
- In chat mode: the user has reviewed the changes and given approval.
- For a pull-request: the user is reviewer of the pull request to give approval.

## Forbidden Actions
- Do NOT invent datasets, files, or APIs.
- Do NOT assume undocumented variables exist.
- Do NOT change any definitions in `definitions/`, or any statement in `configs/` unless explicitly asked for.
- Do NOT change folder structure unless explicitly requested.
- Do NOT change copilot-instructions.md unless explicitly requested.

## Testing Rules
- Add or update tests when behavior changes.
- Tests belong only in `/tests`.
- Prefer minimal unit tests over integration tests.
- all testing routines `test_statistics_functions.py` for functions in `statistics_functions.py` must test the output-format. The outputformat MUST be a pandas.Series with Multiindex of ``country`` and ``unit``. It CAN include more levels in the Multiindex.

## Background Information
> [!WARNING]
> External documentation provides semantic guidance only. Local project conventions override external documentation.

- nomenclature-package: https://nomenclature-iamc.readthedocs.io/en/stable/
- pyam-package: https://pyam-iamc.readthedocs.io/en/stable/
- IAMC-format naming conventions: https://docs.ece.iiasa.ac.at/standards/variables.html
- pypsa StatisticsAccessor: https://docs.pypsa.org/latest/api/networks/statistics/#pypsa.Network.statistics
- pypsa Documentation: https://docs.pypsa.org/latest/

