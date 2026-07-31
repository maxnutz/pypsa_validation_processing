# Contributing

## Project Context

This package computes IAMC variables from PyPSA network results and is part of the PyPSA-AT project (PyPSA-AT – a nationally tailored, fully sector-coupled energy system model for Austria). The initial set of IAMC variables is defined in [energy-scenarios-at-workflow](https://github.com/iiasa/energy-scenarios-at-workflow).

## Code Style

- Python ≥ 3.12; type hints are required in all function signatures.
- Docstrings follow the NumPy style (no type hints in docstrings — they belong in the signature).
- Format code with `pixi run black .` before opening a pull request.

## Function Architecture

- **Statistics functions** in `pypsa_validation_processing/statistics_functions.py` are independent: each corresponds to one IAMC variable and must never import or call another statistics function.
- Statistics functions may only rely on helpers in `pypsa_validation_processing/utils.py` for shared logic.
- **Helpers** in `utils.py` may call other `utils.py` helpers, but must never call statistics functions.

## Statistics-Function Conventions

### Naming convention

Function names follow the IAMC variable name with these substitutions:

- Each `|` (pipe / hierarchy separator) is replaced by `__` (double underscore).
- Spaces are replaced by `_` (single underscore).
- Other special characters are removed.

| IAMC Variable | Function Name |
|---|---|
| `Final Energy [by Carrier]\|Electricity` | `Final_Energy_by_Carrier__Electricity` |
| `Final Energy [by Sector]\|Transportation` | `Final_Energy_by_Sector__Transportation` |

### Fixed signature

Every statistics function takes `n: pypsa.Network` (one network / investment year) and `aggregate_per_year: bool = True`:

```python
def <function_name>(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    <config: dict>,
) -> pd.Series | pd.DataFrame:
    ...
```

Additional optional parameters can be added when a variable needs them, e.g. `config: dict` or `energy_totals: Path`. All class-Variables can be used as parameters. Additional parameters are identified automatically when processing the statistics-function.

### Return format

- `aggregate_per_year=True` → return a `pandas.Series`.
- `aggregate_per_year=False` → return a `pandas.DataFrame` with snapshots as columns.
- In both cases, the index must include at least the `location` and `unit` levels.

### Mapping file

`configs/mapping.default.yaml` maps each IAMC variable name to its corresponding function name in `statistics_functions.py`. At runtime, `Network_Processor` looks up the function for each defined variable via this mapping. Variables without a mapping entry are silently skipped.

## Logging

- Use the standard library `logging` module.
- Each module gets its own `logger = logging.getLogger(__name__)` near the top of the file.
- `pypsa_validation_processing/workflow.py::main()` configures logging once via `utils.setup_logging()`; statistics functions and helpers must not call it themselves.

## Testing

- Tests live only in `tests/` — see the [testing README](https://github.com/maxnutz/pypsa_validation_processing/blob/main/tests/README.md).
- Write unit tests that test small, isolated logic.
- Every test for a function in `statistics_functions.py` must assert the output format: a `pandas.Series` with a MultiIndex containing at least `country` and `unit` (it can include more levels).

## Contribution Workflow

1. Open a new issue and select the "New Variable Statistics" issue template (for new IAMC variables) or describe the change you're proposing.
2. Create a branch linked to the issue.
3. Implement the change, following the conventions above.
4. Add or update tests in `tests/`.
5. Make sure `pixi run test` and `pixi run workflow_test` pass, and that there is no leftover debug code, commented-out blocks, or TODO stubs.
6. Merge the newest `main` into your feature branch.
7. Open a pull request and assign [@maxnutz](https://github.com/maxnutz) as reviewer.
