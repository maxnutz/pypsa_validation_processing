# Contracts

Status: draft

Contracts between the components of `pypsa_validation_processing`. Each contract lists the requirements, the sources it is based on, and acceptance criteria (AC) that can become unit tests in `tests/`. Spec-vs-code differences are referenced as `SC-n`, open questions as `OQ-n`, assumptions as `A-n` (all in [open_questions.md](open_questions.md)).

General rule for all contracts: [constitution/principles.md](constitution/principles.md) P5 "Fail early and loud".

---

## C1 Config → `Network_Processor`

**Requirements**
1. `Network_Processor(config_path)` MUST read the package config with `yaml.safe_load`. The keys, types, defaults and allowed values are specified in [configuration.md](configuration.md); that table is part of this contract.
2. Required keys: `network_results_path`, `definitions_path`, `country`, `model_name`, `scenario_name`. A missing, `null` or empty required key MUST raise `ValueError` naming the key and the config path. (SC-4)
3. All other keys (`convert_units`, `mapping_path`, `output_path`, `aggregation_level`, `aggregate_per_year`, `map_country_codes_to_names`) are optional: a config containing only the five required keys MUST initialise without error, and the defaults of [configuration.md](configuration.md) apply.
   > Checked against the code on 2026-10-07: `Network_Processor` initialises with only the five required keys, both with `definitions_path: false` and with a definitions folder. Two of the applied defaults differ from the spec (`map_country_codes_to_names`, `output_path`; SC-1, SC-2).
4. Every key, required or optional, whose value has the wrong data type MUST make `Network_Processor` fail with `ValueError` naming the key, the expected type and the given value. The same applies to values outside the allowed values. Expected types: [configuration.md](configuration.md). (SC-5, SC-19)
   - YAML 1.1 parses some unquoted values as non-strings, e.g. `country: NO` (Norway) as boolean `false`. Such a value MUST be rejected as a wrong type, and the message SHOULD advise quoting (`country: "NO"`).
5. A configured path that does not exist MUST raise `FileNotFoundError` naming the path: `network_results_path`, `definitions_path` (unless `false`), `mapping_path`.
6. `country` MUST accept every ISO 3166-1 alpha-2 code and the value `all`; anything else MUST raise `ValueError`. This explicitly includes the codes of all 27 EU member states: `AT`, `BE`, `BG`, `CY`, `CZ`, `DE`, `DK`, `EE`, `ES`, `FI`, `FR`, `GR`, `HR`, `HU`, `IE`, `IT`, `LT`, `LU`, `LV`, `MT`, `NL`, `PL`, `PT`, `RO`, `SE`, `SI`, `SK`, and non-EU codes such as `CH`, `NO`, `GB`. (SC-3, OQ-4, OQ-11)
7. All config validation MUST be completed before any network file is read (P5 "early"). (SC-18)
8. Relative paths are resolved against the current working directory (A-1).

**Sources:** `class_definitions.py::Network_Processor.__init__` (l.165-279), `_is_valid_country_identifier`, `_is_definitions_disabled`; `configs/config.default.yaml`; `README.md` "Set the config parameters"; owner decisions in the kick-off.

**Acceptance criteria**
- C1-AC1: For each required key, a config without it raises `ValueError` whose message contains the key name.
- C1-AC2: Each of the 27 EU member-state codes listed in requirement 6 is accepted (parametrised test), as are `CH`, `"NO"` (quoted), `GB` and `all`; `XX`, `Austria`, `at1` raise `ValueError`.
- C1-AC3: Each of the following raises `ValueError` naming the key: `aggregation_level: nation`, `aggregation_level: 1`, `aggregate_per_year: "yes"`, `map_country_codes_to_names: "yes"`, `convert_units: "yes"`, `country: 1`, `model_name: 1.0`, `scenario_name: [a, b]`, `network_results_path: 5`, `mapping_path: true`, `output_path: 5`.
- C1-AC3b: Unquoted `country: NO` raises `ValueError` whose message mentions quoting.
- C1-AC4: A non-existing `network_results_path`, `definitions_path` or `mapping_path` raises `FileNotFoundError`.
- C1-AC5: With an invalid `aggregation_level`, `pypsa.NetworkCollection` is not constructed (mock asserts not called).
- C1-AC6: A config with only the five required keys initialises without error, and the defaults of [configuration.md](configuration.md) apply (`aggregation_level == "country"`, `aggregate_per_year is True`, `map_country_codes_to_names is False`, `convert_units` true, default mapping file, output directory `<cwd>/resources`).

---

## C2 Network results folder

Example: `resources/AT_KN2040/` (contains `configs/`, `networks/`, `resources/energy_totals.csv`, among others).

**Requirements**
1. **Networks.** All files `<network_results_path>/networks/*.nc` MUST be read together as one `pypsa.NetworkCollection`. Each file holds one solved network for one investment year. A missing `networks/` folder or a folder without `.nc` files MUST raise `FileNotFoundError` during initialisation. (SC-11)
2. **Investment year.** (Owner decision, kick-off review.)
   - If `n.meta["wildcards"]["planning_horizons"]` is present, it MUST be used as the investment year. `n.meta` is present in PyPSA-AT networks.
   - If it is not present (e.g. pypsa-eur networks, which carry no `n.meta`), the investment year MUST be taken from the network's file name, and a `WARNING` naming the file and the derived year MUST be logged. The year is the last group of exactly four digits that is not adjacent to other digits, e.g. `base_s_adm__none_2030.nc` → 2030, `base_s_adm__none_2040_1H.nc` → 2040 (file names from `resources/AT_KN2040/networks/`, `resources/AT_KN2040_1H/networks/`).
   - No `planning_horizons` entry and no four-digit group in the file name → `ValueError` naming the file.
   - Two networks with the same investment year MUST raise `ValueError` (A-2). (SC-11)
   - The investment year MUST be determined during initialisation (P5 "early").
3. **Network config.** For each investment year, the file matching `<network_results_path>/configs/config*<year>.yaml` (e.g. `config.base_s_adm__none_2030.yaml`) MUST be loaded with `yaml.safe_load` and passed as `config` (C5).
   - No matching file → log `WARNING` naming year and pattern; `config=None`.
   - Several matching files → use the first one in lexicographic order and log `WARNING` listing all matches. (SC-17)
   - File cannot be read or parsed → log `WARNING` naming the file and error; `config=None`.
   - What a function declaring `config` does with `config=None` is open (OQ-6).
4. **Energy totals.** The path `<network_results_path>/resources/energy_totals.csv` MUST be passed as `energy_totals` (C5) to functions declaring that parameter.
   - Its existence MUST be checked during initialisation.
   - Missing file → log one `WARNING` naming the path. Every variable whose function declares `energy_totals` MUST then be skipped, each with a `WARNING` naming variable and function. All other variables MUST be evaluated normally. (Owner decision, kick-off review; A-3; SC-7)

**Sources:** `Network_Processor._read_pypsa_network_collection`, `_get_network_config`, `_execute_function_for_variable`, `calculate_variables_values`; `resources/AT_KN2040/` (folder listing); `README.md` "Function Signature".

**Acceptance criteria**
- C2-AC1: A results folder without `networks/`, or with an empty `networks/`, raises `FileNotFoundError` at initialisation.
- C2-AC2: A network with file name `base_s_adm__none_2030.nc` and `meta["wildcards"]["planning_horizons"] = 2040` produces output for 2040, and no file-name `WARNING` is logged.
- C2-AC3: A network without `n.meta` and file name `base_s_adm__none_2040_1H.nc` produces output for 2040, and a `WARNING` naming the file is logged (`caplog`).
- C2-AC3b: A network without `n.meta` and file name `network.nc` raises `ValueError` naming the file. Two networks with the same investment year (from meta or file name) raise `ValueError`.
- C2-AC4: With `configs/config.a_2030.yaml` and `configs/config.b_2030.yaml`, `config.a_2030.yaml` is loaded and a `WARNING` is logged (`caplog`).
- C2-AC5: Without a matching network config, a `WARNING` is logged and a function declaring `config` receives `None`.
- C2-AC6: Without `resources/energy_totals.csv`, a function declaring `energy_totals` is not called, a `WARNING` naming its variable is logged, and a function not declaring it is still called and its variable appears in the output.

---

## C3 Variable selection

**Requirements**
1. `definitions_path: <folder>` → the evaluated variables are the variables of `nomenclature.DataStructureDefinition(<folder>)` that have an entry in the mapping file, in the order of the definitions.
   - Definition variables without a mapping entry are skipped without warning: the definitions intentionally cover more variables than are implemented.
   - Mapping entries whose variable is not in the definitions are not evaluated; this SHOULD be logged once as `WARNING` at initialisation listing those variables (OQ-7).
   - Units are converted to the definition units if `convert_units: true` (C9).
2. `definitions_path: false` (YAML bool `false` or string `"false"`, case-insensitive) → every variable in the mapping file is evaluated, in file order. No unit conversion takes place, independent of `convert_units`.
3. Each selected variable is evaluated once per investment year.

**Sources:** `Network_Processor.calculate_variables_values` (l.839-843), `_is_definitions_disabled`, class docstring; `README.md` "Mapping File"; `CLAUDE.md` "Key Implementation Notes".

**Acceptance criteria**
- C3-AC1: With definitions `{A, B, C}` and mapping `{A, B}`, exactly `A` and `B` are evaluated.
- C3-AC2: With `definitions_path: false` and mapping `{A, D}`, exactly `A` and `D` are evaluated and units are not converted (output unit equals the `UNITS_MAPPING`-normalised PyPSA unit).
- C3-AC3: `definitions_path: "False"` behaves like `definitions_path: false`.
- C3-AC4: With definitions `{A}` and mapping `{A, D}`, `D` is not evaluated and a `WARNING` naming `D` is logged.

---

## C4 Mapping file

**Requirements**
1. The mapping file is a YAML mapping from `<IAMC variable>` (string) to an entry in one of two forms (owner decision, aggregation classes):
   - short form `<IAMC variable>: <function name>` (string), equivalent to `{function: <function name>, aggregation: flow}`;
   - long form `<IAMC variable>: {function: <function name>, aggregation: <class>}` with `<class>` ∈ {`flow`, `stock`, `intensive`} (item 5). The key `aggregation` MAY be omitted (default `flow`); `function` is required.

   Default: `pypsa_validation_processing/configs/mapping.default.yaml`; override via `mapping_path`.
2. A missing mapping file MUST raise `FileNotFoundError`. A file that is empty, not a mapping, or has an entry that is neither of the forms in item 1 (missing `function`, unknown key, `aggregation` not one of the three classes) MUST raise `ValueError` naming the variable. (SC-6, SC-21)
3. Every function name SHOULD follow the naming convention of `README.md` ("Naming Convention"): `|` → `__`, space → `_`, other special characters removed.
4. Every function name of a variable selected for evaluation (C3) MUST exist in `pypsa_validation_processing/statistics_functions.py`.
   - The check MUST happen during initialisation, before any network is read (P5 "early").
   - A missing function is a configuration error: `Network_Processor` MUST raise `ValueError` naming the variable and the function. (Owner decision, second review round; replaces the earlier "warn and skip"; SC-6)
5. **Aggregation classes.** The aggregation class of a variable determines how values are aggregated over time (inside the statistics function, C6) and over regions and extra index levels (in `Network_Processor`, C8):

   | Class | Typical quantities (examples) | Over time (`aggregate_per_year=True`, C6) | Over regions and extra index levels (C8) |
   |---|---|---|---|
   | `flow` | energy (`MWh`), emissions (`t`), total costs (`EUR`) | sum over snapshots, weighted by snapshot weightings | sum |
   | `stock` | capacity (`MW`), storage volume (`MWh`) | end-of-year value; no sum over snapshots | sum |
   | `intensive` | prices (`EUR/MWh`), specific investment costs (`EUR/kW`) | weighted mean over snapshots, computed by the function | weighted mean with the weights returned by the function |

   The class is a property of the variable, not of the function: the same function MAY in principle serve variables of different classes, but the declared class MUST match what the function returns (C6.10–C6.12).

**Sources:** `configs/mapping.default.yaml`, `configs/mapping.prices_ie.yaml`; `Network_Processor._read_mappings`, `_execute_function_for_variable` (l.368-382); `README.md` "Mapping File", "Naming Convention".

**Acceptance criteria**
- C4-AC1: A non-existing `mapping_path` raises `FileNotFoundError`; an empty mapping file raises `ValueError`.
- C4-AC2: With `definitions_path: false` and a mapping entry `X: does_not_exist`, constructing `Network_Processor` raises `ValueError` whose message contains `X` and `does_not_exist`, and `pypsa.NetworkCollection` is not constructed (mock asserts not called).
- C4-AC3: Every entry of `mapping.default.yaml` names an existing function in `statistics_functions.py`.
- C4-AC4: `X: f` and `X: {function: f}` both give class `flow` for `X`; `X: {function: f, aggregation: intensive}` gives class `intensive`.
- C4-AC5: Each of `X: {aggregation: flow}`, `X: {function: f, aggregation: mean}`, `X: {function: f, weight: g}` and `X: [f]` raises `ValueError` at initialisation naming `X`, and `pypsa.NetworkCollection` is not constructed.

---

## C5 Statistics function interface

**Requirements**
1. A statistics function is a module-level function in `statistics_functions.py` with signature
   ```python
   def <function_name>(
       n: pypsa.Network,
       aggregate_per_year: bool = True,
       config: dict | None = None,        # optional, only if needed
       energy_totals: Path | None = None, # optional, only if needed
   ) -> pd.Series | pd.DataFrame: ...
   ```
2. Every statistics function MUST declare `n` and `aggregate_per_year` as its first two parameters (owner decision, second review round). `n` receives one `pypsa.Network` (one investment year), not the collection.
3. `Network_Processor` MUST always call a statistics function with `n` and `aggregate_per_year` (the configured value).
4. `config` and `energy_totals` are optional parameters. `Network_Processor` MUST pass them as keyword arguments only if the function's signature declares them (`inspect.signature`).
5. Further parameters MAY be added; they MUST have defaults, and `Network_Processor` never passes them.
6. The signature of every function selected for evaluation MUST be checked during initialisation. A function that does not declare `n` and `aggregate_per_year` as its first two parameters, or has a parameter other than `n` without default, is a configuration error: `ValueError` naming the variable and the function (P5).
7. Type hints in the signature and a NumPy-style docstring are required (`CLAUDE.md` "Code Style").

**Sources:** `Network_Processor._execute_function_for_variable` (l.384-398); `README.md` "Function Signature (fixed)"; `statistics_functions.py` module docstring.

**Acceptance criteria**
- C5-AC1: `f(n, aggregate_per_year=True)` receives the configured `aggregate_per_year` (test with `true` and `false`) and no other keyword arguments; `f(n, aggregate_per_year=True, config=None)` additionally receives the network config of its year; `f(n, aggregate_per_year=True, energy_totals=None)` additionally receives `<network_results_path>/resources/energy_totals.csv`.
- C5-AC2: Mapping a variable to `f(n)` (no `aggregate_per_year`), or to `f(n, aggregate_per_year=True, x)` (`x` without default), raises `ValueError` at initialisation naming the variable and `f`.
- C5-AC3: For every public function defined in `statistics_functions.py`, the first two parameters are `n` and `aggregate_per_year`, and all parameters except `n` have defaults.

---

## C6 Statistics function output

**Requirements**
1. `aggregate_per_year=True` → MUST return a `pd.Series` with a `pd.MultiIndex` containing at least the levels `location` and `unit`. Values are the yearly values according to the variable's aggregation class (C4.5, items 10–12).
2. `aggregate_per_year=False` → MUST return a `pd.DataFrame` (not a `pd.Series`) whose columns are snapshot timestamps of `n` and whose index is a `pd.MultiIndex` containing at least `location` and `unit`.
3. Additional index levels MAY be present; they are aggregated in post-processing according to the aggregation class (C8). The level name `quantity` is reserved for `intensive` variables (item 12).
4. Values MUST be of a numeric dtype. NaN and zero are valid values; a result whose values are all zero or all NaN is valid (owner decision, second review round).
5. `unit` values MUST be valid PyPSA units per C9.1 (e.g. `MWh_el`, `MWh_LHV`, `MWh_th`, `t_co2`): non-empty, not a carrier label, key of `utils.UNITS_MAPPING`.
6. `location` values MUST be non-empty values of `n.buses.location` of the evaluated network (e.g. `AT1`). The function MUST NOT aggregate to country level (C8 does this).
7. The result MUST contain at least one row (A-4).
8. A result is invalid **only if its structure is incorrect**, i.e. it violates one of items 1, 2, 4–7 and the structural parts of items 10–12 (presence and values of the `quantity` level). Values themselves (zero, NaN, sign, magnitude) are not checked here, with the exception of negative weights (item 12).
9. `Network_Processor` MUST validate every result against item 8. An invalid result MUST abort the run with an exception whose message names the variable and the violation (P5, owner decision). (SC-8)
10. **`flow`**: the yearly value is the sum over all snapshots, weighted by the snapshot weightings the function uses (e.g. `n.snapshot_weightings.objective` via `n.statistics`). The result MUST NOT have a `quantity` level.
11. **`stock`**: the yearly value is the end-of-year value of the investment year, typically read from static component data (e.g. `p_nom_opt`) and not summed over snapshots. With `aggregate_per_year=False`, each snapshot column holds the value at that snapshot if time-variant data is available; otherwise every column holds the yearly value. The result MUST NOT have a `quantity` level.
12. **`intensive`**: the result MUST have an index level `quantity` with exactly the values `value` and `weight`; every row with `quantity = value` MUST have a row with `quantity = weight` and identical other index labels, and vice versa (the weight row carries the same `unit` label as its value row).
    - `value` rows hold the intensive quantity (e.g. `EUR/MWh`). `weight` rows hold the non-negative weight for aggregation, e.g. the energy volume the price applies to; a negative weight is a structural error. Which weight is used is part of the variable spec.
    - With `aggregate_per_year=False`, weights are given per snapshot and already include the snapshot weighting (e.g. energy per snapshot in `MWh`, not power).
    - With `aggregate_per_year=True`, the `value` row is the weighted mean over snapshots, Σₜ vₜ·wₜ / Σₜ wₜ, and the `weight` row is Σₜ wₜ.
    - The function computes both; `Network_Processor` never aggregates over time.

**Sources:** `CLAUDE.md` "Function Architecture (Critical)", "Local debugging", "Testing Rules"; `README.md` "Return format rules"; `Network_Processor.calculate_variables_values` (l.849-856).

**Acceptance criteria**
- C6-AC1 (per statistics function, in `tests/test_statistics_functions.py`): with `aggregate_per_year=True` the result
  - is a `pd.Series` with a `pd.MultiIndex` and `{"location", "unit"} ⊆ set(result.index.names)`;
  - has at least one row and a numeric dtype (`pd.api.types.is_numeric_dtype`);
  - has only `unit` values that are non-empty keys of `UNITS_MAPPING` and not carrier labels (C9.1);
  - has only `location` values contained in `n.buses.location` of the mock network and none empty.
- C6-AC2 (per statistics function): with `aggregate_per_year=False` the result
  - is a `pd.DataFrame` (not a `pd.Series`) with a `pd.MultiIndex` and `{"location", "unit"} ⊆ set(result.index.names)`;
  - has columns that are a subset of `n.snapshots`, at least one row, and only numeric column dtypes;
  - fulfils the `unit` and `location` checks of C6-AC1.
- C6-AC3: For one function and the same network, the `True` result follows from the `False` result according to the class (per statistics function, in `tests/test_statistics_functions.py`):
  - `flow`: the sum over the columns of the `False` result equals the `True` result (weighted by snapshot weightings where the function uses them);
  - `stock`: the last column of the `False` result equals the `True` result;
  - `intensive`: for each row, the `True` `weight` equals the sum over the columns of the `False` `weight` row, and the `True` `value` equals Σₜ vₜ·wₜ / Σₜ wₜ computed from the `False` `value` and `weight` rows.
- C6-AC4: `Network_Processor` raises an exception naming the variable and the violation when a function returns, for `aggregate_per_year=True`:
  - a Series with zero rows;
  - a Series without `location` level, or without `unit` level, or with a flat index;
  - a Series of dtype `object` with string values;
  - a Series with unit `""`, `"land transport"` or `"foo"`;
  - a Series with location `""` or `"XX9"` (not in `n.buses.location`);
  - a `pd.DataFrame`;
  - for a `flow` or `stock` variable: a Series with a `quantity` level;
  - for an `intensive` variable: a Series without `quantity` level; with a `quantity` value other than `value`/`weight`; with a `value` row lacking its `weight` row; with a negative weight;

  and, for `aggregate_per_year=False`:
  - a `pd.Series`;
  - a DataFrame without `location` level;
  - a DataFrame with columns that are not snapshots of `n`;
  - a DataFrame with a non-numeric column.
- C6-AC5: `Network_Processor` does **not** raise for a structurally valid Series whose values are all `0.0`, nor for one whose values are all NaN; the variable appears in the output (all-NaN rows MAY be dropped by pyam, see OQ-12).

---

## C7 Function independence

**Requirements**
1. A statistics function MUST NOT call or import another statistics function.
2. Shared logic MUST live in `utils.py`. Helpers in `utils.py` MAY call other `utils.py` helpers.
3. `utils.py` MUST NOT import from `statistics_functions.py`.

**Sources:** `CLAUDE.md` "Function Architecture (Critical)"; `docs/contributing.md` "Function Architecture".

**Acceptance criteria**
- C7-AC1: Parsing `statistics_functions.py` with `ast`, no function body references the name of another function defined in that module.
- C7-AC2: `utils.py` contains no import of `statistics_functions`.

---

## C8 Aggregation (in `Network_Processor`)

The country of a location is its first two characters (`AT1` → `AT`). "Aggregate" in the table means the class-specific operation of item 2 (sum for `flow` and `stock`, weighted mean for `intensive`).

| `aggregation_level` | `country: <code>` (e.g. `AT`) | `country: all` |
|---|---|---|
| `country` | keep locations starting with `<code>`, aggregate them into one row per `(variable, unit)`; region label = `<code>` | aggregate per country prefix (`AT1 → AT`, `DE2 → DE`); one row per `(variable, country, unit)`; region label = country code |
| `region` | keep only locations starting with `<code>`; one row per `(variable, location, unit)`; region label = location | keep all locations; one row per `(variable, location, unit)` |

**Post-processing order.** After a statistics function has returned a valid result (C6.9), `Network_Processor` MUST apply these steps in this order:

1. **Aggregation** by the table below and over extra index levels (item 2), grouped by the **raw PyPSA unit labels** (`MWh_el` and `MWh_th` stay separate rows).
2. **Unit label normalisation** via `UNITS_MAPPING` (C9.1).
3. **Re-groupby** by region label (and `quantity` for `intensive`) and normalised unit, with the same class-specific operation as in step 1 (item 2).
4. **Unit conversion** (C9.2), if configured. It is always the last transformation of values.

**Requirements**
1. Aggregation MUST follow the table and the post-processing order above.
2. Index levels other than `location`, `unit` and `quantity` MUST be aggregated according to the aggregation class (C4.5), in the same step as locations:
   - `flow`, `stock`: sum.
   - `intensive`: weighted mean, value = Σ vᵢ·wᵢ / Σ wᵢ over all rows i of a group, using the `weight` row paired with each `value` row (C6.12). The `weight` of the aggregated row is Σ wᵢ, so that step 3 of the post-processing order can repeat the weighted mean. For time series this is done per snapshot column. If Σ wᵢ = 0, the value is NaN (A-5).
3. Normalisation (step 2) MUST NOT happen before aggregation (step 1). Rows that share region label and normalised unit after step 2 MUST be combined in step 3 with the operation of item 2.
4. If `map_country_codes_to_names: true`, region labels MUST be mapped via `utils.REGION_MAPPING`; labels without entry stay unchanged.
5. A configured country without matching locations: behaviour open (OQ-9).
6. For `intensive` variables, `weight` rows MUST be dropped after step 3 (re-groupby); only `value` rows reach unit conversion and output. With `aggregation_level: region`, no aggregation over locations takes place, but extra index levels are still aggregated as in item 2.

**Sources:** `Network_Processor._aggregate_to_country`, `_filter_to_regions`, `_select_aggregation_result`, `_postprocess_statistics_result`, `structure_pyam_from_pandas`; `CLAUDE.md` "Aggregation behavior".

**Acceptance criteria**
- C8-AC1: Input `{(AT1, MWh): 1, (AT2, MWh): 2, (DE1, MWh): 4}`:
  - `country`/`AT` → one row `AT, MWh = 3`;
  - `country`/`all` → `AT = 3`, `DE = 4`;
  - `region`/`AT` → `AT1 = 1`, `AT2 = 2`;
  - `region`/`all` → `AT1 = 1`, `AT2 = 2`, `DE1 = 4`.
- C8-AC2: Input with an extra level `carrier` is summed over `carrier`.
- C8-AC3: `{(AT1, MWh_el): 1, (AT2, MWh_el): 4, (AT1, MWh_th): 2}` with `country`/`AT`: after step 1 `{(AT, MWh_el): 5, (AT, MWh_th): 2}`; after steps 2–3 one row `AT, MWh = 7`.
- C8-AC3b (`intensive`): `{(AT1, EUR/MWh_el): value 10, weight 1; (AT1, EUR/MWh_th): value 40, weight 2}` with `region`/`AT` → after step 1 two value rows (10 and 40); after steps 2–3 one row `AT1, EUR/MWh = 30` (= (10·1 + 40·2) / 3).
- C8-AC4: With `map_country_codes_to_names: true`, region `AT` becomes `Austria`; an unmapped label is unchanged.
- C8-AC5: The same input in time series form gives the same results per column.
- C8-AC6 (`intensive`): input `{(AT1, EUR/MWh, value): 10, (AT1, EUR/MWh, weight): 1, (AT2, EUR/MWh, value): 40, (AT2, EUR/MWh, weight): 2, (DE1, EUR/MWh, value): 5, (DE1, EUR/MWh, weight): 1}`:
  - `country`/`AT` → one row `AT, EUR/MWh = 30` (= (10·1 + 40·2) / 3);
  - `country`/`all` → `AT = 30`, `DE = 5`;
  - `region`/`AT` → `AT1 = 10`, `AT2 = 40`;
  - in every case the output contains no `weight` rows and no `quantity` level.
- C8-AC7 (`intensive`): an extra level `carrier` with `(AT1, gas): value 20, weight 1` and `(AT1, oil): value 50, weight 0` gives `AT1 = 20` with `region`/`AT`; a group whose weights are all 0 gives NaN.
- C8-AC8 (`stock`): `{(AT1, MW): 100, (AT2, MW): 50}` with `country`/`AT` → `AT, MW = 150`, identical to `flow`.

---

## C9 Unit conversion

**Requirements**
1. **Unit validation and normalisation.** Normalisation is step 2 of the post-processing order (C8): after aggregation, before re-groupby and conversion.
   - Before aggregation (as part of result validation, C6.5), every raw `unit` value MUST be checked. An empty (or whitespace-only) string and a carrier label MUST be rejected with `ValueError` naming variable and value, **even if the value is a key of `UNITS_MAPPING`**. Example: `land transport` is a carrier label, not a unit.
   - `utils.UNITS_MAPPING` MUST contain only physical units as keys and values; the current keys `""` and `"land transport"` are not allowed. (SC-9)
   - Every valid PyPSA unit is then normalised via `UNITS_MAPPING` (e.g. `MWh_el`, `MWh_th`, `MWh_LHV` → `MWh`; `t_co2` → `t`).
   - A unit that is not a key of `UNITS_MAPPING` MUST raise `ValueError` naming variable and unit; it MUST NOT become NaN. (SC-9)
2. **Conversion.** Conversion is step 4 of the post-processing order (C8), the last transformation of values. If `convert_units: true` and definitions are used (C3), each variable MUST be converted with `pyam.IamDataFrame.convert_unit(current, to)` from the normalised unit to the unit in the definitions (pint with the `iam-units` registry). If both are equal, no conversion takes place.
3. If a definition lists several units (e.g. `unit: [ TJ, TWh ]` in `definitions/variable/trade.yaml`), the first one is used. A unit list that cannot be parsed MUST raise `ValueError`; there is no fallback unit. (SC-10)
4. If a variable has several definition entries, the first one is used and a `WARNING` is logged.
5. Errors (each MUST raise an exception naming the variable):
   - always: variable without unit → `ValueError`; several units for one variable after normalisation → `ValueError`;
   - only when conversion applies (C9.2: `convert_units: true` and definitions used): definition without unit → exception; unit not convertible → `ValueError`.

   A variable missing from the definitions never reaches this step (C3.1); with `definitions_path: false`, no definition-related check takes place (C3.2, C9.6).
6. If `convert_units: false` or `definitions_path: false`, output units are the normalised PyPSA units.

**Sources:** `Network_Processor._map_unit_level`, `_convert_units_to_common_definitions`, `_get_unit_from_common_definitions`; `utils.UNITS_MAPPING`; `definitions/variable/*.yaml`; https://pyam-iamc.readthedocs.io/en/stable/ (`convert_unit`).

**Acceptance criteria**
- C9-AC1: A result with unit `MWh_el` for a variable defined in `TJ` is output as `TJ` with value × 0.0036 (1 MWh = 3.6 GJ).
- C9-AC2: A result with unit `foo` (not in `UNITS_MAPPING`) raises `ValueError` containing `foo`.
- C9-AC2b: A result with unit `""` or `"land transport"` raises `ValueError` naming the variable, and no row with unit `MWh` is produced from it.
- C9-AC2c: `UNITS_MAPPING` contains neither the key `""` nor the key `"land transport"`.
- C9-AC3: For a definition `unit: [ TJ, TWh ]`, the output unit is `TJ`.
- C9-AC4: A variable with rows in `MWh` and `t` raises `ValueError`.
- C9-AC5: A unit pair without conversion (e.g. `t` → `TJ`) raises `ValueError`.
- C9-AC6: With `convert_units: false`, a `MWh_el` result is output as `MWh`.

---

## C10 Output

**Requirements**
1. **Data structure.** The result MUST be a `pyam.IamDataFrame` with IAMC index `model, scenario, region, variable, unit`; `model` = `model_name`, `scenario` = `scenario_name`, `region` = country or region label (C8).
2. **Output directory.** `output_path` is always a directory (default: repository-root `resources/`, see [configuration.md](configuration.md)). It MUST be created if it does not exist. (SC-1)
3. **Path tokens.** In file and folder names, whitespace runs in `model_name`, `scenario_name` and `country` are replaced by `_`; leading/trailing whitespace is removed. `_<country>` is omitted for `country: all`. `<level>` is the value of `aggregation_level` (`country` or `region`) and is always part of the name, so that runs that differ only in `aggregation_level` do not overwrite each other (owner decision, review; SC-22).
4. **Yearly output** (`aggregate_per_year: true`): one file `<output_path>/PYPSA_<model>_<scenario>_<level>[_<country>].xlsx`; year columns are integers (investment years).
5. **Time series output** (`aggregate_per_year: false`): folder `<output_path>/PYPSA_timeseries_<model>_<scenario>_<level>[_<country>]/` with one file per investment year `PYPSA_<model>_<scenario>_<level>[_<country>]_<year>.xlsx`.
   - Columns are timezone-aware timestamps in UTC (`+00:00`).
   - The year of every snapshot timestamp is replaced by the investment year (e.g. `2019-01-01 00:00` → `2050-01-01 00:00`). Leap-day handling is open (OQ-5).
6. **Excel layout.** Files are written with `pyam.IamDataFrame.to_excel` defaults (pyam 3.2): sheet `data` with all IAMC dimensions and sheet `meta`.
7. Existing files with the same name are overwritten. With the naming of items 3–5, this happens only for runs with identical `output_path`, `model_name`, `scenario_name`, `aggregation_level`, `country` and `aggregate_per_year`.

**Sources:** `Network_Processor.structure_pyam_from_pandas`, `write_output_to_xlsx`, `_sanitize_path_token`, `calculate_variables_values` (l.869-875); `format_timestamps`; `README.md` "Output behavior"; owner decisions in the kick-off.

**Acceptance criteria**
- C10-AC1: Without `output_path` and without `aggregation_level`, the yearly file is written to `<cwd>/resources/PYPSA_<model>_<scenario>_country_<country>.xlsx`.
- C10-AC2: With `output_path: out` (not existing), `out/` is created and contains the file.
- C10-AC3: `model_name: "Pypsa-AT v1.0"`, `scenario_name: "KN 2040"`, `aggregation_level: country`, `country: AT` → file name `PYPSA_Pypsa-AT_v1.0_KN_2040_country_AT.xlsx`; with `country: all` → `PYPSA_Pypsa-AT_v1.0_KN_2040_country.xlsx`; with `aggregation_level: region`, `country: AT` → `PYPSA_Pypsa-AT_v1.0_KN_2040_region_AT.xlsx`.
- C10-AC4: Time series for investment years 2030 and 2040 → folder `PYPSA_timeseries_<model>_<scenario>_<level>_<country>/` with files `PYPSA_<model>_<scenario>_<level>_<country>_2030.xlsx` and `…_2040.xlsx`.
- C10-AC5: Reading a yearly file with `pyam.IamDataFrame(path)` gives integer years and the configured model and scenario.
- C10-AC6: A time series column for snapshot `2019-03-01 12:00` in investment year 2050 is `2050-03-01 12:00+00:00`.
- C10-AC7: The written workbook contains the sheets `data` and `meta`.
- C10-AC8: Two runs into the same `output_path` with identical config except `aggregation_level` (`country`, then `region`) leave two yearly files (resp. two time series folders), and the first file is unchanged after the second run.

---

## C11 External dependencies

The package relies on the following behaviour. A dependency update that changes it is a breaking change and MUST be checked against this list. Versions: [constitution/tech-stack.md](constitution/tech-stack.md).

| Dependency | Relied-on behaviour | Used in |
|---|---|---|
| `pypsa` | `pypsa.NetworkCollection(list_of_paths)` reads `.nc` files; indexing yields `pypsa.Network`; `len()` gives the number of networks. | `_read_pypsa_network_collection`, `calculate_variables_values` |
| `pypsa` | In PyPSA-AT networks, `n.meta["wildcards"]["planning_horizons"]` holds the investment year; networks without `n.meta` (e.g. pypsa-eur) fall back to the file name (C2.2). | `calculate_variables_values` |
| `pypsa` | `n.statistics.<metric>(…, groupby=[…, "location", "unit"], nice_names=False, groupby_time=…)` returns a Series (time-aggregated) or DataFrame (snapshots as columns) with the requested index levels; filters `components`, `carrier`, `bus_carrier`, `direction`, `at_port`; metrics used: `energy_balance`, `supply`, `withdrawal`, `transmission`. | statistics functions; `utils.statistics_kwargs*`; https://docs.pypsa.org/latest/api/networks/statistics/ |
| `pandas` | MultiIndex `Series`/`DataFrame`, `groupby(...).sum()` over index levels. | everywhere |
| `nomenclature-iamc` | `DataStructureDefinition(path)` reads `variable/` and `region/`; `.variable.to_pandas()` returns columns `variable` and `unit`; tag expansion such as `{Final Energy Carrier}`. | `read_definitions`, `_get_unit_from_common_definitions`, `calculate_variables_values` |
| `pyam-iamc` | `IamDataFrame(data, model=, scenario=, region=, variable=, unit=)` from a wide DataFrame; `filter`, `concat`, `convert_unit(current, to)` with `iam-units`; `to_excel` writes sheets `data` and `meta`. | `structure_pyam_from_pandas`, `_convert_units_to_common_definitions`, `write_output_to_xlsx` |
| `pyyaml` | `yaml.safe_load` for package config, mapping, network configs. | `_read_config`, `_read_mappings`, `_get_network_config` |
| `openpyxl` | Excel engine used by `to_excel`. | `write_output_to_xlsx` |

**Acceptance criteria**
- C11-AC1: The integration run `pixi run workflow_test` succeeds with the locked versions.
