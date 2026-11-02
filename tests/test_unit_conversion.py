"""Tests for common-definitions unit conversion in Network_Processor."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pyam
import pytest

from pypsa_validation_processing.class_definitions import Network_Processor
from pypsa_validation_processing.utils import UNITS_MAPPING


def _make_config(tmp_path: Path, extra: str = "") -> Path:
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    (defs_path / "variables.csv").write_text(
        "variable\nFinal Energy [by Carrier]|Electricity\n"
    )

    nw_path = tmp_path / "networks"
    nw_path.mkdir(parents=True)
    (nw_path / "dummy.nc").touch()

    config = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output'}
{extra}
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config)
    return config_path


@pytest.fixture
def processor(tmp_path: Path) -> Network_Processor:
    config_path = _make_config(tmp_path)
    with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
        with patch(
            "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
        ):
            return Network_Processor(config_path=config_path)


class TestCommonDefinitionsConfiguration:
    """Test unit-conversion configuration initialization."""

    def test_config_without_common_definitions_path(self, tmp_path: Path):
        config_path = _make_config(tmp_path)
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_path)
        assert not hasattr(processor, "common_definitions_path")
        assert processor.common_dsd is not None

    def test_config_ignores_common_definitions_path(self, tmp_path: Path):
        common_defs = tmp_path / "common_defs"
        common_defs.mkdir()
        config_path = _make_config(
            tmp_path, extra=f"common_definitions_path: {common_defs}\n"
        )
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_path)
        assert not hasattr(processor, "common_definitions_path")
        assert processor.common_dsd is not None

    def test_common_dsd_initialized_correctly(self, tmp_path: Path):
        config_path = _make_config(tmp_path)
        common_dsd = MagicMock()
        definitions_dsd = MagicMock()
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition",
                side_effect=[common_dsd, definitions_dsd],
            ) as mock_dsd:
                processor = Network_Processor(config_path=config_path)
        assert not hasattr(processor, "common_definitions_path")
        assert processor.common_dsd is common_dsd
        assert processor.dsd is definitions_dsd
        assert mock_dsd.call_count == 2

    def test_convert_units_false_leaves_common_dsd_none(self, tmp_path: Path):
        """convert_units: false with a real definitions_path skips common_dsd init."""
        config_path = _make_config(tmp_path, extra="convert_units: false\n")
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_path)
        assert processor.common_dsd is None

    def test_definitions_disabled_overrides_convert_units_true(self, tmp_path: Path):
        """definitions_path: False leaves common_dsd None even if convert_units is true."""
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True)
        (nw_path / "dummy.nc").touch()
        config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: False
convert_units: true
network_results_path: {tmp_path}
output_path: {tmp_path / 'output'}
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(config_content)
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_path)
        assert processor.use_definitions is False
        assert processor.common_dsd is None


class TestGetUnitFromCommonDefinitions:
    """Tests for _get_unit_from_common_definitions()."""

    def test_returns_unit_for_known_variable(self, processor: Network_Processor):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A", "B"], "unit": ["EJ/yr", "MWh/yr"]}
        )
        assert processor._get_unit_from_common_definitions("A") == "EJ/yr"

    def test_raises_keyerror_for_unknown_variable(self, processor: Network_Processor):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["EJ/yr"]}
        )
        with pytest.raises(KeyError, match="not defined"):
            processor._get_unit_from_common_definitions("B")

    def test_warns_and_uses_first_match_for_multiple_definitions(
        self, processor: Network_Processor, caplog
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A", "A"], "unit": ["EJ/yr", "TWh/yr"]}
        )
        with caplog.at_level(logging.WARNING):
            assert processor._get_unit_from_common_definitions("A") == "EJ/yr"
        assert any(
            "Multiple definitions found for variable" in record.message
            for record in caplog.records
        )

    def test_raises_runtime_error_when_common_dsd_not_initialized(
        self, processor: Network_Processor
    ):
        processor.common_dsd = None
        with pytest.raises(RuntimeError, match="not initialized"):
            processor._get_unit_from_common_definitions("A")

    def test_raises_keyerror_when_variable_column_missing(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"unit": ["EJ/yr"]}
        )
        with pytest.raises(KeyError, match="Variable column not found"):
            processor._get_unit_from_common_definitions("A")

    def test_raises_keyerror_when_unit_column_missing(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"]}
        )
        with pytest.raises(KeyError, match="Unit column not found"):
            processor._get_unit_from_common_definitions("A")

    def test_parses_first_unit_from_multi_unit_bracket_string(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["['GWh', 'TJ']"]}
        )
        assert processor._get_unit_from_common_definitions("A") == "GWh"

    def test_raises_for_malformed_multi_unit_string(
        self, processor: Network_Processor
    ):
        """C9.3: an unparsable unit list raises ValueError, no TJ fallback (SC-10)."""
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["[TJ, GWh]"]}
        )
        with pytest.raises(ValueError, match="Cannot parse the unit list"):
            processor._get_unit_from_common_definitions("A")

    def test_raises_keyerror_for_nan_unit(self, processor: Network_Processor):
        """The NaN check runs before the bracket-parsing check, so a NaN unit
        raises the documented KeyError rather than TypeError."""
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": [float("nan")]}
        )
        with pytest.raises(KeyError, match="Unit information not found"):
            processor._get_unit_from_common_definitions("A")


class TestConvertUnitsToCommonDefinitions:
    """Tests for _convert_units_to_common_definitions()."""

    def test_skips_conversion_when_no_common_dsd(self, processor: Network_Processor):
        processor.common_dsd = None
        iam_df = pyam.IamDataFrame(
            pd.DataFrame(
                {
                    "variable": ["A"],
                    "unit": ["EJ/yr"],
                    "year": [2020],
                    "value": [1.0],
                }
            ),
            model="m",
            scenario="s",
            region="World",
        )
        assert processor._convert_units_to_common_definitions(iam_df) is iam_df

    def test_converts_variable_to_target_unit(self, processor: Network_Processor):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["TWh/yr"]}
        )
        iam_df = pyam.IamDataFrame(
            pd.DataFrame(
                {
                    "variable": ["A"],
                    "unit": ["EJ/yr"],
                    "year": [2020],
                    "value": [1.0],
                }
            ),
            model="m",
            scenario="s",
            region="World",
        )

        converted = processor._convert_units_to_common_definitions(iam_df)
        assert converted.unit == ["TWh/yr"]

    def test_raises_value_error_when_no_unit_found_for_variable(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        iam_df = MagicMock()
        iam_df.variable = ["A"]
        var_df = MagicMock()
        var_df.unit = []
        iam_df.filter.return_value = var_df

        with pytest.raises(ValueError, match="No unit found for variable"):
            processor._convert_units_to_common_definitions(iam_df)

    def test_raises_value_error_when_variable_has_multiple_units(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        iam_df = MagicMock()
        iam_df.variable = ["A"]
        var_df = MagicMock()
        var_df.unit = ["EJ/yr", "TWh/yr"]
        iam_df.filter.return_value = var_df

        with pytest.raises(ValueError, match="multiple units"):
            processor._convert_units_to_common_definitions(iam_df)

    def test_raises_runtime_error_for_missing_variable_definition(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["B"], "unit": ["TWh/yr"]}
        )
        iam_df = pyam.IamDataFrame(
            pd.DataFrame(
                {
                    "variable": ["A"],
                    "unit": ["EJ/yr"],
                    "year": [2020],
                    "value": [1.0],
                }
            ),
            model="m",
            scenario="s",
            region="World",
        )

        with pytest.raises(RuntimeError, match="not found in common definitions"):
            processor._convert_units_to_common_definitions(iam_df)

    def test_raises_value_error_on_failed_conversion(
        self, processor: Network_Processor
    ):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["TWh/yr"]}
        )
        iam_df = pyam.IamDataFrame(
            pd.DataFrame(
                {
                    "variable": ["A"],
                    "unit": ["EJ/yr"],
                    "year": [2020],
                    "value": [1.0],
                }
            ),
            model="m",
            scenario="s",
            region="World",
        )

        with patch.object(pyam, "IamDataError", ValueError, create=True):
            with patch.object(
                pyam.core.IamDataFrame,
                "convert_unit",
                side_effect=ValueError("conversion failed"),
            ):
                with pytest.raises(ValueError, match="Failed to convert units"):
                    processor._convert_units_to_common_definitions(iam_df)

    def test_structure_pyam_calls_unit_conversion(self, processor: Network_Processor):
        processor.aggregation_level = "country"
        df = pd.DataFrame(
            {
                "2020": [1.0],
            },
            index=pd.MultiIndex.from_tuples(
                [("A", "EJ/yr")], names=["variable", "unit"]
            ),
        )
        with patch.object(
            processor,
            "_convert_units_to_common_definitions",
            side_effect=lambda iam: iam,
        ) as mock_convert:
            processor.structure_pyam_from_pandas(df)
        mock_convert.assert_called_once()

    def test_structure_pyam_applies_conversion_with_common_definitions(
        self, processor: Network_Processor
    ):
        processor.aggregation_level = "country"
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["TWh/yr"]}
        )
        df = pd.DataFrame(
            {"2020": [1.0]},
            index=pd.MultiIndex.from_tuples(
                [("A", "EJ/yr")], names=["variable", "unit"]
            ),
        )

        iam_df = processor.structure_pyam_from_pandas(df)
        assert iam_df.unit == ["TWh/yr"]


def _unit_result(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """Statistics result with levels location and unit and a value column."""
    index = pd.MultiIndex.from_tuples(
        [(loc, unit) for loc, unit, _ in rows], names=["location", "unit"]
    )
    return pd.DataFrame({"value": [v for _, _, v in rows]}, index=index)


class TestUnitNormalisation:
    """Tests for unit validation and normalisation in post-processing (C9.1, C9.5)."""

    def test_units_mapping_has_no_empty_unit(self):
        """C9-AC2c (part): UNITS_MAPPING does not contain the key ''."""
        assert "" not in UNITS_MAPPING

    @pytest.mark.parametrize("unit", ["foo", ""])
    def test_unknown_unit_raises(self, processor: Network_Processor, unit: str):
        """C9-AC2, C9-AC2b: a unit outside UNITS_MAPPING raises ValueError naming variable and unit."""
        result = _unit_result([("AT1", unit, 1.0)])
        with pytest.raises(ValueError, match=f"Variable 'Var'.*{re.escape(repr(unit))}"):
            processor._postprocess_statistics_result("Var", result)

    @pytest.mark.parametrize("country", ["AT", "all"])
    def test_null_unit_raises_with_country_aggregation(
        self, processor: Network_Processor, country: str
    ):
        """C9-AC2: a null unit is not dropped by country aggregation but raises ValueError."""
        processor.country = country
        result = _unit_result([("AT1", None, 1.0), ("AT2", "MWh_el", 2.0)])
        with pytest.raises(ValueError, match="Variable 'Var'.*nan"):
            processor._postprocess_statistics_result("Var", result)

    def test_several_units_raise_without_conversion(self, tmp_path: Path):
        """C9-AC4: rows in MWh and t raise ValueError also with convert_units: false (SC-24)."""
        config_path = _make_config(tmp_path, extra="convert_units: false")
        with (
            patch(
                "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
            ),
            patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ),
        ):
            processor = Network_Processor(config_path=config_path)
        assert processor.common_dsd is None
        result = _unit_result([("AT1", "MWh_el", 1.0), ("AT2", "t_co2", 2.0)])
        with pytest.raises(ValueError, match="several units"):
            processor._postprocess_statistics_result("Var", result)

    def test_normalised_unit_without_conversion(self, tmp_path: Path):
        """C9-AC6: with convert_units: false, a MWh_el result is output as MWh."""
        config_path = _make_config(tmp_path, extra="convert_units: false")
        with (
            patch(
                "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
            ),
            patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ),
        ):
            processor = Network_Processor(config_path=config_path)
        result = _unit_result([("AT1", "MWh_el", 1.0), ("AT2", "MWh_th", 2.0)])
        out = processor._postprocess_statistics_result("Var", result)
        assert out.index.get_level_values("unit").tolist() == ["MWh"]
        assert out["value"].tolist() == [3.0]
