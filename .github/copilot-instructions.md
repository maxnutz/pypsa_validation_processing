# Copilot Instructions

## Project Overview
This repository implements a reusable Python module (`pypsa_validation_processing`) that:
- Takes a definitions folder holding IAMC-formatted variable definitions
- Executes the corresponding function (if available) to extract the value of the respective variable from a given PyPSA NetworkCollection
- Returns the results as a `pyam.IamDataFrame`

## Code Structure

```mermaid
classDiagram
    class workflow.py{
        config_path: pathlib.Path
        build_parser()
    }

    class statistics_functions.py{
        one function per variable
    }

    class utils.py{
        EU27_COUNTRY_CODES: dict
    }

    class mapping.yaml{
        mapping variables to function names
    }

    class config.yaml{
        user configuration
    }

    Network_Processor <-- workflow.py : executes
    statistics_functions.py <-- Network_Processor : executes
    utils.py <-- Network_Processor : imports
    mapping.yaml <|-- Network_Processor : includes
    config.yaml <|-- Network_Processor : includes

    class Network_Processor{
        config_path: pathlib.Path
        config: dict
        network_results_path: pathlib.Path
        definitions_path: pathlib.Path
        mappings_path: pathlib.Path
        country: str
        model_name: str
        scenario_name: str
        network_collection: pypsa.NetworkCollection
        dsd: nomenclature.DataStructureDefinition
        functions_dict: dict
        dsd_with_values: pyam.IamDataFrame | None
        path_dsd_with_values: pathlib.Path

        __init__()
        __repr__()
        _read_config()
        _read_mappings()
        _read_pypsa_network_collection()
        read_definitions()
        _execute_function_for_variable()
        _postprocess_statistics_result()
        structure_pyam_from_pandas()
        calculate_variables_values()
        write_output_to_xlsx()
    }
    note for Network_Processor "in class_definitions.py"
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
- For a pull-request: the user has to be reviewer of the pull request to give approval.

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

## Background Information
> [!WARNING]
> External documentation provides semantic guidance only. Local project conventions override external documentation.

- nomenclature-package: https://nomenclature-iamc.readthedocs.io/en/stable/
- pyam-package: https://pyam-iamc.readthedocs.io/en/stable/
- IAMC-format naming conventions: https://docs.ece.iiasa.ac.at/standards/variables.html
- pypsa StatisticsAccessor: https://docs.pypsa.org/latest/api/networks/statistics/#pypsa.Network.statistics
- pypsa Documentation: https://docs.pypsa.org/latest/

