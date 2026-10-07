# Open questions, assumptions and spec-vs-code differences

Status: draft

- **OQ-n:** open question, needs a decision by the owner.
- **SC-n:** observed difference between spec and code, documentation or project instructions. Candidate for a GitHub issue; the spec wins (P1).
- **A-n:** assumption made in the specs; to be confirmed.

Code references are to commit `1b38477` (branch base of `spec/kickoff-scaffold`).

## Open questions

| ID | Question | Context | Spec ref |
|---|---|---|---|
| OQ-1 | How should the domestic aviation/navigation share be determined for countries other than AT and for investment years other than 2020? | `utils.get_energy_totals_domestic_share` hardcodes `.loc["AT"]` and `year == 2020` (marked `# TODO generalize`) and returns one scalar for all locations. With `country: all` other countries get the AT share. | C2.4; future variable spec `Final_Energy_by_Sector__Transportation` |
| OQ-2 | Must output regions be valid regions of the common definitions? | `definitions/region/common.yaml` lists only `Austria`. The default output uses codes (`AT`, `AT1`, …), which are not in that list. The package never validates regions. Relevant for Scenario Explorer submissions (`docs/index.md`). | C8, C10; configuration `map_country_codes_to_names` |
| ~~OQ-3~~ | _Resolved (owner, kick-off review):_ an invalid result aborts the run; only a variable that cannot be run (missing function, missing special input data) is warned and skipped. | | P5, C6.7 |
| OQ-4 | Are identifiers that are not assigned ISO codes, such as `EU`, `GB0`, `GB1`, `XK`, or sub-country codes valid values for `country`? | `utils.EU27_COUNTRY_CODES` (used for validation) contains them. The spec allows only ISO 3166-1 alpha-2 codes and `all`. | C1.5 |
| OQ-5 | How should a 29 February snapshot be handled when the investment year is not a leap year? | `calculate_variables_values` uses `ts.replace(year=investment_year)`, which raises `ValueError` for 29 Feb → non-leap year. | C10.5 |
| OQ-6 | What happens to a function that declares `config` when no network config exists (`config=None`)? | The code passes `None` (warning logged). Per P5, a variable that cannot run because input data is missing is warned and skipped; open is whether a missing network config makes a variable unrunnable, or whether the function may handle `None`. `resources/AT_KN2040_1H/` has no `configs/` folder. | C2.3 |
| OQ-7 | Should mapping entries whose variable is missing from the definitions be reported? | Spec says SHOULD warn once at initialisation (P5). Example: `Prices\|Final Energy\|Electricity` in `mapping.prices_ie.yaml` is not in the definitions and is never evaluated when definitions are used. | C3.1 |
| OQ-8 | Is the yearly value always the snapshot-weighted sum of the time series? | Holds for energy flows; not for intensive quantities such as prices (`mapping.prices_ie.yaml`). C6-AC3 may need per-variable exceptions. | C6-AC3 |
| OQ-9 | What should happen if no location matches the configured `country`? | `_aggregate_to_country` / `_filter_to_regions` then return empty data without a message. Options: `ValueError` at initialisation (check `n.buses.location`), or `WARNING`. | C8.5 |
| OQ-10 | Should unknown config keys be reported? | Currently ignored silently; a typo (e.g. `convert_unit`) silently falls back to the default. | configuration.md "Unknown keys" |
| OQ-11 | Should `EL` (Eurostat code for Greece) be accepted as an alias of the ISO code `GR`? | The spec requires ISO 3166-1 alpha-2 codes for all EU member states (Greece = `GR`). Eurostat uses `EL`; the reference data from `eurostat-energy-balance_processing` may use it. | C1.6 |

## Spec-vs-code differences (GitHub issue candidates)

| ID | Spec says | Code / docs do | Source |
|---|---|---|---|
| SC-1 | `output_path` is always a directory; default is the repository-root `resources/` directory (relative path `resources`). | Default is built as a *file* path `pypsa_validation_processing/resources/PYPSA_<model>_<scenario>[_<country>].xlsx` (a folder that does not exist in the package), and `write_output_to_xlsx` appends the file name again. Tests pin the file-name behaviour (`tests/test_aggregation.py:216,246,272`). | `class_definitions.py` l.263-279, l.915-926 |
| SC-2 | `map_country_codes_to_names` defaults to `false`. | `__init__` defaults to `True` (l.251-253); test `test_map_country_codes_to_names_defaults_to_true` asserts `True` while its docstring says `False` (`tests/test_network_processor.py:855-865`). `config.default.yaml` sets `false`; `README.md` example sets `true`. | `class_definitions.py` l.251 |
| SC-3 | `country` accepts every ISO 3166-1 alpha-2 code or `all`. | `_is_valid_country_identifier` accepts only keys of `utils.EU27_COUNTRY_CODES`: 39 keys incl. non-EU codes (`CH`, `NO`, `GB`, …) and keys that are not assigned ISO 3166-1 alpha-2 codes (`EU`, `GB0`, `GB1`, `XK`), but not e.g. `IS`, `LI`, `UA`. The dict name suggests EU-27 only. | `class_definitions.py` l.295-297; `utils.py` l.7 |
| SC-4 | Missing/null `model_name` or `scenario_name` → `ValueError`. | Missing key → `KeyError` (`self.config["model_name"]`); only an explicit `null` reaches the `ValueError`; empty string is accepted. | `class_definitions.py` l.223-228 |
| SC-5 | `convert_units` must be a bool, else `ValueError`. | Not validated; any truthy value enables conversion. | `class_definitions.py` l.202 |
| SC-6 | Mapping validated at initialisation: missing file → `FileNotFoundError`, empty/invalid → `ValueError`, missing function → one `WARNING` at initialisation, variable skipped. | Missing function is detected only during evaluation and warned once per network (investment year); empty or non-mapping YAML is not checked. | `class_definitions.py` l.313-318, l.375-382 |
| SC-7 | Missing `energy_totals.csv` → one `WARNING` at initialisation; variables whose function declares `energy_totals` skipped with `WARNING`; others evaluated. | Existence not checked; the function fails inside `pd.read_csv` and the whole run aborts. The docstring of `Final_Energy_by_Sector__Transportation` claims `None` falls back to default shares, but `get_energy_totals_domestic_share(None, …)` cannot handle `None`. | `class_definitions.py` l.393-396; `statistics_functions.py` l.808-847; `utils.py` l.180-204 |
| SC-8 | Every result validated (type, `location`/`unit` levels, numeric, not empty, not all-NaN); violation → exception naming the variable. | Only the type for `aggregate_per_year=False` is checked (`RuntimeError`); for `True`, `.to_frame` is called without checks; empty/all-NaN results pass. | `class_definitions.py` l.849-856 |
| SC-9 | A unit not in `UNITS_MAPPING` → `ValueError`; no silent NaN. `UNITS_MAPPING` contains only units. | `_map_unit_level` uses `.map(UNITS_MAPPING)`; unknown units silently become NaN. `UNITS_MAPPING` contains the key `"land transport"`, which is a carrier, not a unit. | `class_definitions.py` l.482-492; `utils.py` l.124-132 |
| SC-10 | Unparsable list of definition units → `ValueError`. | Falls back to `"TJ"` with a warning. | `class_definitions.py` l.739-755 |
| SC-11 | Missing/empty `networks/` → `FileNotFoundError` at initialisation. Investment year from `n.meta["wildcards"]["planning_horizons"]`, else from the file name with `WARNING`; no year found or duplicate years → `ValueError`. | `os.listdir` raises an unspecific error for a missing folder; an empty folder is not handled. The investment year is read only from `n.meta` during evaluation; networks without `n.meta` (e.g. pypsa-eur) fail with `KeyError`; duplicates are not detected. | `class_definitions.py` l.320-324, l.836 |
| SC-12 | Python `>=3.11`; `pixi.toml` is authoritative and wins over `CLAUDE.md` (owner decision). | `CLAUDE.md` "Code Style" and `docs/contributing.md` state Python ≥ 3.12. `pixi.toml`, `pyproject.toml` and the `README.md` badge agree with the spec. | tech-stack.md |
| SC-13 | Every runtime dependency is declared in the environment. | `pypsa` is not in `pixi.toml`; it is only installed via the editable package (`pyproject.toml`). | `pixi.toml`, `pyproject.toml` |
| SC-14 | Implementation source rule P6: port pypsa-de logic where a matching variable exists; `pypsa.statistics` only otherwise. | `CLAUDE.md` "Blueprint": "use `pypsa.statistics` more extensively"; `sister_packages/CLAUDE.md` treats pypsa-de as "semantic map" only. Both should be aligned with P6. | `CLAUDE.md`; `sister_packages/CLAUDE.md` |
| SC-15 | Time series columns are UTC (`+00:00`). | Code uses UTC (`format_timestamps`, `fixed_tz` = +00:00); `README.md` "Output behavior" says fixed `+01:00`. | `class_definitions.py` l.52; `README.md` |
| SC-16 | Statistics-function results are Series/DataFrame per C6. | `tests/README.md` describes `TestFinalEnergyByCarrierElectricity` as "Validates return type (DataFrame)" with levels "country, unit", and lists a `TestEU27CountryCodes` class that does not exist (actual: `TestRegionsCodes`). | `tests/README.md`; `tests/test_utils.py` |
| SC-17 | Several matching network configs → first in lexicographic order, `WARNING`. | `glob.glob` order (not sorted), logged at `INFO`. | `class_definitions.py` l.777-789 |
| SC-19 | Every key with a wrong data type → `ValueError`; unquoted `country: NO` (parsed as `false`) is rejected with a hint to quote it. | Types of `network_results_path`, `definitions_path`, `country`, `model_name`, `scenario_name`, `mapping_path`, `output_path`, `aggregation_level` are not checked; `country: NO` gives the misleading message `got: False`. | `class_definitions.py` l.165-279 |
| SC-18 | All config validation before reading networks. | `aggregation_level`, `aggregate_per_year`, `map_country_codes_to_names` are validated after `_read_pypsa_network_collection` and `read_definitions`. | `class_definitions.py` l.234-258 |

## Assumptions

| ID | Assumption | Spec ref |
|---|---|---|
| A-1 | Relative paths in the package config (`network_results_path`, `definitions_path`, `mapping_path`, `output_path`) are resolved against the current working directory. `pixi run` tasks run from the repository root, so the default `output_path` `resources` is the repository-root `resources/` directory. For a `pip install`ed package run elsewhere, `resources/` is relative to that working directory. | C1.7, configuration.md |
| A-2 | Two networks with the same investment year are an error (the output has one column/file per year). | C2.2 |
| A-3 | Owner decision "missing `energy_totals.csv` → only a warning; other variables can succeed" is specified as: one `WARNING` at initialisation, and every variable whose function declares `energy_totals` is skipped with its own `WARNING`. | C2.4 |
