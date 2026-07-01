# CLAUDE.md

This repository is a Python package that computes IAMC variables from PyPSA network results and exports IAMC-formatted Excel outputs for validation workflows.

- Package manager/environment: Pixi (`pixi run ...`).
- Main run command: `pixi run workflow`.
- Test command: `pixi run test`.

## Project Context

You are working as a senior software engineer on the PyPSA-AT project. PyPSA is a Python framework for energy system modelling. PyPSA-AT is a nationally tailored, fully sector-coupled energy system model for Austria. This package (`pypsa_validation_processing`) derives pypsa-statistics for IAMC-variables.

- **Initial IAMC-variables:** [energy-scenarios-at-workflow](https://github.com/iiasa/energy-scenarios-at-workflow) defines the initial set of variables.

## Key Implementation Notes
- Main class: `pypsa_validation_processing/class_definitions.py::Network_Processor`
- Workflow entrypoint: `pypsa_validation_processing/workflow.py`
- Root `workflow.py` is only a compatibility wrapper.
- All Statistics-functions in `config/mapping.default.yaml` are executed.
- All Functions in `pypsa_validation_processing/statistics_functions.py` are stand-alone. They can only rely on helpers-functions in `pypsa_validation_processing/utils.py` for general tasks, that need execution in multiple functions.
- **Blueprint:** [export_ariadne_variables.py](https://github.com/PyPSA/pypsa-de/blob/main/scripts/pypsa-de/export_ariadne_variables.py) serves as blueprint for evaluations, but use `pypsa.statistics` more extensively.

### Aggregation behavior
- `aggregation_level: country`
  - `country: AT` -> sum AT* regions into one country row.
  - `country: all` -> sum per country prefix (`AT1 -> AT`, `DE2 -> DE`) and keep one row per country.
- `aggregation_level: region`
  - `country: AT` -> keep only matching AT* regions.
  - `country: all` -> keep all regions.

## Working Principles
Before writing any code:

1. Analyse — read relevant files, understand existing patterns
2. Propose architecture — explain the approach, wait for feedback
3. Break into small tasks — incremental, no big-bang changes
4. Write statistics-functions each independent from the others.
5. Touch only what's needed.
6. Code changes are in `pypsa_validation_processing/statistics_functions.py`, `pypsa_validation_processing/class_definitions.py`, `pypsa_validation_processing/utils.py`

### Local debugging
- locally, use the `pixi run workflow_test` for debugging. This statement includes all possible evaluation setups.
- Test if `pypsa.statistics`-function calls return values.
  - empty pd.DataFrame or pd.DataFrame with all NaN values are not valid.
  - empty pd.Series or pd.Series with all NaN values are not valid.

### Function Architecture (Critical)
- Statistics functions in `statistics_functions.py`: each is independent, can only call helpers from `utils.py`
- Helpers in `utils.py`: can call other `utils.py` functions, not statistics functions
- Return format: pandas.Series with MultiIndex containing at minimum (country, unit)
- **Practical example:** If you create `calculate_foo()` and `calculate_bar()`, they must never import or call each other. Shared logic goes into `utils.py`.

## Code Style
- Python ≥ 3.12; type hints in all function signatures
- Docstrings in NumPy style (no type hints in docstrings — they're in the signature)
- Black formatter for formatting (`pixi run black .`)

## Tone and Behavior
- Be direct. Skip "Great question!" and "I'd be happy to help!" — just help.
- Have opinions. If you see a better approach, say so and explain why.
- Flag uncertainty explicitly — don't guess on specifics silently.
- Prefer showing a concrete diff or code snippet over long prose explanations.

## Forbidden Actions
- Do NOT invent datasets, files, or APIs.
- Do NOT assume undocumented variables exist.
- Do NOT change any definitions in `definitions/`, or any statement in `configs/` unless explicitly asked for.
- Do NOT change folder structure unless explicitly requested.
- Do NOT change CLAUDE.md unless explicitly requested.

## Testing Rules
- Add or update tests only when behavior changes.
- Tests belong only in `/tests`.
- all testing routines `test_statistics_functions.py` for functions in `statistics_functions.py` must test the output-format. The outputformat MUST be a pandas.Series with Multiindex of ``country`` and ``unit``. It CAN include more levels in the Multiindex.

### Writing Tests
Tests live in `tests/`. Write **Unit tests** — test small isolated logic.

## PR Readiness Checklist
- [ ] `pixi run test` runs successfully
- [ ] for local jobs: `pixi run workflow_test` runs successfully
- [ ] PR description explains *what* changed and *why*
- [ ] No leftover debug code, commented-out blocks or TODO stubs

## Useful links
- Repository README: `README.md`
- sister-packages instructions: `sister_packages/CLAUDE.md`
- resources instructions: `resources/README.md`
- IAMC naming conventions: https://docs.ece.iiasa.ac.at/standards/variables.html
- pyam docs: https://pyam-iamc.readthedocs.io/en/stable/
- nomenclature docs: https://nomenclature-iamc.readthedocs.io/en/stable/
- PyPSA statistics accessor docs: https://docs.pypsa.org/latest/api/networks/statistics/#pypsa.Network.statistics

## Delegated coding tasks
For coding work delegated to a subagent (parallel or isolated-context work), a matching subagent is available at `.claude/agents/developer.md`. It follows the same conventions as this file.
