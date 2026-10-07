# Tech stack

Status: draft

Version constraints are taken from `pixi.toml` and `pyproject.toml`; locked versions from the committed `pixi.lock` (linux-64 / noarch / pure-Python wheels). Nothing here is a new requirement unless written with MUST/SHOULD.

## Language
| Item | Constraint | Locked | Source |
|---|---|---|---|
| Python | `>=3.11` | 3.14.3 | `pixi.toml` `[dependencies]`, `pyproject.toml` `requires-python`, `pixi.lock` |

> **Open question:** `CLAUDE.md` and `docs/contributing.md` require Python ≥ 3.12; `pixi.toml`, `pyproject.toml` and the `README.md` badge say 3.11. See [open_questions.md](../open_questions.md) SC-12.

## Environment
- Pixi workspace `pypsa-validation-processing`, channel `conda-forge`, platforms `linux-64`, `osx-arm64`, `osx-64`, `win-64` (`pixi.toml` `[workspace]`).
- Tasks (`pixi.toml` `[tasks]`):
  - `workflow`: `python workflow.py` (packaged default config).
  - `workflow_test`: runs the four `config.{country,region}-{year,timeseries}.yaml` setups, then `pytest tests/ -v`.
  - `test`: `pytest tests/ -v --cov=pypsa_validation_processing --cov-report=term-missing --cov-fail-under=90`.
- Package build: setuptools (`pyproject.toml` `[build-system]`); CLI entry point `pypsa-validation-processing = pypsa_validation_processing.workflow:main`.

## Runtime libraries
| Library | Constraint | Locked | Role in this package |
|---|---|---|---|
| `pypsa` | none (only `pyproject.toml` `dependencies`) | 1.1.2 | Reads networks as `pypsa.NetworkCollection`; `n.statistics` accessor is the main computation API of statistics functions; `n.meta` carries the investment year. |
| `pandas` | `>=1.0.0` | 2.3.3 | Internal data model: `pd.Series` / `pd.DataFrame` with MultiIndex (`location`, `unit`, …). |
| `pyam-iamc` | `>=2.0.0` | 3.2.0 | `pyam.IamDataFrame` as output structure; `convert_unit`; `to_excel`. |
| `nomenclature-iamc` | `>=0.29` | 0.29.4 | `nomenclature.DataStructureDefinition` reads variable/region definitions and their units. |
| `iam-units` | transitive | 2026.3.10 | Unit registry used by `pyam.IamDataFrame.convert_unit`. |
| `pint` | transitive | 0.25.3 | Unit handling behind `iam-units`. |
| `pyyaml` | `>=5.3` | 6.0.3 | Reads package config, mapping file and network configs (`yaml.safe_load`). |
| `openpyxl` | `>=3.0` | 3.1.5 | Excel engine for `IamDataFrame.to_excel`. |
| `numpy` | `>=1.18.0` | 2.4.3 | Numerical helper in statistics functions. |

> **Open question:** `pypsa` is not declared in `pixi.toml`; it enters only through the editable install of this package (`pyproject.toml`). See SC-13.

Which behaviour of each library the package relies on is specified in [contracts.md](../contracts.md) C11.

## Sister packages (read-only, `sister_packages/`)
| Package | Use | Source |
|---|---|---|
| `energy-scenarios-at-workflow` | IAMC variable and region definitions (`definitions/variable`, `definitions/region`). | `CLAUDE.md`; `sister_packages/CLAUDE.md` |
| `pypsa-de` | `scripts/pypsa-de/export_ariadne_variables.py`: primary implementation source for statistics functions ([principles.md](principles.md) P6). | `CLAUDE.md` "Blueprint"; `sister_packages/CLAUDE.md` |
| `eurostat-energy-balance_processing` | Produces the reference data this package's output is validated against. | `README.md` tip box |

## Testing
- `pytest` (`>=7.0`, locked 9.0.2), `pytest-cov` (`>=4.0`, locked 7.0.0), `pytest-mock` (`>=3.0`, locked 3.15.1).
- Coverage of `pypsa_validation_processing` MUST be ≥ 90 % (`pixi.toml` task `test`).
- Tests live only in `tests/`; statistics-function tests MUST check the output format of contract C6 (`CLAUDE.md`, "Testing Rules").

## Formatting
- Black (`>=26.5.1,<27`, locked 26.5.1), run via `pixi run black .` (`CLAUDE.md`, "Code Style").
- NumPy-style docstrings without types; type hints in all signatures (`CLAUDE.md`).

## Documentation
- mkdocs (`>=1.6`, locked 1.6.1), mkdocs-material (`>=9.5`, locked 9.7.6), mkdocstrings[python] (`>=0.26`, locked 1.0.4); config `mkdocs.yml`, sources `docs/`.
- New public functions in `utils.py`, `class_definitions.py`, `workflow.py` MUST be added to the `members:` allowlist in `docs/api/*.md` (`README.md`, "Documentation Pages").
