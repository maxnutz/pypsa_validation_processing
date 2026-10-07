# Configuration

Status: draft

The package config is a YAML file passed via `--config <path>`; without `--config`, `pypsa_validation_processing/configs/config.default.yaml` is used and a `WARNING` is logged (`workflow.py::resolve_config_path`). Validation rules and errors: [contracts.md](contracts.md) C1.

"Packaged config" below means the value in `configs/config.default.yaml`; "Default" means the value used when the key is absent. Both can differ.

## Keys

| Key | Type | Required | Default | Allowed values | Effect | Error on invalid |
|---|---|---|---|---|---|---|
| `network_results_path` | path (string) | yes | – | existing directory | Results folder (C2). | missing or wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `definitions_path` | path (string) or `false` | yes | – | existing directory in IAMC-valid definitions format, or `false` / `"false"` (case-insensitive) | Folder → variables from definitions + unit conversion; `false` → all mapping variables, no conversion (C3). | missing/empty or wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `country` | string | yes | – | ISO 3166-1 alpha-2 code, incl. all 27 EU member states (e.g. `AT`, `DE`, `GR`) and non-EU codes (e.g. `CH`, `"NO"`, `GB`), or `all` | Selects locations and output granularity (C8); part of output names (C10). | `ValueError` (SC-3, SC-19, OQ-4, OQ-11) |
| `model_name` | string | yes | – | non-empty string | IAMC `model`; part of output names. | `ValueError` (SC-4, SC-19) |
| `scenario_name` | string | yes | – | non-empty string | IAMC `scenario`; part of output names. | `ValueError` (SC-4, SC-19) |
| `convert_units` | bool | no | `true` | `true`, `false` | Convert to definition units (C9). Without effect if `definitions_path: false`. | `ValueError` (SC-5) |
| `mapping_path` | path (string) | no | `pypsa_validation_processing/configs/mapping.default.yaml` | existing YAML file | Variable → function mapping (C4). | wrong type: `ValueError`; not existing: `FileNotFoundError` |
| `output_path` | path (string) | no | `resources` (repository-root `resources/` directory) | directory path | Directory for output files (C10); created if missing. | wrong type: `ValueError` |
| `aggregation_level` | string | no | `"country"` | `"country"`, `"region"` | Output granularity (C8). | `ValueError` |
| `aggregate_per_year` | bool | no | `true` | `true`, `false` | `true`: one value per investment year; `false`: full time series per investment year (C6, C10). | `ValueError` |
| `map_country_codes_to_names` | bool | no | `false` | `true`, `false` | Map region labels via `utils.REGION_MAPPING` (e.g. `AT` → `Austria`) (C8). | `ValueError` (SC-2) |

Every key whose value has the wrong data type MUST make `Network_Processor` fail with `ValueError` (C1.4). All keys marked "no" are optional; a config with only the five required keys is valid (C1.3, checked against the code on 2026-10-07).

Sources: `class_definitions.py::Network_Processor.__init__` (l.165-279); `configs/config.default.yaml`; `configs/config.{country,region}-{year,timeseries}.yaml`; `README.md` "Set the config parameters"; owner decisions in the kick-off (`output_path`, `map_country_codes_to_names`, `country`) and kick-off review (`output_path` = repository-root `resources/`).

## Notes per key

### `network_results_path`
Expected structure: `networks/*.nc` (required), `configs/config*<year>.yaml` (optional), `resources/energy_totals.csv` (optional); see C2. Example: `resources/AT_KN2040/`. `resources/AT_KN2040_1H/` (used by `config.region-timeseries.yaml`) has no `configs/` folder, so `config=None` is passed for every year in that setup.

### `definitions_path`
Default choice and packaged config: `sister_packages/energy-scenarios-at-workflow/definitions` (the common definitions). Any other `definitions/` folder MAY be set, as long as it is a valid IAMC variable definition readable by `nomenclature.DataStructureDefinition` (owner decision, kick-off review). The key is required even when definitions are not used: then it MUST be set to `false` explicitly.

### `country`
`all` keeps every country (or region) of the network. A specific code selects all locations whose label starts with that code (C8). Packaged config: `all`.

YAML 1.1 (`yaml.safe_load`) parses some unquoted codes as non-strings: `country: NO` becomes boolean `false` (checked 2026-10-07). Such codes MUST be quoted (`country: "NO"`); an unquoted one is rejected as a wrong type (C1.4).

### `convert_units`
Only `config.default.yaml`, `config.country-timeseries.yaml` and `config.region-timeseries.yaml` set it (`true`); the other example configs rely on the default.

### `mapping_path`
Packaged config: commented out (default applies). Alternative packaged mapping: `configs/mapping.prices_ie.yaml`.

### `output_path`
Always a directory, never a file name; file names are built per C10. Default: the `resources/` directory at the repository root, i.e. the relative path `resources` resolved against the working directory (A-1). Packaged config: `resources`; example configs: `outputs`. (SC-1)

### `aggregation_level`
Default `"country"`; the packaged config sets `"region"`. This is not a conflict: the default applies only when the key is absent.

### `aggregate_per_year`
Packaged config: `true`. `false` switches statistics functions to time series output and produces one file per investment year.

### `map_country_codes_to_names`
Default `false` (owner decision). Region labels without an entry in `REGION_MAPPING` are kept. The common region definitions (`sister_packages/energy-scenarios-at-workflow/definitions/region/common.yaml`) currently list only `Austria`; see OQ-2.

## Unknown keys
> **Open question:** Keys not listed above are currently ignored silently. Per P5 ("loud") they SHOULD probably be logged as `WARNING` (typo protection). See OQ-10.

## CLI options (not config keys)
| Option | Default | Allowed | Effect | Source |
|---|---|---|---|---|
| `--config` | packaged `config.default.yaml` | path | Package config; `~` expanded, made absolute. | `workflow.py::build_parser`, `resolve_config_path` |
| `--log-level` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Root logging level. | `workflow.py::build_parser`, `utils.setup_logging` |
