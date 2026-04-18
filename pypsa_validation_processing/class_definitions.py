from __future__ import annotations
import datetime
import glob
import importlib
import inspect
import os
from pathlib import Path
import re
import yaml
import pandas as pd
import pypsa
import nomenclature
import pyam

from pypsa_validation_processing.utils import EU27_COUNTRY_CODES, UNITS_MAPPING


def format_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Convert timestamp-like columns to tz-aware pandas.Timestamp (+01:00)."""
    fixed_tz = datetime.timezone(datetime.timedelta(hours=1))
    cols = list(df.columns)
    idx_name = df.columns.name
    try:
        parsed = pd.to_datetime(cols, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(cols, errors="coerce")

    converted_list: list[object] = []
    nat_list: list[object] = []

    for i, col in enumerate(cols):
        is_year_only = isinstance(col, str) and re.match(r"^\d{4}$", col) is not None
        parsed_value = parsed[i]

        if pd.isna(parsed_value) and not is_year_only:
            continue

        ts = (
            parsed_value
            if not pd.isna(parsed_value)
            else pd.Timestamp(f"{col}-01-01 00:00:00")
        )

        if ts.tz is not None:
            cols[i] = ts
            converted_list.append(col)
            continue

        try:
            ts_tz = ts.tz_localize(fixed_tz)
        except (TypeError, ValueError) as exc:
            print(
                f"WARNING: format_timestamps: failed to localize column {col!r}: {exc}. "
                "Setting label to pd.NaT"
            )
            ts_tz = pd.NaT
            nat_list.append(col)

        cols[i] = ts_tz
        if not pd.isna(ts_tz):
            converted_list.append(col)

    py_datetimes = pd.Index(cols, name=idx_name).to_pydatetime()
    df.columns = pd.Index(py_datetimes, dtype="object", name=idx_name)
    if nat_list:
        print("WARNING: format_timestamps: columns set to NaT:", nat_list)
    return df


class Network_Processor:
    """Processes a PyPSA NetworkCollection against IAMC variable definitions.

    Reads variable definitions from a definitions folder, executes the
    corresponding statistics functions to extract values from a given PyPSA
    NetworkCollection, and returns the results as a pyam.IamDataFrame.

    Outputs are converted to the units of common definitions, set in the
    definitions variable in ``definitions_path`` via
    :meth:`pyam.IamDataFrame.convert_unit` if ``convert_units`` is ``True`` in config.
    """

    def __init__(
        self,
        config_path: Path,
    ) -> None:
        self.config_path = config_path
        self.config = self._read_config()

        network_results_path = self.config.get("network_results_path")
        if network_results_path is None:
            raise ValueError(
                f"'network_results_path' not set in config at {self.config_path}"
            )
        self.network_results_path: Path = Path(network_results_path)
        if not self.network_results_path.exists():
            raise FileNotFoundError(
                f"Network results folder does not exist: {self.network_results_path}"
            )

        definitions_path = self.config.get("definitions_path", None)
        if definitions_path is None:
            raise ValueError(
                f"'definition_path' not set in config at {self.config_path}"
            )
        self.definitions_path: Path = Path(definitions_path)
        if not self.definitions_path.exists():
            raise FileNotFoundError(
                f"Definition folder does not exist: {self.definitions_path}"
            )

        if self.config.get("convert_units", True):
            self.common_dsd: nomenclature.DataStructureDefinition | None = (
                nomenclature.DataStructureDefinition(self.definitions_path)
            )

        default_mappings_path = (
            Path(__file__).resolve().parent / "configs" / "mapping.default.yaml"
        )
        self.mappings_path: Path = (
            Path(self.config["mapping_path"])
            if "mapping_path" in self.config
            else default_mappings_path
        )

        self.country: str = self.config.get("country", None)
        if self.country is None or not self._is_valid_country_identifier(self.country):
            raise ValueError(
                f"'country' must be an ISO 3166-1 alpha-2 code or 'all', got: {self.country!r}"
            )
        self.model_name: str = self.config["model_name"]
        self.scenario_name: str = self.config["scenario_name"]
        if self.model_name == None or self.scenario_name == None:
            raise ValueError(
                f"'model_name' and 'scenario_name' must be set in config at {self.config_path}"
            )
        self.network_collection = self._read_pypsa_network_collection()
        self.dsd: nomenclature.DataStructureDefinition = self.read_definitions()
        self.functions_dict: dict[str, str | list] = self._read_mappings()
        self.aggregation_level: str = self.config.get("aggregation_level", "country")
        if self.aggregation_level not in ["country", "region"]:
            raise ValueError(
                f"Invalid aggregation_level: '{self.aggregation_level}'. "
                f"Must be 'country' or 'region'."
            )
        self.aggregate_per_year: bool = self.config.get("aggregate_per_year", True)
        if not isinstance(self.aggregate_per_year, bool):
            raise ValueError(
                f"Invalid aggregate_per_year: '{self.aggregate_per_year}'. "
                f"Must be true or false."
            )
        self._function_parameter_cache: dict[object, set[str]] = {}
        self.dsd_with_values: pyam.IamDataFrame | list[tuple[int, pyam.IamDataFrame]] | None = None
        if self.country == "all":
            default_path_dsd_with_values = (
                Path(__file__).resolve().parent
                / "resources"
                / f"PYPSA_{self.model_name}_{self.scenario_name}.xlsx"
            )
        else:
            default_path_dsd_with_values = (
                Path(__file__).resolve().parent
                / "resources"
                / f"PYPSA_{self.model_name}_{self.scenario_name}_{self.country}.xlsx"
            )
        self.path_dsd_with_values: Path = (
            Path(self.config["output_path"])
            if "output_path" in self.config
            else default_path_dsd_with_values
        )

    def __repr__(self) -> str:
        return (
            f"Network_Processor\n"
            f"  country: {self.country}\n"
            f"  aggregation_level: {self.aggregation_level}\n"
            f"  network_results_path: {self.network_results_path}\n"
            f"  definitions_path: {self.definitions_path}\n"
        )

    def _is_valid_country_identifier(self, country: str) -> bool:
        """Check if country is a valid ISO code or the special value 'all'."""
        return country == "all" or country in EU27_COUNTRY_CODES

    def _read_config(self) -> dict:
        """Read and return the YAML configuration file."""
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def _read_mappings(self) -> dict:
        """Read and return the YAML mapping file."""
        if not self.mappings_path.exists():
            raise FileNotFoundError(
                f"Mapping file not found: {self.mappings_path}"
            )
        with open(self.mappings_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _read_pypsa_network_collection(self) -> pypsa.NetworkCollection:
        """Reads in pypsa networks as NetworkCollection from network_results_path / networks"""
        nw_path = self.network_results_path / "networks"
        file_list = [nw_path / f for f in os.listdir(nw_path) if f.endswith(".nc")]
        return pypsa.NetworkCollection(file_list)

    def read_definitions(self) -> nomenclature.DataStructureDefinition:
        """Read IAMC variable definitions from the definitions folder.

        Populates ``dsd`` with a
        :class:`nomenclature.DataStructureDefinition` built from
        ``self.definitions_path`` and returns it.

        Returns
        -------
        nomenclature.DataStructureDefinition
            The loaded data structure definition.
        """
        dsd = nomenclature.DataStructureDefinition(self.definitions_path)
        return dsd

    def _execute_function_for_variable(
        self, variable: str, n: pypsa.Network, config: dict | None = None
    ) -> pd.Series | None:
        """Look up and execute the statistics function for a single variable.

        Looks up *variable* in ``self.functions_dict``, imports the
        corresponding function from :mod:`pypsa_validation_processing.statistics_functions`,
        calls it with ``self.network_collection``, and returns the result.

        Parameters
        ----------
        variable : str
            IAMC variable name to process.
        n : pypsa.Network
            PyPSA network to process.
        config : dict | None, optional
            Configuration dictionary loaded from the network results config file
            for the corresponding investment year. Passed to the statistics
            function only if the function's signature includes a ``config``
            parameter.

        Returns
        -------
        pd.Series | None
            Computed values for the variable, or ``None`` if no function
            is registered for it.
        """
        func_name = self.functions_dict.get(variable)
        if func_name is None:
            return None

        stats_module = importlib.import_module(
            "pypsa_validation_processing.statistics_functions"
        )
        func = getattr(stats_module, func_name, None)
        if func is None:
            print(
                f"WARNING: Variable {variable}: Function '{func_name}' not found in statistics_functions.py"
            )
            return None

        params = self._function_parameter_cache.get(func)
        if params is None:
            params = set(inspect.signature(func).parameters)
            self._function_parameter_cache[func] = params
        kwargs: dict = {}
        if "config" in params:
            kwargs["config"] = config
        if "aggregate_per_year" in params:
            kwargs["aggregate_per_year"] = self.aggregate_per_year
        return func(n, **kwargs)

    def _aggregate_to_country(self, result: pd.DataFrame) -> pd.DataFrame:
        """Aggregate a regional Series/DataFrame to country level by summing regions.

        Parameters
        ----------
        result : pd.DataFrame
            DataFrame with MultiIndex containing at least ``location``
            and ``unit`` levels

        Returns
        -------
        pd.DataFrame
            When ``self.country`` is a specific code: DataFrame with
            MultiIndex containing only the ``unit`` level (regions filtered to
            the configured country and summed).

            When ``self.country == "all"``: DataFrame with MultiIndex
            ``["country", "unit"]`` where each country's regions are summed
            independently (country derived from the first two characters of the
            location identifier).
        """
        if self.country == "all":
            # Derive 2-letter country code from location prefix, then group by
            # (country, unit) so each country is summed independently.
            locations = result.index.get_level_values("location")
            countries = pd.Index([loc[:2] for loc in locations], name="country")
            units = result.index.get_level_values("unit")
            new_index = pd.MultiIndex.from_arrays(
                [countries, units], names=["country", "unit"]
            )
            result = pd.DataFrame(
                result.values, index=new_index, columns=result.columns
            )
            return result.groupby(["country", "unit"]).sum()
        mask = result.index.get_level_values("location").isin(
            [
                reg
                for reg in result.index.get_level_values("location")
                if reg.startswith(self.country)
            ]
        )
        return result.loc[mask].groupby("unit").sum()

    def _filter_to_regions(self, result: pd.DataFrame) -> pd.DataFrame:
        """Filter a regional Series to the all regions of the given country.

        Parameters
        ----------
        result : pd.DataFrame
            DataFrame with MultiIndex containing at least ``location`` and ``unit``
            levels, as returned by statistics functions.

        Returns
        -------
        pd.DataFrame
            Datafrme with MultiIndex containing levels ``location`` and ``unit``.

        Notes
        -----
        When ``self.country == "all"``, all regions are returned without
        filtering.  When a specific country code is configured, only regions
        whose location starts with that code are returned.
        """
        if self.country == "all":
            return result
        mask = result.index.get_level_values("location").isin(
            [
                reg
                for reg in result.index.get_level_values("location")
                if reg.startswith(self.country)
            ]
        )
        return result.loc[mask]

    def _select_aggregation_result(
        self, result: pd.Series | pd.DataFrame
    ) -> pd.DataFrame:
        """Return result at configured aggregation level (country or region)."""
        if self.aggregation_level == "country":
            return self._aggregate_to_country(result)
        return self._filter_to_regions(result)

    def _map_unit_level(self, data: pd.DataFrame) -> pd.DataFrame:
        """Map the ``unit`` index level using ``UNITS_MAPPING``."""
        if isinstance(data.index, pd.MultiIndex):
            idx_frame = data.index.to_frame(index=False)
            idx_frame["unit"] = idx_frame["unit"].map(UNITS_MAPPING)
            data.index = pd.MultiIndex.from_frame(idx_frame)
            return data

        data.index = data.index.map(UNITS_MAPPING)
        data.index.name = "unit"
        return data

    def _postprocess_group_levels(self) -> list[str]:
        """Return grouping levels based on configured aggregation granularity."""
        if self.aggregation_level == "country":
            if self.country == "all":
                return ["variable", "country", "unit"]
            return ["variable", "unit"]
        return ["variable", "location", "unit"]

    def _postprocess_statistics_result(
        self, variable: str, result: pd.Series | pd.DataFrame
    ) -> pd.DataFrame:
        """Format a statistics-function result into a DataFrame.

        Applies aggregation based on ``self.aggregation_level``:

        - ``"country"``: sums all regions via :meth:`_aggregate_to_country`,
          then returns a DataFrame grouped by ``["variable", "unit"]``.
        - ``"region"``: keeps all regions, returns a DataFrame grouped
          by ``["variable", "location", "unit"]``.

        When ``self.aggregate_per_year`` is ``True`` the input *result* is a
        :class:`pandas.Series` and a ``"value"`` column is produced.
        When ``False`` the input is a :class:`pandas.DataFrame` with snapshot
        timestamps as columns, which are preserved in the output.

        Parameters
        ----------
        variable : str
            IAMC variable name.
        result : pd.Series | pd.DataFrame
            Series (``aggregate_per_year=True``) or DataFrame
            (``aggregate_per_year=False``) with MultiIndex
            ``["location", "unit"]`` (plus possible extra levels) as returned
            by statistics functions.

        Returns
        -------
        pd.DataFrame
            DataFrame with ``variable``, ``unit`` (and ``location`` when
            ``aggregation_level="region"``), and ``value`` column or snapshot
            columns, grouped accordingly.
        """
        processed = self._select_aggregation_result(result)
        processed = self._map_unit_level(processed)

        df = pd.concat({variable: processed}, names=["variable"])
        return df.groupby(self._postprocess_group_levels()).sum()

    def structure_pyam_from_pandas(self, df: pd.DataFrame) -> pyam.IamDataFrame:
        """Creates a pyam.IamDataFrame from a pandas DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with IAMC variables as columns and years as index.

        Returns
        -------
        pyam.IamDataFrame
            A pyam.IamDataFrame with IAMC variables as columns and years as index.

        Notes
        -----
        When ``aggregation_level="country"`` and ``country`` is a specific ISO
        code, the region is set to the full country name from
        :data:`EU27_COUNTRY_CODES`.  When ``country="all"``, the ``country``
        column in *df* (populated by :meth:`_aggregate_to_country`) is mapped
        to full country names and used as the region dimension, so each country
        appears as a separate row.  When ``aggregation_level="region"``, the
        ``location`` column in *df* is used directly.
        """
        df = format_timestamps(df)
        # add 'variable' and 'unit' columns
        df = df.reset_index()
        # rename columns if needed
        col_renaming_dict = {
            "variable": "variable_name",
            "unit": "unit_pypsa",
        }
        df = df.rename(
            columns={k: v for k, v in col_renaming_dict.items() if k in df.columns}
        )

        if self.aggregation_level == "country":
            if self.country == "all":
                # Map 2-letter country codes in the "country" column to full
                # country names so each country becomes its own pyam region.
                df["country"] = df["country"].map(
                    lambda c: EU27_COUNTRY_CODES.get(c, c)
                )
                dsd = pyam.IamDataFrame(
                    data=df.drop_duplicates(),
                    model=self.model_name,
                    scenario=self.scenario_name,
                    region="country",
                    variable="variable_name",
                    unit="unit_pypsa",
                )
            else:
                region = EU27_COUNTRY_CODES.get(self.country, self.country)
                dsd = pyam.IamDataFrame(
                    data=df.drop_duplicates(),
                    model=self.model_name,
                    scenario=self.scenario_name,
                    region=region,
                    variable="variable_name",
                    unit="unit_pypsa",
                )
        else:
            # region: use column "location" for pyams region-variable
            dsd = pyam.IamDataFrame(
                data=df.drop_duplicates(),
                model=self.model_name,
                scenario=self.scenario_name,
                region="location",
                variable="variable_name",
                unit="unit_pypsa",
            )
        dsd = self._convert_units_to_common_definitions(dsd)

        return dsd

    def _convert_units_to_common_definitions(
        self, iam_df: pyam.IamDataFrame
    ) -> pyam.IamDataFrame:
        """Convert variable units to units from ``self.common_dsd`` if configured."""
        if self.common_dsd is None:
            return iam_df

        converted_parts: list[pyam.IamDataFrame] = []
        for variable in dict.fromkeys(iam_df.variable):
            var_df = iam_df.filter(variable=variable)
            units = list(var_df.unit)
            if not units:
                raise ValueError(
                    f"No unit found for variable '{variable}' in IamDataFrame."
                )
            if len(set(units)) != 1:
                raise ValueError(
                    f"Variable '{variable}' has multiple units in IamDataFrame: {sorted(set(units))}"
                )

            current_unit = units[0]
            try:
                target_unit = self._get_unit_from_common_definitions(variable)
            except KeyError as exc:
                raise RuntimeError(
                    f"Variable '{variable}' not found in common definitions: {exc}"
                ) from exc

            if current_unit != target_unit:
                try:
                    var_df = var_df.convert_unit(current=current_unit, to=target_unit)
                except (ValueError, pyam.IamDataError) as exc:
                    raise ValueError(
                        f"Failed to convert units for variable '{variable}' from "
                        f"'{current_unit}' to '{target_unit}': {exc}"
                    ) from exc

            converted_parts.append(var_df)

        return pyam.concat(converted_parts)

    def _get_unit_from_common_definitions(self, variable: str) -> str:
        """Return target unit from common definitions for a given variable."""
        if self.common_dsd is None:
            raise RuntimeError("Common definitions are not initialized.")

        variables_df = self.common_dsd.variable.to_pandas()
        variable_col = "variable" if "variable" in variables_df.columns else "Variable"
        unit_col = "unit" if "unit" in variables_df.columns else "Unit"

        if variable_col not in variables_df.columns:
            raise KeyError("Variable column not found in common definitions.")
        if unit_col not in variables_df.columns:
            raise KeyError("Unit column not found in common definitions.")

        match = variables_df.loc[variables_df[variable_col] == variable]
        if match.empty:
            raise KeyError(f"Variable '{variable}' not defined in common definitions.")
        if len(match) > 1:
            print(
                f"WARNING: Multiple definitions found for variable '{variable}' in common definitions. Take first one: {match.iloc[0]}"
            )

        target_unit = match.iloc[0][unit_col]
        if pd.isna(target_unit):
            raise KeyError(
                f"Unit information not found for variable '{variable}' in common definitions."
            )
        return str(target_unit)

    def _get_network_config(self, investment_year):
        # Load network-results config for this investment year
        config_pattern = str(
            self.network_results_path / "configs" / f"config*{investment_year}.yaml"
        )
        matching_files = glob.glob(config_pattern)
        network_config: dict | None = None
        if matching_files:
            selected_config_file = matching_files[0]
            if len(matching_files) > 1:
                print(
                    f"INFO: Multiple config files found for investment year {investment_year}; "
                    f"using '{selected_config_file}'"
                )
            try:
                with open(selected_config_file, "r") as f:
                    network_config = yaml.safe_load(f)
            except Exception as exc:
                print(
                    f"WARNING: Could not load config file '{selected_config_file}': {exc}"
                )
        else:
            print(
                f"WARNING: No config file found for investment year {investment_year} "
                f"at pattern '{config_pattern}'"
            )
        return network_config

    def calculate_variables_values(self) -> None:
        """Calculate values for all defined variables.

        Iterates over all variables in ``self.dsd``, calls
        :meth:`_execute_function_for_variable` for each one, and assembles
        the results.

        When ``self.aggregate_per_year`` is ``True`` (default), assembles a
        single :class:`pyam.IamDataFrame` with one column per investment year
        and stores it in ``self.dsd_with_values``.

        When ``self.aggregate_per_year`` is ``False``, stores a
        ``list[tuple[int, pyam.IamDataFrame]]`` in ``self.dsd_with_values``,
        one entry per investment year.  Each :class:`pyam.IamDataFrame`
        contains the full time-series for that year.

        Applies aggregation based on ``self.aggregation_level`` config.
        """
        merge_keys = (
            ["variable", "country", "unit"]
            if (self.aggregation_level == "country" and self.country == "all")
            else (
                ["variable", "unit"]
                if self.aggregation_level == "country"
                else ["variable", "location", "unit"]
            )
        )
        container_investment_years = []
        for i in range(0, self.network_collection.__len__()):
            n = self.network_collection[i]
            investment_year = n.meta["wildcards"]["planning_horizons"]
            network_config = self._get_network_config(investment_year)

            results = []
            for variable in self.dsd.variable.to_pandas()["variable"]:
                result = self._execute_function_for_variable(variable, n, config=network_config)
                if result is not None:
                    # if aggregate_per_year, function returns a Series - convert to DataFrame.
                    if self.aggregate_per_year == True:
                        result = result.to_frame(name="value")
                    results.append(
                        self._postprocess_statistics_result(variable, result)
                    )

            if results:
                year_df = pd.concat(results, ignore_index=False)
                if self.aggregate_per_year:
                    year_df.rename(columns={"value": str(investment_year)}, inplace=True)
                    container_investment_years.append(year_df)
                else:
                    # Replace the year component of each snapshot timestamp with
                    # the investment year so that e.g. 2019-01-01 becomes 2050-01-01.
                    year_df.columns = year_df.columns.map(
                        lambda ts: ts.replace(year=int(investment_year))
                    )
                    iam_df = self.structure_pyam_from_pandas(year_df)
                    container_investment_years.append((investment_year, iam_df))

        if self.aggregate_per_year:
            if len(container_investment_years) > 0:
                ds_with_values = container_investment_years[0]
            if len(container_investment_years) > 1:
                for year_df in container_investment_years[1:]:
                    ds_with_values = ds_with_values.merge(
                        year_df, on=merge_keys, how="outer"
                    )
            self.dsd_with_values = self.structure_pyam_from_pandas(ds_with_values)
        else:
            self.dsd_with_values = container_investment_years

    def write_output_to_xlsx(self) -> Path:
        """Write the computed IAMC data to an Excel file (or files).

        Parameters
        ----------
            - When ``aggregate_per_year=True``: writes a single file
              ``<self.path_dsd_with_values>/PYPSA_{model}_{scenario}_{country}.xlsx``.
            - When ``aggregate_per_year=False``: creates a sub-folder
              ``<self.path_dsd_with_values>/PYPSA_timeseries_{model}_{scenario}_{country}/``
              and writes one file per investment year named
              ``PYPSA_{model}_{scenario}_{country}_{year}.xlsx``.

        Returns
        -------
        Path
            Path to the written file (``aggregate_per_year=True``) or to the
            folder containing all per-year files (``aggregate_per_year=False``).

        Raises
        ------
        RuntimeError
            If :meth:`calculate_variables_values` has not been called yet.
        """
        if self.dsd_with_values is None:
            raise RuntimeError(
                "No data available. Call calculate_variables_values() first."
            )

        base_dir = self.path_dsd_with_values
        if self.country == "all":
            base_filename = f"PYPSA_{self.model_name}_{self.scenario_name}"
        else:
            base_filename = f"PYPSA_{self.model_name}_{self.scenario_name}_{self.country}"

        if self.aggregate_per_year:
            file_path = base_dir / f"{base_filename}.xlsx"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self.dsd_with_values.to_excel(file_path)
            return file_path
        else:
            if self.country == "all":
                folder_name = f"PYPSA_timeseries_{self.model_name}_{self.scenario_name}"
            else:
                folder_name = f"PYPSA_timeseries_{self.model_name}_{self.scenario_name}_{self.country}"
            folder_path = base_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            for investment_year, iam_df in self.dsd_with_values:
                file_name = f"{base_filename}_{investment_year}.xlsx"
                iam_df.to_excel(folder_path / file_name)
            return folder_path
