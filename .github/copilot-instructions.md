# Copilot Instructions

This repository is a Python package that computes IAMC variables from PyPSA network results and exports IAMC-formatted Excel outputs for validation workflows.

- Package manager/environment: Pixi (`pixi run ...`).
- Main run command: `pixi run workflow`.
- Test command: `pixi run test`.

## Key Implementation Notes
- Main class: `pypsa_validation_processing/class_definitions.py::Network_Processor`
- Workflow entrypoint: `pypsa_validation_processing/workflow.py`
- Root `workflow.py` is only a compatibility wrapper.
- Statistics functions are discovered dynamically from mapping names in `statistics_functions.py`.

### Aggregation behavior
- `aggregation_level: country`
  - `country: AT` -> sum AT* regions into one country row.
  - `country: all` -> sum per country prefix (`AT1 -> AT`, `DE2 -> DE`) and keep one row per country.
- `aggregation_level: region`
  - `country: AT` -> keep only matching AT* regions.
  - `country: all` -> keep all regions.

## Forbidden Actions
- Do NOT invent datasets, files, or APIs.
- Do NOT assume undocumented variables exist.
- Do NOT change any definitions in `definitions/`, or any statement in `configs/` unless explicitly asked for.
- Do NOT change folder structure unless explicitly requested.
- Do NOT change copilot-instructions.md unless explicitly requested.

## Testing Rules
- Add or update tests when behavior changes.
- Tests belong only in `/tests`.
- all testing routines `test_statistics_functions.py` for functions in `statistics_functions.py` must test the output-format. The outputformat MUST be a pandas.Series with Multiindex of ``country`` and ``unit``. It CAN include more levels in the Multiindex.

## Useful links
- Repository README: `README.md`
- IAMC naming conventions: https://docs.ece.iiasa.ac.at/standards/variables.html
- pyam docs: https://pyam-iamc.readthedocs.io/en/stable/
- nomenclature docs: https://nomenclature-iamc.readthedocs.io/en/stable/
- PyPSA statistics accessor docs: https://docs.pypsa.org/latest/api/networks/statistics/#pypsa.Network.statistics