# Configuration

Status: reviewed

The package config is a YAML file passed via `--config <path>`; without `--config`, `pypsa_validation_processing/configs/config.default.yaml` is used and a `WARNING` is logged (`workflow.py::resolve_config_path`). Validation rules and errors: [contracts.md](contracts.md) C1.

"Packaged config" below means the value in `configs/config.default.yaml`; "Default" means the value used when an optional key is absent or `null` (C1.4). Both can differ.

`configs/config.default.yaml` is the only versioned config. The test configs used by `pixi run workflow_test` are local files only (section "Test configs"; #129). They replace the earlier example configs `configs/config.{country,region}-{year,timeseries}.yaml`, which are removed: they are no longer needed (owner, PR #142 review 2026-11-04).

## Keys

| Key | Type | Required | Default | Allowed values | Effect | Error on invalid |
|---|---|---|---|---|---|---|
| `network_results_path` | path (string) | yes | – | existing directory | Results folder (C2). | missing or wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `definitions_path` | path (string) or `false` | yes | – | existing directory in IAMC-valid definitions format, or `false` / `"false"` (case-insensitive) | Folder → variables from definitions + unit conversion; `false` → all mapping variables, no conversion (C3). | missing/empty or wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `country` | string | yes | – | ISO 3166-1 alpha-2 code or `XK` (pypsa-eur notation, OQ-4), incl. all 27 EU member states (e.g. `AT`, `DE`, `GR`) and non-EU codes (e.g. `CH`, `"NO"`, `GB`), `EU` (European Union = the 27 member states, C8.8), or `all` | Selects locations and output granularity (C8); part of output names (C10). | `ValueError` (SC-3, SC-19, OQ-4, OQ-11) |
| `model_name` | string | yes | – | non-empty string | IAMC `model`; part of output names. | `ValueError` (SC-4, SC-19) |
| `scenario_name` | string | yes | – | non-empty string | IAMC `scenario`; part of output names. | `ValueError` (SC-4, SC-19) |
| `convert_units` | bool | no | `true` | `true`, `false` | Convert to definition units (C9). Without effect if `definitions_path: false`. | `ValueError` (SC-5) |
| `mapping_path` | path (string) | no | `pypsa_validation_processing/configs/mapping.default.yaml` | existing YAML file | Variable → function mapping (C4). | wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `output_path` | path (string) | no | `resources` (repository-root `resources/` directory) | directory path | Directory for output files (C10); created if missing. | wrong type: `ValueError` |
| `aggregation_level` | string | no | `"country"` | `"country"`, `"region"` | Output granularity (C8). | `ValueError` |
| `aggregate_per_year` | bool | no | `true` | `true`, `false` | `true`: one value per investment year; `false`: full time series per investment year (C6, C10). | `ValueError` |
| `map_country_codes_to_names` | bool | no | `false` | `true`, `false` | Map region labels via `utils.REGION_MAPPING` (e.g. `AT` → `Austria`) (C8). | `ValueError` (SC-2) |
| `industry_non_energy_shares_path` | path (string) | no | – (not set) | CSV file written by `eurostat-energy-balance_processing` | Eurostat fallback for industrial non-energy use (C2.5, D5). An empty value (`null`) or an empty or whitespace-only string means "not set". Not set, not existing or not readable → variables needing it are skipped with `WARNING`. | wrong type: `ValueError`; unreadable file: `WARNING`, skip (C2.5); invalid content: `ValueError` (C2.5) |
| `industry_non_energy_shares_year` | `latest` or int | no | `latest` | `latest`, a year present in the shares file | Year of the Eurostat shares (C2.5): `latest` = latest year per country and carrier; a year = rows of that year only. Empty value (`null`) = `latest`. Checked and used only if the shares file is read; ignored otherwise, also with a wrong type (C2.5). | only if the file is read: wrong type: `ValueError`; year not in the file: `ValueError` (C2.5) |

Every key whose value has the wrong data type MUST make `Network_Processor` fail with `ValueError` (C1.4). `null` (empty value) is not a wrong type for an optional key: it means "not set" and the default applies, for every optional key (owner, PR #127 review 2026-11-03, OQ-30). Implemented in PR #139 (SC-44 resolved). All keys marked "no" are optional; a config with only the five required keys is valid (C1.3, checked against the code on 2026-10-07).

Sources: `class_definitions.py::Network_Processor.__init__`, `_validate_config` (PR #122, PR #139); `configs/config.default.yaml`; local test configs (section "Test configs", not versioned); `README.md` "Set the config parameters"; owner decisions in the kick-off (`output_path`, `map_country_codes_to_names`, `country`) and kick-off review (`output_path` = repository-root `resources/`).

## Notes per key

### `network_results_path`
Expected structure: `networks/*.nc` (required), `configs/config*<year>.yaml` (optional), `resources/energy_totals.csv` (optional); see C2. The config and the energy totals are taken from `n.meta` if the networks carry them; the files are only the fallback (C2.3, C2.4). Example: `resources/electricity_network_0p3/` (test configs). `resources/AT_KN2040_1H/` has no `configs/` folder; its networks carry the config in `n.meta`.

### `definitions_path`
Default choice and packaged config: `sister_packages/energy-scenarios-at-workflow/definitions` (the common definitions). Any other `definitions/` folder MAY be set, as long as it is a valid IAMC variable definition readable by `nomenclature.DataStructureDefinition` (owner decision, kick-off review). The key is required even when definitions are not used: then it MUST be set to `false` explicitly.

### `country`
`all` keeps every country (or region) of the network. A specific code selects all locations whose label starts with that code (C8). Packaged config: `all`. `EU` selects the locations of the 27 EU member states, not the copperplate pseudo-location `EU` of the networks, which is never part of the output (C8.7, C8.8).

YAML 1.1 (`yaml.safe_load`) parses some unquoted codes as non-strings: `country: NO` becomes boolean `false` (checked 2026-10-07). Such codes MUST be quoted (`country: "NO"`); an unquoted one is rejected as a wrong type (C1.4).

Codes are case-sensitive; lower-case codes are rejected (owner, PR #127 review 2026-11-03, OQ-31). `country` uses the pypsa-eur notation (owner, 2026-11-03, OQ-4): ISO 3166-1 alpha-2 codes plus `XK` (Kosovo), `EU` and `all`. `GR` and `GB` are the codes for Greece and the United Kingdom (OQ-11); `EL`, `UK`, `GB0`, `GB1` are rejected. `country: XK` with `aggregation_level: country` gives one row `XK`. Implemented in PR #139 (SC-45 resolved).

### `convert_units`
`config.default.yaml` sets it (`true`). Test configs: see section "Test configs".

### `mapping_path`
Packaged config: commented out (default applies). The repository contains only `configs/mapping.default.yaml`; further mapping files in `configs/` (e.g. a local `mapping.prices_ie.yaml`) are not versioned (`.gitignore` l.76 ignores `pypsa_validation_processing/configs/*`).

### `output_path`
Always a directory, never a file name; file names are built per C10. Default: the `resources/` directory at the repository root, i.e. the relative path `resources` resolved against the working directory (A-1). Packaged config: `resources`; test configs: `outputs/test`. (SC-1)

### `aggregation_level`
Default `"country"`; the packaged config sets `"region"`. This is not a conflict: the default applies only when the key is absent.

### `aggregate_per_year`
Packaged config: `true`. `false` switches statistics functions to time series output and produces one file per investment year.

### `map_country_codes_to_names`
Default `false` (owner decision). Region labels without an entry in `REGION_MAPPING` are kept. The common region definitions (`sister_packages/energy-scenarios-at-workflow/definitions/region/common.yaml`) currently list only `Austria`; see OQ-2.

### `industry_non_energy_shares_path`
Produced by `pixi run python workflow.py` in `eurostat-energy-balance_processing` (default output `resources/industry_non_energy_shares_<publication_year>.csv` there; maxnutz/eurostat-energy-balance_processing#8). The file is the interface between the two repositories; this package does not import the other one. Only used while the networks carry no industry production data (C2.5).

### `industry_non_energy_shares_year`
Owner decision 2026-10-29 (resolves A-6). `latest` uses the newest data per country, even if years differ between countries. A fixed year makes all countries use the same Eurostat year, e.g. `2020` when a network for 2020 is evaluated against the 2020 energy balance.

## Test configs
Owner decisions: #129 and PR #127 review (2026-11-03); location and versioning 2026-11-04.

`pixi run workflow_test` runs the workflow once per test config below, then `pytest tests/ -v`. The task fails if one run exits with an error. The test configs exercise the full workflow on a real network with every important combination of keys; they do not replace the unit tests.

**Location.** `pypsa_validation_processing/configs/test/<setup>.yaml`, one file per setup, file name = setup name. Not versioned: `.gitignore` l.76 ignores `pypsa_validation_processing/configs/*`. Every maintainer creates them locally from this section, so this section is the only shared definition of the setups.

**Local data (preconditions).** Not part of the repository:
- `resources/electricity_network_0p3/`: PyPSA-AT run `AT_KN2040` (measured 2026-11-04): networks `base_s_adm__none_{2025,2030,2040,2050}.nc`, 365 snapshots with weighting 24 h, 77 locations (35 Austrian NUTS3 regions `AT111`…`AT342`, `DE1`…`DE5`, `GB0`, `GB1`, `CH`, `XK`, the copperplate `EU` and further European countries). `n.meta` holds the run config, `wildcards.planning_horizons` and `resources.energy_totals`; `configs/config.base_s_adm__none_<year>.yaml` and `resources/energy_totals.csv` exist as well.
- The industry non-energy shares file of `eurostat-energy-balance_processing`, `../eurostat-energy-balance_processing/resources/industry_non_energy_shares_2026.csv` (relative to the repository root; carriers `Coal`, `Natural Gas`, `Oil`; years up to 2024, incl. 2020).

**Keys common to all setups.** `network_results_path: resources/electricity_network_0p3`; `model_name: "PyPSA-AT electricity_network_0p3"`; `scenario_name: <setup>`; `output_path: outputs/test`. Exception: `minimal` sets only the five required keys.

| Setup | `aggregation_level` | `aggregate_per_year` | `country` | `definitions_path` | `convert_units` | `map_country_codes_to_names` | `industry_non_energy_shares_path` | `industry_non_energy_shares_year` | Covers |
|---|---|---|---|---|---|---|---|---|---|
| `country-year-all` | `country` | `true` | `all` | common definitions | `true` | `false` | shares file | `latest` | baseline; one row per country incl. `XK`, `CH`, `GB` (C8); D5 mean for `CH` |
| `country-timeseries-AT` | `country` | `false` | `AT` | common definitions | `true` | `false` | shares file | `latest` | time series output, one file per year, timestamps (C10.5) |
| `country-year-EU` | `country` | `true` | `EU` | common definitions | `true` | `true` | shares file | `latest` | `EU` = 27 member states, copperplate `EU` dropped (C8.7, C8.8); label `European Union` |
| `region-year-AT` | `region` | `true` | `AT` | common definitions | `false` | `true` | shares file | `2020` | NUTS3 regions with names (`REGION_MAPPING`); no unit conversion; fixed shares year |
| `region-timeseries-all` | `region` | `false` | `all` | `false` | – (no effect) | `false` | shares file | `latest` | every mapped variable without definitions (C3); all regions as time series |
| `minimal` | – (`country`) | – (`true`) | `AT` | common definitions | – (`true`) | – (`false`) | – (not set) | – | only the five required keys, defaults apply (C1.3); output in `resources/` (C10-AC1); variables needing the shares file skipped (C2.5) |

"Common definitions" = `sister_packages/energy-scenarios-at-workflow/definitions`. "–" = key absent; the default is in brackets.

**Acceptance criteria**
- CT-AC1: Each setup exits without error and writes its output per C10: a yearly file (`aggregate_per_year: true`) or a time series folder with one file per investment year 2025, 2030, 2040, 2050.
- CT-AC2: The outputs of all setups contain the configured model and scenario and no region for the copperplate `EU`.
- CT-AC3: `minimal` logs one `WARNING` that the shares file is not set, if a mapped function declares `industry_non_energy_shares` (C2.5, C2-AC8); its other variables are written.
- CT-AC4: `pixi run workflow_test` runs exactly the setups of this section, then `pytest tests/ -v`.
- CT-AC5: The earlier example configs `configs/config.{country,region}-{year,timeseries}.yaml` are removed; no task, document or test refers to them (owner, PR #142 review 2026-11-04).

Not covered by the test configs (covered by unit tests in `tests/`): networks without `n.meta` (fallback to `configs/` and `energy_totals.csv`, C2.3, C2.4), invalid configs (C1), `null` for optional keys (C1.4), unreadable shares files (C2.5).

## Unknown keys
> **Open question:** Keys not listed above are currently ignored silently. Per P5 ("loud") they SHOULD probably be logged as `WARNING` (typo protection). See OQ-10.

## CLI options (not config keys)
| Option | Default | Allowed | Effect | Source |
|---|---|---|---|---|
| `--config` | packaged `config.default.yaml` | path | Package config; `~` expanded, made absolute. | `workflow.py::build_parser`, `resolve_config_path` |
| `--log-level` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Root logging level. | `workflow.py::build_parser`, `utils.setup_logging` |
