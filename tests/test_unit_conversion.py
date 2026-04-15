"""Tests for common-definitions unit conversion in Network_Processor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pyam
import pytest

from pypsa_validation_processing.class_definitions import Network_Processor


def _make_config(tmp_path: Path, extra: str = "") -> Path:
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    (defs_path / "variables.csv").write_text("variable\nFinal Energy [by Carrier]|Electricity\n")

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
        with patch("pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"):
            return Network_Processor(config_path=config_path)


class TestCommonDefinitionsConfiguration:
    """Test common_definitions_path initialization."""

    def test_config_without_common_definitions_path(self, tmp_path: Path):
        config_path = _make_config(tmp_path)
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch("pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"):
                processor = Network_Processor(config_path=config_path)
        assert processor.common_definitions_path is None
        assert processor.common_dsd is None

    def test_config_with_nonexistent_common_definitions_path(self, tmp_path: Path):
        missing = tmp_path / "missing_common"
        config_path = _make_config(
            tmp_path, extra=f"common_definitions_path: {missing}\n"
        )
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch("pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"):
                with pytest.raises(FileNotFoundError, match="Common definitions folder"):
                    Network_Processor(config_path=config_path)

    def test_common_dsd_initialized_correctly(self, tmp_path: Path):
        common_defs = tmp_path / "common_defs"
        common_defs.mkdir()
        config_path = _make_config(
            tmp_path, extra=f"common_definitions_path: {common_defs}\n"
        )
        common_dsd = MagicMock()
        definitions_dsd = MagicMock()
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition",
                side_effect=[common_dsd, definitions_dsd],
            ) as mock_dsd:
                processor = Network_Processor(config_path=config_path)
        assert processor.common_definitions_path == common_defs
        assert processor.common_dsd is common_dsd
        assert mock_dsd.call_count == 2


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

    def test_raises_value_error_on_failed_conversion(self, processor: Network_Processor):
        processor.common_dsd = MagicMock()
        processor.common_dsd.variable.to_pandas.return_value = pd.DataFrame(
            {"variable": ["A"], "unit": ["NOT_A_UNIT"]}
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
            index=pd.MultiIndex.from_tuples([("A", "EJ/yr")], names=["variable", "unit"]),
        )

        iam_df = processor.structure_pyam_from_pandas(df)
        assert iam_df.unit == ["TWh/yr"]
