from __future__ import annotations
import datetime
import glob
import importlib
import inspect
import logging
from pathlib import Path
import re
import yaml
import pandas as pd
import pypsa
import nomenclature
import pyam

from pypsa_validation_processing.utils import (
    EU27_COUNTRY_CODES,
    REGION_MAPPING,
    UNITS_MAPPING,
    MissingInputError,
)

logger = logging.getLogger(__name__)

# last group of exactly four digits not adjacent to other digits (C2.2)
_YEAR_IN_FILE_NAME = re.compile(r"(?<!\d)\d{4}(?!\d)")


def format_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize timestamp-like columns to tz-aware objects or
    formatted integers in UTC+00:00.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame whose columns may contain year strings, date strings, or
        timestamp-like values.

    Returns
    -------
    pd.DataFrame
        The same DataFrame with columns converted to Python ``datetime``
        objects localized to ``+00:00`` where possible for timeseries. For
        yearly aggregated data, columns are converted to integers.

    Notes
    -----
    Columns that cannot be parsed as timestamps are left unchanged. Values
    that can be parsed but cannot be localized are replaced with ``pd.NaT``
    and reported via logger warnings.
    Yearly aggregated data is identified by all column labels being
    4-digit year strings only. In this case, the columns are converted to
    integers. For non-aggregated data, columns are converted to Python
    ``datetime`` objects localized to UTC+00:00.
    """
    fixed_tz = datetime.timezone(datetime.timedelta(hours=0))

    cols = list(df.columns)
    idx_name = df.columns.name
    try:
        parsed = pd.to_datetime(cols, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(cols, errors="coerce")

    converted_list: list[object] = []
    nat_list: list[object] = []

    # for yearly aggregated data, use integers as column labels.
    if all([(isinstance(elem, str) and re.match(r"^\d{4}$", elem)) for elem in cols]):
        converted_list = [int(col) for col in cols]
        df.columns = pd.Index(converted_list, name=idx_name)
    # for non-aggregated data, use timestamps as column labels.
    else:
        for i, col in enumerate(cols):
            is_year_only = (
                isinstance(col, str) and re.match(r"^\d{4}$", col) is not None
            )
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
                logger.warning(
                    "format_timestamps: failed to localize column %r: %s. "
                    "Setting label to pd.NaT",
                    col,
                    exc,
                )
                ts_tz = pd.NaT
                nat_list.append(col)

            cols[i] = ts_tz
            if not pd.isna(ts_tz):
                converted_list.append(col)

        py_datetimes = pd.Index(cols, name=idx_name).to_pydatetime()
        df.columns = pd.Index(py_datetimes, dtype="object", name=idx_name)
    if nat_list:
        logger.warning("format_timestamps: columns set to NaT: %s", nat_list)
    return df


class Network_Processor:
    """Processes a PyPSA NetworkCollection against IAMC variable definitions.

    Reads variable definitions from a definitions folder, executes the
    corresponding statistics functions to extract values from a given PyPSA
    NetworkCollection, and returns the results as a pyam.IamDataFrame.

    Outputs are converted to the units of common definitions, set in the
    definitions variable in ``definitions_path`` via
    :meth:`pyam.IamDataFrame.convert_unit` if ``convert_units`` is ``True`` in config.

    If ``definitions_path`` is set to ``False`` (as a YAML bool or the string
    ``"False"``/``"false"``), definitions are disabled entirely: every
    variable in the mapping file (``mapping_path``) is evaluated regardless
    of whether it has a definitions-folder entry, and unit conversion is
    skipped.
    """

    def __init__(
        self,
        config_path: Path,
    ) -> None:
        """Initialize the processor from a YAML configuration file.

        Parameters
        ----------
        config_path : Path
            Path to the YAML configuration file used to configure the
            processor.

        Notes
        -----
        The configuration is expected to define the network results path,
        definitions path, country, model name, scenario name, and optional
        settings such as mapping, aggregation, output, and unit conversion
        behavior.

        ``definitions_path`` may also be set to ``False`` (YAML bool, or the
        string ``"False"``/``"false"``) to disable definitions entirely: all
        variables from the mapping file are evaluated and unit conversion is
        skipped.

        Raises
        ------
        ValueError
            If required configuration entries are missing or invalid, or if
            ``definitions_path`` is unset/empty.
        FileNotFoundError
            If the configured network results or definitions directories do
            not exist.
        """

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
        is_empty = definitions_path is None or (
            isinstance(definitions_path, str) and definitions_path.strip() == ""
        )
        if is_empty:
            raise ValueError(
                f"'definitions_path' not set in config at {self.config_path}. "
                "Set it to a valid definitions folder path, or to False to "
                "evaluate all variables from the mapping file without unit "
                "conversion."
            )

        self.use_definitions: bool = not self._is_definitions_disabled(definitions_path)

        if self.use_definitions:
            self.definitions_path: Path | None = Path(definitions_path)
            if not self.definitions_path.exists():
                raise FileNotFoundError(
                    f"Definition folder does not exist: {self.definitions_path}"
                )
        else:
            self.definitions_path = None

        if self.use_definitions and self.config.get("convert_units", True):
            self.common_dsd: nomenclature.DataStructureDefinition | None = (
                nomenclature.DataStructureDefinition(self.definitions_path)
            )
        else:
            self.common_dsd = None

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
        self.model_name_path_token: str = self._sanitize_path_token(self.model_name)
        self.scenario_name_path_token: str = self._sanitize_path_token(
            self.scenario_name
        )
        self.country_path_token: str = self._sanitize_path_token(self.country)
        self.network_collection = self._read_pypsa_network_collection()
        self.network_inputs: list[dict] = self._collect_network_inputs()
        self.dsd: nomenclature.DataStructureDefinition | None = (
            self.read_definitions() if self.use_definitions else None
        )
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
        self.map_country_codes_to_names: bool = self.config.get(
            "map_country_codes_to_names", True
        )
        if not isinstance(self.map_country_codes_to_names, bool):
            raise ValueError(
                f"Invalid map_country_codes_to_names: '{self.map_country_codes_to_names}'. "
                f"Must be true or false."
            )
        self._function_parameter_cache: dict[object, set[str]] = {}
        self.dsd_with_values: (
            pyam.IamDataFrame | list[tuple[int, pyam.IamDataFrame]] | None
        ) = None
        if self.country == "all":
            default_path_dsd_with_values = (
                Path(__file__).resolve().parent
                / "resources"
                / f"PYPSA_{self.model_name_path_token}_{self.scenario_name_path_token}.xlsx"
            )
        else:
            default_path_dsd_with_values = (
                Path(__file__).resolve().parent
                / "resources"
                / f"PYPSA_{self.model_name_path_token}_{self.scenario_name_path_token}_{self.country_path_token}.xlsx"
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
            f"  definitions_path: {self.definitions_path if self.use_definitions else 'False (all variables, no unit conversion)'}\n"
        )

    @staticmethod
    def _sanitize_path_token(value: str) -> str:
        """Strip and replace whitespace runs with underscores for path safety."""
        return re.sub(r"\s+", "_", value.strip())

    def _is_valid_country_identifier(self, country: str) -> bool:
        """Check if country is a valid ISO code or the special value 'all'."""
        return country == "all" or country in EU27_COUNTRY_CODES

    @staticmethod
    def _is_definitions_disabled(value: object) -> bool:
        """Check whether a definitions_path config value requests disabling definitions."""
        if isinstance(value, bool):
            return value is False
        if isinstance(value, str):
            return value.strip().lower() == "false"
        return False

    def _read_config(self) -> dict:
        """Read and return the YAML configuration file."""
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def _read_mappings(self) -> dict:
        """Read and return the YAML mapping file."""
        if not self.mappings_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {self.mappings_path}")
        with open(self.mappings_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _read_pypsa_network_collection(self) -> pypsa.NetworkCollection:
        """Reads in pypsa networks as NetworkCollection from network_results_path / networks.

        The sorted file paths are stored in ``self.network_files``, in the
        order of the networks in the collection.

        Raises
        ------
        FileNotFoundError
            If the ``networks`` folder does not exist or contains no ``.nc`` file.
        """
        nw_path = self.network_results_path / "networks"
        if not nw_path.is_dir():
            raise FileNotFoundError(f"Networks folder does not exist: {nw_path}")
        self.network_files: list[Path] = sorted(nw_path.glob("*.nc"))
        if not self.network_files:
            raise FileNotFoundError(f"No .nc files found in networks folder: {nw_path}")
        return pypsa.NetworkCollection(self.network_files)

    @staticmethod
    def _get_investment_year(n: pypsa.Network, label: str) -> int:
        """Return the investment year of a network (C2.2).

        Uses ``n.meta["wildcards"]["planning_horizons"]``, else
        ``n.meta["wildcards"]["horizon"]``, else the last four-digit group of
        the file name (with a WARNING).

        Parameters
        ----------
        n : pypsa.Network
            Network to inspect.
        label : str
            File name of the network, used for the fallback and in messages.

        Returns
        -------
        int
            The investment year.

        Raises
        ------
        ValueError
            If neither ``n.meta`` nor the file name holds a year.
        """
        wildcards = (getattr(n, "meta", None) or {}).get("wildcards") or {}
        for key in ("planning_horizons", "horizon"):
            if wildcards.get(key) is not None:
                return int(wildcards[key])
        matches = _YEAR_IN_FILE_NAME.findall(label)
        if not matches:
            raise ValueError(
                f"Cannot determine the investment year of network '{label}': "
                "no 'planning_horizons' or 'horizon' in n.meta['wildcards'] and "
                "no four-digit year in the file name."
            )
        year = int(matches[-1])
        logger.warning(
            "Network '%s' has no investment year in n.meta; using %s from the file name.",
            label,
            year,
        )
        return year

    @staticmethod
    def _stringify_keys(value: object) -> object:
        """Recursively convert all mapping keys to ``str`` (C2.3)."""
        if isinstance(value, dict):
            return {
                str(k): Network_Processor._stringify_keys(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [Network_Processor._stringify_keys(v) for v in value]
        return value

    def _get_energy_totals(
        self, n: pypsa.Network, config: dict | None, label: str
    ) -> pd.DataFrame | None:
        """Return the energy totals of one network, indexed by ``country`` (C2.4).

        Uses ``n.meta["resources"]["energy_totals"]`` (pandas ``split``
        orientation) if present, else the rows of
        ``<network_results_path>/resources/energy_totals.csv`` with
        ``year == config["energy"]["energy_totals_year"]``.

        Parameters
        ----------
        n : pypsa.Network
            Network to inspect.
        config : dict | None
            Network config of the same network (C2.3).
        label : str
            File name of the network, used in messages.

        Returns
        -------
        pd.DataFrame | None
            One row per country, or ``None`` (with a WARNING) if neither
            source is available or the CSV cannot be read.
        """
        resources = (getattr(n, "meta", None) or {}).get("resources") or {}
        table = resources.get("energy_totals")
        if table is not None:
            energy_totals = pd.DataFrame(
                data=table["data"], index=table["index"], columns=table["columns"]
            )
            energy_totals.index.name = "country"
            return energy_totals

        csv_path = self.network_results_path / "resources" / "energy_totals.csv"
        energy_config = (config or {}).get("energy")
        year = (
            energy_config.get("energy_totals_year")
            if isinstance(energy_config, dict)
            else None
        )
        if not csv_path.exists():
            missing = f"file {csv_path}"
        elif year is None:
            missing = "config key 'energy.energy_totals_year'"
        else:
            try:
                energy_totals = pd.read_csv(csv_path, index_col=["country", "year"])
            except Exception as exc:
                energy_totals = None
                missing = f"a readable file {csv_path} ({exc})"
            if energy_totals is not None:
                years = energy_totals.index.get_level_values("year")
                if int(year) in years:
                    return energy_totals.xs(int(year), level="year")
                missing = f"rows of year {year} in {csv_path}"
        logger.warning(
            "Network '%s': no energy totals available (missing %s). Variables "
            "whose function declares 'energy_totals' are skipped.",
            label,
            missing,
        )
        return None

    def _collect_network_inputs(self) -> list[dict]:
        """Determine investment year, config and energy totals per network.

        Returns
        -------
        list[dict]
            One dict per network of ``self.network_collection`` (same order)
            with keys ``investment_year``, ``config`` and ``energy_totals``.

        Raises
        ------
        ValueError
            If an investment year cannot be determined or occurs twice.
        """
        inputs: list[dict] = []
        for i in range(len(self.network_collection)):
            n = self.network_collection[i]
            files = self.network_files
            label = files[i].name if i < len(files) else str(n.name)
            year = self._get_investment_year(n, label)
            config = self._get_network_config(n, year)
            inputs.append(
                {
                    "investment_year": year,
                    "config": config,
                    "energy_totals": self._get_energy_totals(n, config, label),
                }
            )
        years = [entry["investment_year"] for entry in inputs]
        duplicates = sorted({year for year in years if years.count(year) > 1})
        if duplicates:
            raise ValueError(
                f"Several networks in {self.network_results_path / 'networks'} "
                f"have the same investment year: {duplicates}"
            )
        return inputs

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
        self,
        variable: str,
        n: pypsa.Network,
        config: dict | None = None,
        energy_totals: pd.DataFrame | None = None,
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
            Network config of the corresponding investment year.
            Passed to the statistics function only if the function's
            signature includes a ``config`` parameter.
        energy_totals : pd.DataFrame | None, optional
            Energy totals of the corresponding investment year.
            Passed only if the function's signature includes an
            ``energy_totals`` parameter.

        Returns
        -------
        pd.Series | None
            Computed values for the variable, or ``None`` if no function
            is registered for it, if a declared input (``config``,
            ``energy_totals``) is ``None``, or if the function raises
            :class:`~pypsa_validation_processing.utils.MissingInputError`.
            Each skip is logged as WARNING.
        """
        func_name = self.functions_dict.get(variable)
        if func_name is None:
            return None

        stats_module = importlib.import_module(
            "pypsa_validation_processing.statistics_functions"
        )
        func = getattr(stats_module, func_name, None)
        if func is None:
            logger.warning(
                "Variable %s: Function '%s' not found in statistics_functions.py",
                variable,
                func_name,
            )
            return None

        params = self._function_parameter_cache.get(func)
        if params is None:
            params = set(inspect.signature(func).parameters)
            self._function_parameter_cache[func] = params
        kwargs: dict = {}
        if "aggregate_per_year" in params:
            kwargs["aggregate_per_year"] = self.aggregate_per_year
        for name, value in (("config", config), ("energy_totals", energy_totals)):
            if name not in params:
                continue
            if value is None:
                logger.warning(
                    "Variable %s: skipped, function '%s' declares '%s' but it is "
                    "not available for this network.",
                    variable,
                    func_name,
                    name,
                )
                return None
            kwargs[name] = value

        try:
            return func(n, **kwargs)
        except MissingInputError as exc:
            logger.warning(
                "Variable %s: skipped, function '%s' is missing input '%s'.",
                variable,
                func_name,
                exc,
            )
            return None

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
        When ``aggregation_level="country"``, region labels are country codes by
        default. If ``map_country_codes_to_names`` is ``True`` in config, country
        codes are mapped to full names via :data:`REGION_MAPPING`. For
        ``country="all"``, the ``country`` column in *df* (populated by
        :meth:`_aggregate_to_country`) is used as the region dimension, one row
        per country. When ``aggregation_level="region"``, the ``location`` column
        in *df* is used directly.
        """
        df = format_timestamps(df)
        # add 'variable' and 'unit' columns
        df = df.reset_index()
        # rename columns if needed
        col_renaming_dict = {
            "variable": "variable_name",
            "unit": "unit_pypsa",
            "country": "location",
        }
        df = df.rename(
            columns={k: v for k, v in col_renaming_dict.items() if k in df.columns}
        )

        if self.aggregation_level == "country" and self.country != "all":
            df["location"] = self.country

        if self.map_country_codes_to_names:
            # Map 2-letter country codes and nuts2 / nuts3 regions code
            # to full names (en for country-codes, de for nuts2/nuts3)
            df["location"] = df["location"].map(lambda c: REGION_MAPPING.get(c, c))

        if self.aggregation_level == "country":
            if self.country == "all":

                dsd = pyam.IamDataFrame(
                    data=df.drop_duplicates(),
                    model=self.model_name,
                    scenario=self.scenario_name,
                    region="location",
                    variable="variable_name",
                    unit="unit_pypsa",
                )
            else:
                dsd = pyam.IamDataFrame(
                    data=df.drop_duplicates(),
                    model=self.model_name,
                    scenario=self.scenario_name,
                    region="location",
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
        """Processes unit conversion from current unit to units defined in ``self.common_dsd`` if configured.
        Leaves the structure unchanged. Leaves the IamDataFrame unchanged if ``self.common_dsd`` is not initialized.

        Parameters
        ----------
        iam_df : pyam.IamDataFrame
            The IamDataFrame to process for unit conversion.

        Returns
        -------
        pyam.IamDataFrame
            The processed IamDataFrame.

        Raises
        ------
        ValueError
            If the IamDataFrame contains multiple units for a single variable.
        ValueError
            If the IamDataFrame contains no units for a single variable.
        ValueError
            If the IamDataFrame contains no units for a single variable.
        RuntimeError
            If ``self.common_dsd`` is not initialized.
        """
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
        """Reads the unit from the common definitions and returns it for a given variable

        Parameters
        ----------
        variable : str
            The variable name for which to retrieve the unit.

        Returns
        -------
        str
            The unit for the given variable.

        Raises
        ------
        KeyError
            If the variable is not found in the common definitions.
        KeyError
            If the unit is not found for the variable in the common definitions.
        RuntimeError
            If ``self.common_dsd`` is not initialized.

        Notes
        -----
        If multiple units are defined for one variable (in one entry of this variable!),
        the first one of these variables is taken. If there are more then one definitions for
        the searched variable, the first entry is taken and a warning is logged.
        """
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
            logger.warning(
                "Multiple definitions found for variable '%s' in common definitions. Take first one: %s",
                variable,
                match.iloc[0],
            )

        target_unit = match.iloc[0][unit_col]
        if pd.isna(target_unit):
            raise KeyError(
                f"Unit information not found for variable '{variable}' in common definitions."
            )
        if ("[" in target_unit) and ("]" in target_unit) and ("," in target_unit):
            logger.info(
                "Several possible units defined for variable '%s' in common definitions. Take first one:",
                variable,
            )
            try:
                import ast

                target_unit = ast.literal_eval(target_unit)[0]
                logger.info(target_unit)
            except Exception as exc:
                logger.warning(
                    "Failed to parse multiple units for variable '%s': %s. Using TJ as unit.",
                    variable,
                    exc,
                )
                target_unit = "TJ"
        return str(target_unit)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Return *base* updated recursively with *override* (override wins)."""
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = Network_Processor._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _read_network_config_file(
        self, investment_year: int, log_level: int
    ) -> dict | None:
        """Read ``<network_results_path>/configs/config*<year>.yaml``.

        Parameters
        ----------
        investment_year : int
            Investment year used in the file pattern.
        log_level : int
            Logging level for problems (no file, several files, unreadable
            file, root not a mapping).

        Returns
        -------
        dict | None
            Content of the first matching file in lexicographic order, or
            ``None`` if no file matches, it cannot be read or its root is not
            a mapping.
        """
        config_pattern = str(
            self.network_results_path / "configs" / f"config*{investment_year}.yaml"
        )
        matching_files = sorted(glob.glob(config_pattern))
        if not matching_files:
            logger.log(
                log_level,
                "No config file found for investment year %s at pattern '%s'",
                investment_year,
                config_pattern,
            )
            return None
        selected_config_file = matching_files[0]
        if len(matching_files) > 1:
            logger.log(
                log_level,
                "Multiple config files found for investment year %s: %s; using '%s'",
                investment_year,
                matching_files,
                selected_config_file,
            )
        try:
            with open(selected_config_file, "r") as f:
                network_config = yaml.safe_load(f)
        except Exception as exc:
            logger.log(
                log_level,
                "Could not load config file '%s': %s",
                selected_config_file,
                exc,
            )
            return None
        if not isinstance(network_config, dict):
            logger.log(
                log_level,
                "Config file '%s' is not a mapping (got %s); it is ignored.",
                selected_config_file,
                type(network_config).__name__,
            )
            return None
        return network_config

    def _get_network_config(
        self, n: pypsa.Network, investment_year: int
    ) -> dict | None:
        """Return the network config of one network (C2.3).

        ``n.meta`` without ``wildcards`` and ``resources`` is deep-merged
        over the content of ``<network_results_path>/configs/config*<year>.yaml``:
        values in ``n.meta`` win, keys missing from ``n.meta`` are taken from
        the file.

        Parameters
        ----------
        n : pypsa.Network
            Network whose ``n.meta`` is used.
        investment_year : int
            Investment year of *n*, used to find the config file.

        Returns
        -------
        dict | None
            The merged config with all mapping keys converted to ``str``, or
            ``None`` if neither ``n.meta`` nor a readable config file holds
            any config.

        Notes
        -----
        Problems with the config file (none, several, unreadable, root not a
        mapping) are logged as WARNING if ``n.meta`` holds no config, else as
        INFO.
        """
        meta = getattr(n, "meta", None) or {}
        meta_config = self._stringify_keys(
            {k: v for k, v in meta.items() if k not in ("wildcards", "resources")}
        )
        file_config = self._stringify_keys(
            self._read_network_config_file(
                investment_year, logging.INFO if meta_config else logging.WARNING
            )
        )
        if not meta_config and file_config is None:
            return None
        return self._deep_merge(file_config or {}, meta_config)

    def calculate_variables_values(self) -> None:
        """Calculate values for all defined variables.

        Iterates over all variables in ``self.dsd`` (or, when
        ``self.use_definitions`` is ``False``, over every variable in
        ``self.functions_dict``), calls :meth:`_execute_function_for_variable`
        for each one, and assembles the results.

        When ``self.aggregate_per_year`` is ``True`` (default), assembles a
        single :class:`pyam.IamDataFrame` with one column per investment year
        and stores it in ``self.dsd_with_values``.

        When ``self.aggregate_per_year`` is ``False``, stores a
        ``list[tuple[int, pyam.IamDataFrame]]`` in ``self.dsd_with_values``,
        one entry per investment year.  Each :class:`pyam.IamDataFrame`
        contains the full time-series for that year.

        Applies aggregation based on ``self.aggregation_level`` config.

        Raises
        ------
        RuntimeError
            If no variable produced values for any network.
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
            network_inputs = self.network_inputs[i]
            investment_year = network_inputs["investment_year"]

            variables = (
                self.dsd.variable.to_pandas()["variable"]
                if self.use_definitions
                else list(self.functions_dict.keys())
            )
            results = []
            for variable in variables:
                result = self._execute_function_for_variable(
                    variable,
                    n,
                    config=network_inputs["config"],
                    energy_totals=network_inputs["energy_totals"],
                )
                if result is not None:
                    # if aggregate_per_year, function returns a Series - convert to DataFrame.
                    if self.aggregate_per_year == True:
                        result = result.to_frame(name="value")
                    elif not isinstance(result, pd.DataFrame):
                        raise RuntimeError(
                            f"Expected DataFrame for variable '{variable}' when aggregate_per_year=False, got {type(result)}"
                        )
                    results.append(
                        self._postprocess_statistics_result(variable, result)
                    )

            if results:
                year_df = pd.concat(results, ignore_index=False)
                if self.aggregate_per_year:
                    year_df.rename(
                        columns={"value": str(investment_year)}, inplace=True
                    )
                    container_investment_years.append(year_df)
                else:
                    # Replace the year component of each snapshot timestamp with
                    # the investment year so that e.g. 2019-01-01 becomes 2050-01-01.
                    year_df.columns = year_df.columns.map(
                        lambda ts: ts.replace(year=int(investment_year))
                    )
                    iam_df = self.structure_pyam_from_pandas(year_df)
                    container_investment_years.append((investment_year, iam_df))

        if not container_investment_years:
            raise RuntimeError(
                "No variable produced values for any network in "
                f"{self.network_results_path / 'networks'}; see the warnings above."
            )
        if self.aggregate_per_year:
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
            base_filename = (
                f"PYPSA_{self.model_name_path_token}_{self.scenario_name_path_token}"
            )
        else:
            base_filename = f"PYPSA_{self.model_name_path_token}_{self.scenario_name_path_token}_{self.country_path_token}"

        if self.aggregate_per_year:
            file_path = base_dir / f"{base_filename}.xlsx"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self.dsd_with_values.to_excel(file_path)
            return file_path
        else:
            if self.country == "all":
                folder_name = f"PYPSA_timeseries_{self.model_name_path_token}_{self.scenario_name_path_token}"
            else:
                folder_name = f"PYPSA_timeseries_{self.model_name_path_token}_{self.scenario_name_path_token}_{self.country_path_token}"
            folder_path = base_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            for investment_year, iam_df in self.dsd_with_values:
                file_name = f"{base_filename}_{investment_year}.xlsx"
                iam_df.to_excel(folder_path / file_name)
            return folder_path
