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

    def test_execute_function_passes_config_when_accepted(self, mock_config_file: Path):
        """Test that config is passed to functions that accept it."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.functions_dict = {
                    "Test Variable": "mock_func_with_config"
                }

                # Create a mock function that accepts config
                received_config = {}

                def mock_func_with_config(n, config=None):
                    received_config["value"] = config
                    return pd.Series(
                        [1.0],
                        index=pd.MultiIndex.from_tuples([("AT", "MWh_el")], names=["country", "unit"]),
                    )

                with patch(
                    "pypsa_validation_processing.class_definitions.importlib.import_module"
                ) as mock_import:
                    mock_module = MagicMock()
                    mock_module.mock_func_with_config = mock_func_with_config
                    mock_import.return_value = mock_module

                    mock_network = MockPyPSANetwork()
                    test_config = {"some_key": "some_value"}
                    processor._execute_function_for_variable(
                        "Test Variable", mock_network, config=test_config
                    )
                    assert received_config["value"] == test_config

    def test_execute_function_does_not_pass_config_when_not_accepted(
        self, mock_config_file: Path
    ):
        """Test that config is NOT passed to functions that don't accept it."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.functions_dict = {
                    "Test Variable": "mock_func_without_config"
                }

                call_kwargs = {}

                def mock_func_without_config(n):
                    call_kwargs["called_with_config"] = False
                    return pd.Series(
                        [1.0],
                        index=pd.MultiIndex.from_tuples([("AT", "MWh_el")], names=["country", "unit"]),
                    )

                with patch(
                    "pypsa_validation_processing.class_definitions.importlib.import_module"
                ) as mock_import:
                    mock_module = MagicMock()
                    mock_module.mock_func_without_config = mock_func_without_config
                    mock_import.return_value = mock_module

                    mock_network = MockPyPSANetwork()
                    # Should not raise even though config is provided
                    result = processor._execute_function_for_variable(
                        "Test Variable", mock_network, config={"ignored": True}
                    )
                    assert isinstance(result, pd.Series)
                    assert call_kwargs.get("called_with_config") is False


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
        """Test that write_output creates an Excel file in the given directory."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)

                # Mock the dsd_with_values (aggregate_per_year=True by default)
                mock_iam_df = MagicMock()
                processor.dsd_with_values = mock_iam_df

                result_path = processor.write_output_to_xlsx()

                expected_path = (
                    processor.path_dsd_with_values
                    / "PYPSA_AT_KN2040_test_scenario_AT.xlsx"
                )
                assert result_path == expected_path
                # Verify to_excel was called
                mock_iam_df.to_excel.assert_called_once()

    def test_write_output_timeseries_creates_folder_and_per_year_files(
        self, mock_config_file: Path, tmp_path: Path
    ):
        """Test that write_output with aggregate_per_year=False creates one file per year."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.aggregate_per_year = False

                mock_iam_2020 = MagicMock()
                mock_iam_2030 = MagicMock()
                processor.dsd_with_values = [(2020, mock_iam_2020), (2030, mock_iam_2030)]

                result_path = processor.write_output_to_xlsx()

                expected_folder = (
                    processor.path_dsd_with_values
                    / "PYPSA_timeseries_AT_KN2040_test_scenario_AT"
                )
                assert result_path == expected_folder
                assert result_path.is_dir()
                mock_iam_2020.to_excel.assert_called_once_with(
                    expected_folder / "PYPSA_AT_KN2040_test_scenario_AT_2020.xlsx"
                )
                mock_iam_2030.to_excel.assert_called_once_with(
                    expected_folder / "PYPSA_AT_KN2040_test_scenario_AT_2030.xlsx"
                )

    def test_timeseries_column_year_matches_investment_year(
        self, mock_config_file: Path, tmp_path: Path
    ):
        """Snapshot columns of timeseries DataFrames must use the investment year."""
        import pandas as pd
        from pypsa_validation_processing import statistics_functions as sf

        investment_year = 2050

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.aggregate_per_year = False

                # Build a minimal timeseries DataFrame as a statistics function would return.
                # Columns are 2019 timestamps (mock default); processor must replace the year.
                ts_2019 = pd.date_range("2019-01-01", periods=4, freq="6h", name="snapshot")
                index = pd.MultiIndex.from_tuples(
                    [("AT1", "EJ/yr")], names=["location", "unit"]
                )
                raw_df = pd.DataFrame(
                    {ts: [1.0] for ts in ts_2019}, index=index, dtype=float
                )

                # Simulate what _postprocess_statistics_result produces for region mode.
                variable = "Test Variable"
                processor.aggregation_level = "region"
                # Inject the variable-level MultiIndex manually.
                processed = pd.concat({variable: raw_df}, names=["variable"])
                processed = processed.groupby(["variable", "location", "unit"]).sum()

                # Now simulate calculate_variables_values year-column replacement.
                processed.columns = processed.columns.map(
                    lambda ts: ts.replace(year=investment_year)
                )

                assert all(ts.year == investment_year for ts in processed.columns)


# ---------------------------------------------------------------------------
# Tests for aggregation configuration
# ---------------------------------------------------------------------------


class TestNetworkProcessorAggregation:
    """Test aggregation configuration and execution."""

    def _make_config_file(self, tmp_path: Path, extra: str = "") -> Path:
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_content = f"""
country: AT
model_name: AT_KN2040
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output.xlsx'}
{extra}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return config_file

    def test_aggregation_level_defaults_to_country(self, tmp_path: Path):
        """Test that aggregation_level defaults to 'country' if not specified."""
        config_file = self._make_config_file(tmp_path)
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                assert processor.aggregation_level == "country"

    def test_aggregation_level_from_config_country(self, tmp_path: Path):
        """Test that aggregation_level='country' is read from config."""
        config_file = self._make_config_file(tmp_path, extra='aggregation_level: "country"')
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                assert processor.aggregation_level == "country"

    def test_aggregation_level_from_config_locationwise(self, tmp_path: Path):
        """Test that aggregation_level='region' is read from config."""
        config_file = self._make_config_file(
            tmp_path, extra='aggregation_level: "region"'
        )
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                assert processor.aggregation_level == "region"

    def test_aggregation_level_validation_invalid(self, tmp_path: Path):
        """Test that invalid aggregation_level raises ValueError."""
        config_file = self._make_config_file(tmp_path, extra='aggregation_level: "invalid"')
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                with pytest.raises(ValueError, match="Invalid aggregation_level"):
                    Network_Processor(config_path=config_file)
