from __future__ import annotations

from pathlib import Path
import yaml
import nomenclature
import pyam


class Network_Processor:
    """Processes a PyPSA NetworkCollection against IAMC variable definitions.

    Reads variable definitions from a definitions folder, executes the
    corresponding statistics functions to extract values from a given PyPSA
    NetworkCollection, and returns the results as a pyam.IamDataFrame.
    """

    def __init__(
        self,
        config_path: str | Path,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = self._read_config()

        network_results_path = self.config.get("network_results_path")
        if network_results_path is None:
            raise ValueError(
                f"'network_results_path' not set in config at {self.config_path}"
            )
        self.network_results_path: Path = Path(network_results_path)

        self.definitions_path: Path = Path(self.config["definition_path"])
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

        self.country: str = self.config.get("country", "")
        self.network_collection = None
        self.dsd: nomenclature.DataStructureDefinition | None = None
        self.functions_dict: dict[str, str | list] = {}
        self.dsd_with_values: pyam.IamDataFrame | None = None

    def __repr__(self) -> str:
        return (
            f"Network_Processor\n"
            f"  country: {self.country}\n"
            f"  network_results_path: {self.network_results_path}\n"
            f"  definitions_path: {self.definitions_path}\n"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def read_definitions(self) -> nomenclature.DataStructureDefinition:
        """Read IAMC variable definitions from the definitions folder.

        Populates ``self.dsd`` with a
        :class:`nomenclature.DataStructureDefinition` built from
        ``self.definitions_path`` and also populates ``self.functions_dict``
        from the mapping file so that each variable name is associated with
        the name of its corresponding statistics function.

        Returns
        -------
        nomenclature.DataStructureDefinition
            The loaded data structure definition.
        """
        self.dsd = nomenclature.DataStructureDefinition(self.definitions_path)
        self.functions_dict = self._read_mappings()
        return self.dsd

    def _execute_function_for_variable(
        self, variable: str
    ) -> pyam.IamDataFrame | None:
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
        pyam.IamDataFrame | None
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
            raise AttributeError(
                f"Function '{func_name}' not found in statistics_functions.py"
            )
        return func(self.network_collection)

    def calculate_variables_values(self) -> pyam.IamDataFrame:
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
        if self.dsd is None:
            self.read_definitions()

        results = []
        for variable in self.dsd.variable.to_pandas()["variable"]:
            result = self._execute_function_for_variable(variable)
            if result is not None:
                results.append(result)

        if results:
            self.dsd_with_values = pyam.concat(results)
        else:
            self.dsd_with_values = None

        return self.dsd_with_values

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
