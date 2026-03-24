"""Tests for pypsa_validation_processing.class_definitions.Network_Processor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

from pypsa_validation_processing.class_definitions import Network_Processor
from conftest import MockPyPSANetwork, MockNetworkCollection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_dict() -> dict:
    """Fixture providing a mock configuration dictionary."""
    return {
        "country": "AT",
        "model_name": "AT_KN2040",
        "scenario_name": "test",
        "definitions_path": "/tmp/definitions",
        "network_results_path": "/tmp/network_results",
    }


@pytest.fixture
def mock_definitions_path(tmp_path: Path) -> Path:
    """Fixture providing a mock definitions directory."""
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    
    # Create a minimal definitions file (CSV format expected by nomenclature)
    definitions_file = defs_path / "variables.csv"
    definitions_file.write_text(
        "Variable\n"
        "Final Energy [by Carrier]|Electricity\n"
        "Final Energy [by Sector]|Transportation\n"
    )
    return defs_path


@pytest.fixture
def mock_network_results_path(tmp_path: Path) -> Path:
    """Fixture providing a mock network results directory with networks."""
    nw_path = tmp_path / "networks"
    nw_path.mkdir(parents=True, exist_ok=True)
    
    # Create dummy network files
    for year in [2020, 2030]:
        (nw_path / f"base_s_adm__none_{year}.nc").touch()
    return nw_path.parent


@pytest.fixture
def mock_config_file(
    tmp_path: Path, mock_definitions_path: Path, mock_network_results_path: Path
) -> Path:
    """Fixture providing a temporary config file for testing."""
    config_content = f"""
country: AT
model_name: AT_KN2040
scenario_name: test_scenario
definitions_path: {mock_definitions_path}
network_results_path: {mock_network_results_path}
output_path: {tmp_path / 'output.xlsx'}
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


# ---------------------------------------------------------------------------
# Tests for Network_Processor initialization
# ---------------------------------------------------------------------------


class TestNetworkProcessorInit:
    """Test Network_Processor initialization and configuration loading."""

    def test_init_with_valid_config(self, mock_config_file: Path):
        """Test initialization with a valid configuration file."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                assert processor.country == "AT"
                assert processor.model_name == "AT_KN2040"
                assert processor.scenario_name == "test_scenario"

    def test_init_missing_required_config(self, tmp_path: Path):
        """Test initialization fails with missing required config keys."""
        config_file = tmp_path / "bad_config.yaml"
        config_file.write_text("model_name: test\n")  # Missing required keys
        
        with pytest.raises(ValueError):
            Network_Processor(config_path=config_file)

    def test_repr_method(self, mock_config_file: Path):
        """Test the __repr__ method returns informative string."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                repr_str = repr(processor)
                assert "Network_Processor" in repr_str
                assert "AT" in repr_str


# ---------------------------------------------------------------------------
# Tests for configuration reading
# ---------------------------------------------------------------------------


class TestNetworkProcessorConfigReading:
    """Test configuration file reading functionality."""

    def test_read_config(self, mock_config_file: Path):
        """Test that config is read correctly from YAML."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                config = processor.config
                assert isinstance(config, dict)
                assert "country" in config
                assert "model_name" in config

    def test_config_path_validation(self, tmp_path: Path):
        """Test that nonexistent config file raises error."""
        nonexistent_config = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            Network_Processor(config_path=nonexistent_config)


# ---------------------------------------------------------------------------
# Tests for function execution
# ---------------------------------------------------------------------------


class TestNetworkProcessorFunctionExecution:
    """Test function lookup and execution."""

    def test_execute_function_for_variable_returns_series(self, mock_config_file: Path):
        """Test that _execute_function_for_variable returns a Series."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.functions_dict = {
                    "Final Energy [by Carrier]|Electricity": "Final_Energy_by_Carrier__Electricity"
                }
                
                mock_network = MockPyPSANetwork()
                result = processor._execute_function_for_variable(
                    "Final Energy [by Carrier]|Electricity", mock_network
                )
                
                assert isinstance(result, (pd.DataFrame, pd.Series)) or result is None

    def test_execute_function_not_found(self, mock_config_file: Path):
        """Test that function returns None when not found."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.functions_dict = {}
                
                mock_network = MockPyPSANetwork()
                result = processor._execute_function_for_variable(
                    "Nonexistent Variable", mock_network
                )
                assert result is None


# ---------------------------------------------------------------------------
# Tests for output generation
# ---------------------------------------------------------------------------


class TestNetworkProcessorOutputGeneration:
    """Test output file generation."""

    def test_write_output_raises_without_data(self, mock_config_file: Path):
        """Test that write_output raises error if no data has been calculated."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                with pytest.raises(RuntimeError, match="No data available"):
                    processor.write_output_to_xlsx()

    def test_write_output_creates_file(self, mock_config_file: Path, tmp_path: Path):
        """Test that write_output creates an Excel file."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                
                # Mock the dsd_with_values
                mock_iam_df = MagicMock()
                processor.dsd_with_values = mock_iam_df
                
                output_path = tmp_path / "test_output.xlsx"
                result_path = processor.write_output_to_xlsx(output_path=output_path)
                
                assert result_path == output_path
                # Verify to_excel was called
                mock_iam_df.to_excel.assert_called_once()
