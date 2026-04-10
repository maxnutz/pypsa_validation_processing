from __future__ import annotations
import glob
import importlib
import inspect
import os
from pathlib import Path
import yaml
import pandas as pd
import pypsa
import nomenclature
import pyam

from pypsa_validation_processing.utils import EU27_COUNTRY_CODES, UNITS_MAPPING


class Network_Processor:
    """Processes a PyPSA NetworkCollection against IAMC variable definitions.

    Reads variable definitions from a definitions folder, executes the
    corresponding statistics functions to extract values from a given PyPSA
    NetworkCollection, and returns the results as a pyam.IamDataFrame.
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

        definitions_path = self.config.get("definitions_path")
        if definitions_path is None:
            raise ValueError(
                f"'definition_path' not set in config at {self.config_path}"
            )
        self.definitions_path: Path = Path(definitions_path)
        if not self.definitions_path.exists():
            raise FileNotFoundError(
                f"Definition folder does not exist: {self.definitions_path}"
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
        if self.country == None:
            raise ValueError(f"'country' not set in config at {self.config_path}")
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
        self.dsd_with_values: pyam.IamDataFrame | None = None
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
            f"  network_results_path: {self.network_results_path}\n"
            f"  definitions_path: {self.definitions_path}\n"
        )

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

        if "config" in inspect.signature(func).parameters:
            return func(n, config=config)
        return func(n)

    def _aggregate_to_country(self, result: pd.Series) -> pd.Series:
        """Aggregate a regional Series to country level by summing all regions.

        Parameters
        ----------
        result : pd.Series
            Series with MultiIndex containing at least ``location`` and ``unit``
            levels, as returned by statistics functions.

        Returns
        -------
        pd.Series
            Series with MultiIndex containing only the ``unit`` level.
        """
        mask = result.index.get_level_values("location").isin(
            [
                reg
                for reg in result.index.get_level_values("location")
                if reg.startswith(self.country)
            ]
        )
        return result.loc[mask].groupby("unit").sum()

    def _filter_to_regions(self, result: pd.Series) -> pd.Series:
        """Filter a regional Series to the all regions of the given country.

        Parameters
        ----------
        result : pd.Series
            Series with MultiIndex containing at least ``location`` and ``unit``
            levels, as returned by statistics functions.

        Returns
        -------
        pd.Series
            Series with MultiIndex containing levels ``location`` and ``unit``."""

        mask = result.index.get_level_values("location").isin(
            [
                reg
                for reg in result.index.get_level_values("location")
                if reg.startswith(self.country)
            ]
        )
        return result.loc[mask]

    def _postprocess_statistics_result(
        self, variable: str, result: pd.Series
    ) -> pd.DataFrame:
        """Format a statistics-function result into a DataFrame.

        Applies aggregation based on ``self.aggregation_level``:

        - ``"country"``: sums all regions via :meth:`_aggregate_to_country`,
          then returns a DataFrame grouped by ``["variable", "unit"]``.
        - ``"region"``: keeps all regions, returns a DataFrame grouped
          by ``["variable", "location", "unit"]``.

        Parameters
        ----------
        variable : str
            IAMC variable name.
        result : pd.Series
            Series with MultiIndex ``["location", "unit"]`` (plus possible extra
            levels) as returned by statistics functions.

        Returns
        -------
        pd.DataFrame
            DataFrame with ``variable``, ``unit`` (and ``location`` when
            ``aggregation_level="region"``), and ``value`` columns,
            grouped accordingly.
        """
        if self.aggregation_level == "country":
            aggregated_df = self._aggregate_to_country(result)
            df = pd.DataFrame(
                {
                    "variable": [variable] * len(aggregated_df),
                    "unit": list(
                        aggregated_df.index.get_level_values("unit").map(UNITS_MAPPING)
                    ),
                    "value": list(aggregated_df.values),
                }
            )
            df = df.groupby(["variable", "unit"]).sum()
        else:
            # region: preserve regional granularity
            filtered_df = self._filter_to_regions(result)
            df = pd.DataFrame(
                {
                    "variable": [variable] * len(filtered_df),
                    "location": list(filtered_df.index.get_level_values("location")),
                    "unit": list(
                        filtered_df.index.get_level_values("unit").map(UNITS_MAPPING)
                    ),
                    "value": list(filtered_df.values),
                }
            )
            df = df.groupby(["variable", "location", "unit"]).sum()
        return df

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
        When ``aggregation_level="country"``, the region is set to the full
        country name from :data:`EU27_COUNTRY_CODES`.  When
        ``aggregation_level="region"``, the ``location`` column in *df*
        is used directly.
        """
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
        # perform unit conversion

        return dsd

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
        the results into a single :class:`pyam.IamDataFrame` stored in
        ``self.dsd_with_values``. Applies aggregation based on
        ``self.aggregation_level`` config.

        Returns
        -------
        pyam.IamDataFrame
            Combined results for all variables that have a registered function.
        """
        merge_keys = (
            ["variable", "unit"]
            if self.aggregation_level == "country"
            else ["variable", "location", "unit"]
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
                    results.append(
                        self._postprocess_statistics_result(variable, result)
                    )

            if results:
                year_df = pd.concat(results, ignore_index=False)
                year_df.rename(columns={"value": str(investment_year)}, inplace=True)
                container_investment_years.append(year_df)
        if len(container_investment_years) > 0:
            ds_with_values = container_investment_years[0]
        if len(container_investment_years) > 1:
            for year_df in container_investment_years[1:]:
                ds_with_values = ds_with_values.merge(
                    year_df, on=merge_keys, how="outer"
                )

        self.dsd_with_values = self.structure_pyam_from_pandas(ds_with_values)

    def write_output_to_xlsx(self, output_path: str | Path | None = None) -> Path:
        """Write the computed IAMC data to an Excel file.

        Parameters
        ----------
        output_path : str | Path | None, optional
            Destination file path. If ``None``, a default path inside
            ``resources/`` is used.

        Returns
        -------
        Path
            Path to the written Excel file.

        Raises
        ------
        RuntimeError
            If :meth:`calculate_variables_values` has not been called yet.
        """
        if self.dsd_with_values is None:
            raise RuntimeError(
                "No data available. Call calculate_variables_values() first."
            )

        if output_path is None:
            output_path = Path("resources") / f"pypsa_validation_{self.country}.xlsx"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.dsd_with_values.to_excel(output_path)
        return output_path
