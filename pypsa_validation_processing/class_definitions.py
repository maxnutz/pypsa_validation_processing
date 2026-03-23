from __future__ import annotations
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
        self, variable: str, n: pypsa.Network
    ) -> pd.Series | None:
        """Look up and execute the statistics function for a single variable.

        Looks up *variable* in ``self.functions_dict``, imports the
        corresponding function from :mod:`pypsa_validation_processing.statistics_functions`,
        calls it with ``self.network_collection``, and returns the result.

        Parameters
        ----------
        variable : str
            IAMC variable name to process.

        Returns
        -------
        pd.Series | None
            Computed values for the variable, or ``None`` if no function
            is registered for it.
        """
        import importlib

        func_name = self.functions_dict.get(variable)
        if func_name is None:
            return None

        stats_module = importlib.import_module(
            "pypsa_validation_processing.statistics_functions"
        )
        func = getattr(stats_module, func_name, None)
        if func is None:
            print(
                f"WARNING: Variable {variable}: No function '{func_name}' not found in statistics_functions.py"
            )
            return None
        return func(n)

    def _postprocess_statistics_result(
        self, variable: str, result: pd.Series
    ) -> pd.DataFrame:
        """Formatting and creating a pandas dataframe from results Series and variable_name"""

        return pd.DataFrame(
            {
                "variable": [variable] * len(list(result.values)),
                "unit": list(result.index.get_level_values("unit")),
                "value": list(result.values),
            }
        )

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
        """
        # rename columns if needed
        col_renaming_dict = {
            "variable": "variable_name",
            "unit": "unit_pypsa",
        }
        df = df.rename(
            columns={k: v for k, v in col_renaming_dict.items() if k in df.columns}
        )
        df["unit_pypsa"] = df["unit_pypsa"].map(UNITS_MAPPING)
        # drop columns not needed

        # initialize pyam.IamDataFrame
        dsd = pyam.IamDataFrame(
            data=df.drop_duplicates(),
            model=self.model_name,
            scenario=self.scenario_name,
            region=EU27_COUNTRY_CODES.get(self.country, self.country),
            variable="variable_name",
            unit="unit_pypsa",
        )
        # perform unit conversion

        return dsd

    def calculate_variables_values(self) -> None:
        """Calculate values for all defined variables.

        Iterates over all variables in ``self.dsd``, calls
        :meth:`_execute_function_for_variable` for each one, and assembles
        the results into a single :class:`pyam.IamDataFrame` stored in
        ``self.dsd_with_values``.

        Returns
        -------
        pyam.IamDataFrame
            Combined results for all variables that have a registered function.
        """
        container_investment_years = []
        for i in range(0, self.network_collection.__len__()):
            n = self.network_collection[i]
            investment_year = n.meta["wildcards"]["planning_horizons"]
            results = []
            for variable in self.dsd.variable.to_pandas()["variable"]:
                result = self._execute_function_for_variable(variable, n)
                if result is not None:
                    results.append(
                        self._postprocess_statistics_result(variable, result)
                    )

            if results:
                year_df = pd.concat(results, ignore_index=True)
                year_df.rename(columns={"value": str(investment_year)}, inplace=True)
                container_investment_years.append(year_df)
        if len(container_investment_years) < 0:
            ds_with_values = container_investment_years[0]
        if len(container_investment_years) > 1:
            for year_df in container_investment_years[1:]:
                ds_with_values = ds_with_values.merge(
                    year_df, on=["variable", "unit"], how="outer"
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
