from __future__ import annotations

import copy
import os
import pathlib
import re
from itertools import product
from typing import Any

import pypsa
import yaml


class Processor:
    def __init__(
        self,
        network_results_path: pathlib.Path,
        definitions_path: pathlib.Path,
        mappings_path: pathlib.Path,
        statements_path: pathlib.Path | None = None,
    ) -> None:
        self.network_results_path = network_results_path
        self.definitions_path = definitions_path
        self.mappings_path = mappings_path
        self.statements_path = statements_path
        self.statements_dict = self.read_statements_from_config()
        self.country = "AT"  # TODO: read from config

    def __repr__(self) -> str:
        return (
            f"Processor(network_results_path={self.network_results_path}, "
            f"definitions_path={self.definitions_path}, "
            f"mappings_path={self.mappings_path}, country={self.country})"
        )

    @classmethod
    def process(
        cls,
        network_results_path: pathlib.Path,
        definitions_path: pathlib.Path,
        mappings_path: pathlib.Path,
        statements_path: pathlib.Path | None = None,
    ) -> "Variable_Processor":
        """Create a variable processor.

        Parameters
        ----------
        network_results_path : pathlib.Path
            Path to network outputs.
        definitions_path : pathlib.Path
            Path to IAMC nomenclature definitions.
        mappings_path : pathlib.Path
            Path to mapping YAML file.
        statements_path : pathlib.Path | None, optional
            Optional path to precomputed statement definitions.

        Returns
        -------
        Variable_Processor
            Processor instance for mapping variable definitions to statistics inputs.
        """
        return Variable_Processor(
            network_results_path=network_results_path,
            definitions_path=definitions_path,
            mappings_path=mappings_path,
            statements_path=statements_path,
        )

    def variables_already_processed(self) -> bool:
        """Check whether variable statements are already processed.

        Returns
        -------
        bool
            True if `statements_path` exists, otherwise False.
        """
        if self.statements_path is None:
            return False
        return os.path.exists(self.statements_path)

    def read_statements_from_config(self) -> dict[str, Any]:
        """Read mapping configuration from YAML.

        Returns
        -------
        dict[str, Any]
            Parsed YAML mapping dictionary.
        """
        mapping_path = self.mappings_path
        if not mapping_path.is_absolute():
            package_root = pathlib.Path(__file__).resolve().parents[1]
            mapping_path = package_root / mapping_path

        if not mapping_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

        with open(mapping_path, "r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Invalid mapping structure in '{mapping_path}'.")
        return data

    def write_output_to_xlsx(self) -> None:
        "Writes the results to an IAMC-formattedExcel file"
        pass


class Variable_Processor(Processor):
    def __init__(
        self,
        network_results_path: pathlib.Path,
        definitions_path: pathlib.Path,
        mappings_path: pathlib.Path,
        statements_path: pathlib.Path | None = None,
    ) -> None:
        super().__init__(
            network_results_path=network_results_path,
            definitions_path=definitions_path,
            mappings_path=mappings_path,
            statements_path=statements_path,
        )

    def run(self) -> None:
        """Executes Variable Processor"""
        print("INFO: creating statistics statements from variable definitions...")

        # chain the Network_Processor
        network_processor = Network_Processor(self)
        network_processor.run()

    @staticmethod
    def _template_to_regex(template: str) -> tuple[re.Pattern[str], list[str]]:
        placeholder_names = re.findall(r"\{([^}]+)\}", template)
        pattern = "^" + re.escape(template) + "$"
        for placeholder in placeholder_names:
            pattern = pattern.replace(
                re.escape("{" + placeholder + "}"),
                "(?P<" + placeholder.replace(" ", "_") + ">.+?)",
                1,
            )
        return re.compile(pattern), placeholder_names

    def _match_variable_template(
        self, variable_name: str
    ) -> tuple[str, dict[str, str]]:
        templates = self.statements_dict.get("templates", {})
        for template in templates:
            regex, placeholders = self._template_to_regex(template)
            match = regex.match(variable_name)
            if match:
                values: dict[str, str] = {}
                for placeholder in placeholders:
                    values[placeholder] = match.group(placeholder.replace(" ", "_"))
                return template, values
        raise KeyError(f"No template found for variable '{variable_name}'.")

    @staticmethod
    def _deep_format(obj: Any, placeholder_values: dict[str, str]) -> Any:
        if isinstance(obj, str):
            return obj.format(**placeholder_values)
        if isinstance(obj, list):
            return [Variable_Processor._deep_format(item, placeholder_values) for item in obj]
        if isinstance(obj, dict):
            return {
                key: Variable_Processor._deep_format(value, placeholder_values)
                for key, value in obj.items()
            }
        return obj

    def _selector_by_reference(
        self, selector_reference: str, placeholder_values: dict[str, str]
    ) -> dict[str, Any]:
        selectors = self.statements_dict.get("selectors", {})
        expanded_reference = selector_reference.format(**placeholder_values)
        reference_parts = expanded_reference.split(".")

        cursor: Any = selectors
        for part in reference_parts:
            if not isinstance(cursor, dict) or part not in cursor:
                raise KeyError(
                    f"Selector reference '{expanded_reference}' could not be resolved."
                )
            cursor = cursor[part]

        if not isinstance(cursor, dict):
            raise ValueError(
                f"Selector '{expanded_reference}' is not a dictionary structure."
            )

        return self._deep_format(copy.deepcopy(cursor), placeholder_values)

    @staticmethod
    def _normalize_parameter_set(parameter_set: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(parameter_set)
        normalized.setdefault("components", [])
        normalized.setdefault("carrier", [])
        normalized.setdefault("bus_carrier", [])
        normalized.setdefault("at_port", None)
        return normalized

    def _selector_parameter_sets(self, selector_block: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract parameter sets from selector blocks.

        If `parameter_sets` is empty, this method tries to construct one fallback
        set from `uniqueness_extensions` so unresolved mappings still carry an
        explicit disambiguation definition.
        """
        parameter_sets = selector_block.get("parameter_sets", [])
        if parameter_sets:
            return [self._normalize_parameter_set(item) for item in parameter_sets]

        uniqueness_extensions = selector_block.get("uniqueness_extensions", {})
        if not isinstance(uniqueness_extensions, dict) or not uniqueness_extensions:
            return []

        fallback = self._normalize_parameter_set(dict(uniqueness_extensions))
        return [fallback]

    @staticmethod
    def _deduplicate_parameter_sets(
        parameter_sets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        deduplicated: list[dict[str, Any]] = []
        fingerprints: set[str] = set()
        for parameter_set in parameter_sets:
            serialized = yaml.safe_dump(parameter_set, sort_keys=True)
            if serialized not in fingerprints:
                fingerprints.add(serialized)
                deduplicated.append(parameter_set)
        return deduplicated

    @staticmethod
    def _set_intersection(left: list[str], right: list[str]) -> list[str]:
        if not left:
            return list(right)
        if not right:
            return list(left)
        return sorted(set(left).intersection(right))

    @classmethod
    def _combine_intersection(
        cls, left: dict[str, Any], right: dict[str, Any]
    ) -> dict[str, Any] | None:
        left_n = cls._normalize_parameter_set(left)
        right_n = cls._normalize_parameter_set(right)

        components = cls._set_intersection(
            list(left_n["components"]), list(right_n["components"])
        )
        carrier = cls._set_intersection(list(left_n["carrier"]), list(right_n["carrier"]))
        bus_carrier = cls._set_intersection(
            list(left_n["bus_carrier"]), list(right_n["bus_carrier"])
        )

        at_port_left = left_n["at_port"]
        at_port_right = right_n["at_port"]
        if at_port_left is None:
            at_port = at_port_right
        elif at_port_right is None:
            at_port = at_port_left
        elif at_port_left == at_port_right:
            at_port = at_port_left
        else:
            return None

        if left_n["components"] and right_n["components"] and not components:
            return None
        if left_n["carrier"] and right_n["carrier"] and not carrier:
            return None
        if left_n["bus_carrier"] and right_n["bus_carrier"] and not bus_carrier:
            return None

        merged: dict[str, Any] = {
            "components": components,
            "carrier": carrier,
            "bus_carrier": bus_carrier,
            "at_port": at_port,
        }

        for source in (left_n, right_n):
            for key, value in source.items():
                if key in {"components", "carrier", "bus_carrier", "at_port"}:
                    continue
                if key not in merged:
                    merged[key] = value
                elif merged[key] != value:
                    merged[key] = [merged[key], value]
        return merged

    def _resolve_from_selectors(
        self,
        selector_references: list[str],
        combine: str,
        placeholder_values: dict[str, str],
    ) -> list[dict[str, Any]]:
        selector_parameter_sets: list[list[dict[str, Any]]] = []

        for selector_reference in selector_references:
            selector_block = self._selector_by_reference(
                selector_reference, placeholder_values
            )
            selector_parameter_sets.append(self._selector_parameter_sets(selector_block))

        if not selector_parameter_sets:
            return []

        if combine == "union":
            flattened = [item for subset in selector_parameter_sets for item in subset]
            return self._deduplicate_parameter_sets(flattened)

        if combine == "intersection":
            result_sets = selector_parameter_sets[0]
            for next_sets in selector_parameter_sets[1:]:
                combined: list[dict[str, Any]] = []
                for left_set, right_set in product(result_sets, next_sets):
                    merged = self._combine_intersection(left_set, right_set)
                    if merged is not None:
                        combined.append(merged)
                result_sets = self._deduplicate_parameter_sets(combined)
            return result_sets

        raise ValueError(f"Unsupported combine mode '{combine}'.")

    def get_variable_parameter_mapping(self, variable_name: str) -> dict[str, Any]:
        """Resolve one IAMC variable into statistics statement parameter sets.

        Parameters
        ----------
        variable_name : str
            IAMC variable to resolve.

        Returns
        -------
        dict[str, Any]
            Resolution result with template and list of parameter sets.
        """
        template_name, placeholder_values = self._match_variable_template(variable_name)
        template_cfg = copy.deepcopy(
            self.statements_dict.get("templates", {}).get(template_name, {})
        )
        if not isinstance(template_cfg, dict):
            raise ValueError(f"Template '{template_name}' must map to a dictionary.")

        template_cfg = self._deep_format(template_cfg, placeholder_values)
        mode = template_cfg.get("mode", "direct")
        combine = template_cfg.get("combine", "union")

        parameter_sets: list[dict[str, Any]] = []
        if mode == "direct":
            if template_cfg.get("parameter_sets", []):
                parameter_sets = [
                    self._normalize_parameter_set(item)
                    for item in template_cfg.get("parameter_sets", [])
                ]
            elif template_cfg.get("uniqueness_extensions", {}):
                parameter_sets = [
                    self._normalize_parameter_set(
                        dict(template_cfg.get("uniqueness_extensions", {}))
                    )
                ]
        elif mode == "composed":
            selector_references: list[str] = []
            if "from_selectors" in template_cfg:
                selector_references.extend(template_cfg.get("from_selectors", []))
            if "from_selector_template" in template_cfg:
                selector_references.append(template_cfg["from_selector_template"])
            if "from_selector_templates" in template_cfg:
                selector_references.extend(template_cfg["from_selector_templates"])
            parameter_sets = self._resolve_from_selectors(
                selector_references=selector_references,
                combine=combine,
                placeholder_values=placeholder_values,
            )
        else:
            raise ValueError(f"Unsupported template mode '{mode}'.")

        return {
            "variable": variable_name,
            "template": template_name,
            "placeholders": placeholder_values,
            "status": template_cfg.get("status", "draft"),
            "positive_values": self.statements_dict.get("pypsa_statistics_defaults", {})
            .get("positive_values", True),
            "parameter_sets": self._deduplicate_parameter_sets(parameter_sets),
            "notes": template_cfg.get("notes", []),
        }

    def formulate_variable_statistics_statements(
        self, variable_names: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Resolve parameter sets for a list of IAMC variables.

        Parameters
        ----------
        variable_names : list[str]
            IAMC variables to resolve.

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            Mapping from variable to resolved parameter-set list.
        """
        statements: dict[str, list[dict[str, Any]]] = {}
        for variable_name in variable_names:
            resolved = self.get_variable_parameter_mapping(variable_name)
            statements[variable_name] = resolved["parameter_sets"]
        return statements


class Network_Processor(Processor):
    def __init__(
        self,
        parent_processor: Variable_Processor,
    ) -> None:
        self.__dict__.update(parent_processor.__dict__)

    def run(self) -> None:
        """Executes Network Processor"""
        print("INFO: computing statistics on PyPSA network...")

    def evaluate_network_collection(self, p_dict: dict[str, Any]) -> Any:
        """
        Evaluate the network-collection with pypsa.statistics.energy_balance
        for one variable and parameter set.
        """
        val = pypsa.statistics.energy_balance(
            components=list(p_dict["components"]),
            groupby_method="sum",
            groupby="carrier",
            # at_port=p_dict["at_port"],
            carrier=p_dict["carrier"],
            bus_carrier=p_dict["bus_carrier"],
        ).xs(self.country, level="country").sum().values
        return val

    def evaluate_statistics_on_collection(self) -> dict[str, Any]:
        val_dict: dict[str, Any] = {}
        for variable, parameter_sets in self.statements_dict.items():
            if not isinstance(parameter_sets, list):
                continue
            values = [self.evaluate_network_collection(p_dict) for p_dict in parameter_sets]
            val_dict[variable] = values
        return val_dict
