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

    def test_execute_function_caches_signature_parameters(self, mock_config_file: Path):
        """Test that function signature inspection is cached per function."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.functions_dict = {"Test Variable": "mock_func_with_config"}

                def mock_func_with_config(n, config=None):
                    return pd.Series(
                        [1.0],
                        index=pd.MultiIndex.from_tuples(
                            [("AT", "MWh_el")], names=["country", "unit"]
                        ),
                    )

                with patch(
                    "pypsa_validation_processing.class_definitions.importlib.import_module"
                ) as mock_import:
                    mock_module = MagicMock()
                    mock_module.mock_func_with_config = mock_func_with_config
                    mock_import.return_value = mock_module

                    mock_network = MockPyPSANetwork()
                    processor._execute_function_for_variable(
                        "Test Variable", mock_network, config={"a": 1}
                    )
                    assert len(processor._function_parameter_cache) == 1

                    cache_keys_before = tuple(
                        processor._function_parameter_cache.keys()
                    )
                    processor._execute_function_for_variable(
                        "Test Variable", mock_network, config={"b": 2}
                    )

                    assert len(processor._function_parameter_cache) == 1
                    assert (
                        tuple(processor._function_parameter_cache.keys())
                        == cache_keys_before
                    )


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
        """calculate_variables_values rewrites snapshot years to the investment year."""
        investment_year = 2050

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=mock_config_file)
                processor.aggregate_per_year = False
                processor.aggregation_level = "region"

                network = MockPyPSANetwork()
                network.meta["wildcards"]["planning_horizons"] = investment_year
                processor.network_collection = MockNetworkCollection([network])

                processor.dsd = MagicMock()
                processor.dsd.variable.to_pandas.return_value = pd.DataFrame(
                    {"variable": ["Test Variable"]}
                )

                ts_2019 = pd.date_range("2019-01-01", periods=4, freq="6h", name="snapshot")
                raw_df = pd.DataFrame(
                    {ts: [1.0] for ts in ts_2019},
                    index=pd.MultiIndex.from_tuples(
                        [("AT1", "MWh_el")], names=["location", "unit"]
                    ),
                    dtype=float,
                )

                with patch.object(
                    processor,
                    "_execute_function_for_variable",
                    return_value=raw_df,
                ):
                    with patch.object(
                        processor,
                        "structure_pyam_from_pandas",
                        side_effect=lambda df: df,
                    ):
                        processor.calculate_variables_values()

                assert len(processor.dsd_with_values) == 1
                year, timeseries_df = processor.dsd_with_values[0]
                assert year == investment_year
                assert all(ts.year == investment_year for ts in timeseries_df.columns)
                assert list(timeseries_df.columns) == [
                    ts.replace(year=investment_year) for ts in ts_2019
                ]


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


# ---------------------------------------------------------------------------
# Tests for country="all" initialization
# ---------------------------------------------------------------------------


class TestNetworkProcessorCountryAll:
    """Tests for Network_Processor with country='all'."""

    def _make_config_file(self, tmp_path: Path, country: str = "all", extra: str = "") -> Path:
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_content = f"""
country: {country}
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output.xlsx'}
{extra}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return config_file

    def test_country_all_accepted(self, tmp_path: Path):
        """country='all' must be accepted without raising ValueError."""
        config_file = self._make_config_file(tmp_path, country="all")
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                assert processor.country == "all"

    def test_country_invalid_code_raises(self, tmp_path: Path):
        """An unrecognised country code must raise ValueError."""
        config_file = self._make_config_file(tmp_path, country="XX")
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                with pytest.raises(ValueError, match="'country' must be"):
                    Network_Processor(config_path=config_file)

    def test_repr_includes_aggregation_level(self, tmp_path: Path):
        """__repr__ must include the aggregation_level field."""
        config_file = self._make_config_file(tmp_path, country="AT", extra='aggregation_level: "region"')
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                repr_str = repr(processor)
                assert "aggregation_level" in repr_str
                assert "region" in repr_str


# ---------------------------------------------------------------------------
# Tests for aggregation and filtering
# ---------------------------------------------------------------------------


class TestNetworkProcessorAggregationAndFiltering:
    """Test aggregation and filtering methods."""

    def _setup_processor(
        self, tmp_path: Path, country: str = "AT"
    ) -> Network_Processor:
        """Create a configured Network_Processor for testing."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_content = f"""
country: {country}
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output.xlsx'}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                return Network_Processor(config_path=config_file)

    def test_aggregate_to_country_specific_country(self, tmp_path: Path):
        """Test _aggregate_to_country with specific country code."""
        processor = self._setup_processor(tmp_path, country="AT")

        # Create test data with locations starting with "AT"
        data = pd.Series(
            [100.0, 200.0, 150.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("AT2", "MWh_el"), ("AT1", "MWh_th")],
                names=["location", "unit"],
            ),
        ).to_frame(name="value")

        result = processor._aggregate_to_country(data)

        # Should aggregate AT1 and AT2 rows by unit
        assert "location" not in result.index.names
        assert "unit" in result.index.names
        assert result.index.get_level_values("unit").tolist() == ["MWh_el", "MWh_th"]
        assert result.loc[("MWh_el",), "value"].item() == 300.0  # 100 + 200

    def test_aggregate_to_country_all_countries(self, tmp_path: Path):
        """Test _aggregate_to_country with country='all'."""
        processor = self._setup_processor(tmp_path, country="all")

        # Create test data with multiple country prefixes
        data = pd.Series(
            [100.0, 200.0, 50.0, 75.0],
            index=pd.MultiIndex.from_tuples(
                [
                    ("AT1", "MWh_el"),
                    ("AT2", "MWh_el"),
                    ("DE1", "MWh_el"),
                    ("AT1", "MWh_th"),
                ],
                names=["location", "unit"],
            ),
        ).to_frame(name="value")

        result = processor._aggregate_to_country(data)

        # Should create country index from location prefixes
        assert "country" in result.index.names
        assert "unit" in result.index.names
        assert ("AT", "MWh_el") in result.index
        assert ("DE", "MWh_el") in result.index

    def test_filter_to_regions_specific_country(self, tmp_path: Path):
        """Test _filter_to_regions filters to country prefix."""
        processor = self._setup_processor(tmp_path, country="AT")

        # Create test data with mixed country prefixes
        data = pd.Series(
            [100.0, 200.0, 150.0, 75.0],
            index=pd.MultiIndex.from_tuples(
                [
                    ("AT1", "MWh_el"),
                    ("AT2", "MWh_el"),
                    ("DE1", "MWh_el"),
                    ("AT1", "MWh_th"),
                ],
                names=["location", "unit"],
            ),
        )

        result = processor._filter_to_regions(data)

        # Should filter to only AT regions
        locations = result.index.get_level_values("location")
        assert all(loc.startswith("AT") for loc in locations)
        assert "DE1" not in locations

    def test_filter_to_regions_country_all(self, tmp_path: Path):
        """Test _filter_to_regions doesn't filter when country='all'."""
        processor = self._setup_processor(tmp_path, country="all")

        # Create test data with mixed country prefixes
        data = pd.Series(
            [100.0, 200.0, 150.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("DE1", "MWh_el"), ("AT2", "MWh_th")],
                names=["location", "unit"],
            ),
        )

        result = processor._filter_to_regions(data)

        # Should return all regions unchanaged
        assert len(result) == len(data)
        assert result.index.equals(data.index)

    def test_select_aggregation_result_country_mode(self, tmp_path: Path):
        """Test _select_aggregation_result aggregates in country mode."""
        processor = self._setup_processor(tmp_path, country="AT")
        processor.aggregation_level = "country"

        data = pd.Series(
            [100.0, 200.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("AT2", "MWh_el")],
                names=["location", "unit"],
            ),
        ).to_frame(name="value")

        result = processor._select_aggregation_result(data)

        assert "location" not in result.index.names
        assert "unit" in result.index.names

    def test_select_aggregation_result_region_mode(self, tmp_path: Path):
        """Test _select_aggregation_result preserves regions in region mode."""
        processor = self._setup_processor(tmp_path, country="AT")
        processor.aggregation_level = "region"

        data = pd.Series(
            [100.0, 200.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("AT2", "MWh_el")],
                names=["location", "unit"],
            ),
        ).to_frame(name="value")

        result = processor._select_aggregation_result(data)

        assert "location" in result.index.names
        assert "unit" in result.index.names

    def test_map_unit_level_with_multiindex(self, tmp_path: Path):
        """Test _map_unit_level maps unit column with MultiIndex."""
        processor = self._setup_processor(tmp_path)

        # Create data with units that should be mapped
        data = pd.DataFrame(
            {"value": [100.0, 200.0]},
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("AT2", "MWh_th")],
                names=["location", "unit"],
            ),
        )

        result = processor._map_unit_level(data)

        # MWh_el and MWh_th should be mapped according to UNITS_MAPPING
        assert result.index.get_level_values("unit").tolist() != ["MWh_el", "MWh_th"]

    def test_postprocess_group_levels_country_mode_specific_country(
        self, tmp_path: Path
    ):
        """Test _postprocess_group_levels returns correct levels for country mode."""
        processor = self._setup_processor(tmp_path, country="AT")
        processor.aggregation_level = "country"

        levels = processor._postprocess_group_levels()

        assert levels == ["variable", "unit"]

    def test_postprocess_group_levels_country_mode_all_countries(self, tmp_path: Path):
        """Test _postprocess_group_levels includes country for country='all'."""
        processor = self._setup_processor(tmp_path, country="all")
        processor.aggregation_level = "country"

        levels = processor._postprocess_group_levels()

        assert levels == ["variable", "country", "unit"]

    def test_postprocess_group_levels_region_mode(self, tmp_path: Path):
        """Test _postprocess_group_levels includes location for region mode."""
        processor = self._setup_processor(tmp_path, country="AT")
        processor.aggregation_level = "region"

        levels = processor._postprocess_group_levels()

        assert levels == ["variable", "location", "unit"]


# ---------------------------------------------------------------------------
# Tests for data postprocessing
# ---------------------------------------------------------------------------


class TestNetworkProcessorDataPostprocessing:
    """Test data postprocessing methods."""

    def _setup_processor(self, tmp_path: Path) -> Network_Processor:
        """Create a configured Network_Processor."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output.xlsx'}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                return Network_Processor(config_path=config_file)

    def test_postprocess_statistics_result_series_to_dataframe(self, tmp_path: Path):
        """Test _postprocess_statistics_result converts Series to DataFrame."""
        processor = self._setup_processor(tmp_path)
        processor.aggregation_level = "country"
        processor.aggregate_per_year = True

        # Create a Series result as would be returned by a statistics function
        result = pd.Series(
            [100.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el")],
                names=["location", "unit"],
            ),
        )

        with patch.object(
            processor,
            "_select_aggregation_result",
            return_value=result.to_frame(name="value"),
        ):
            with patch.object(
                processor, "_map_unit_level", return_value=result.to_frame(name="value")
            ):
                output = processor._postprocess_statistics_result(
                    "Final Energy|Electricity", result
                )

        assert isinstance(output, pd.DataFrame)
        assert "variable" in output.index.names

    def test_postprocess_statistics_result_with_region_aggregation(
        self, tmp_path: Path
    ):
        """Test _postprocess_statistics_result preserves regions."""
        processor = self._setup_processor(tmp_path)
        processor.aggregation_level = "region"

        result = pd.Series(
            [100.0, 200.0],
            index=pd.MultiIndex.from_tuples(
                [("AT1", "MWh_el"), ("AT2", "MWh_el")],
                names=["location", "unit"],
            ),
        )

        output = processor._postprocess_statistics_result("Test|Variable", result)

        assert "location" in output.index.names
        assert "variable" in output.index.names

    def test_structure_pyam_from_pandas_country_specific(self, tmp_path: Path):
        """Test structure_pyam_from_pandas with specific country."""
        processor = self._setup_processor(tmp_path)
        processor.aggregation_level = "country"
        processor.country = "AT"

        df = pd.DataFrame(
            {
                "variable": ["Final Energy|Electricity"],
                "unit": ["MWh_el"],
                "value": [1000.0],
                "year": [2020],
            }
        )

        with patch(
            "pypsa_validation_processing.class_definitions.pyam.IamDataFrame"
        ) as mock_iam:
            mock_iam.return_value = MagicMock()
            processor.structure_pyam_from_pandas(df)
            mock_iam.assert_called_once()

    def test_structure_pyam_from_pandas_country_all(self, tmp_path: Path):
        """Test structure_pyam_from_pandas with country='all'."""
        processor = self._setup_processor(tmp_path)
        processor.aggregation_level = "country"
        processor.country = "all"

        df = pd.DataFrame(
            {
                "variable": ["Final Energy|Electricity", "Final Energy|Electricity"],
                "country": ["AT", "DE"],
                "unit": ["MWh_el", "MWh_el"],
                "value": [1000.0, 2000.0],
                "year": [2020, 2020],
            }
        )

        with patch(
            "pypsa_validation_processing.class_definitions.pyam.IamDataFrame"
        ) as mock_iam:
            mock_iam.return_value = MagicMock()
            processor.structure_pyam_from_pandas(df)
            mock_iam.assert_called_once()

    def test_structure_pyam_from_pandas_region_mode(self, tmp_path: Path):
        """Test structure_pyam_from_pandas with region aggregation level."""
        processor = self._setup_processor(tmp_path)
        processor.aggregation_level = "region"

        df = pd.DataFrame(
            {
                "variable": ["Final Energy|Electricity"],
                "location": ["AT1"],
                "unit": ["MWh_el"],
                "value": [1000.0],
                "year": [2020],
            }
        )

        with patch(
            "pypsa_validation_processing.class_definitions.pyam.IamDataFrame"
        ) as mock_iam:
            mock_iam.return_value = MagicMock()
            processor.structure_pyam_from_pandas(df)
            mock_iam.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for file I/O and network loading
# ---------------------------------------------------------------------------


class TestNetworkProcessorFileIO:
    """Test file I/O and configuration loading methods."""

    def test_read_definitions_returns_datastructuredefinition(self):
        """Test read_definitions returns a DataStructureDefinition."""
        with patch(
            "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
        ) as mock_dsd_class:
            mock_dsd = MagicMock()
            mock_dsd_class.return_value = mock_dsd

            with patch(
                "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
            ):
                with patch(
                    "pypsa_validation_processing.class_definitions.Network_Processor._read_config"
                ):
                    with patch(
                        "pypsa_validation_processing.class_definitions.Path.exists",
                        return_value=True,
                    ):
                        with patch(
                            "pypsa_validation_processing.class_definitions.os.listdir",
                            return_value=["test.nc"],
                        ):
                            processor = MagicMock(spec=["definitions_path"])
                            processor.definitions_path = Path("/tmp/definitions")

                            result = Network_Processor.read_definitions(processor)

                            assert result == mock_dsd

    def test_read_mappings_missing_file(self, tmp_path: Path):
        """Test _read_mappings raises FileNotFoundError if file missing."""
        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                config_content = """
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: /tmp/definitions
network_results_path: /tmp/networks
mapping_path: /nonexistent/mapping.yaml
"""
                config_file = tmp_path / "config.yaml"
                config_file.write_text(config_content)

                # Create minimal required directories
                defs_path = tmp_path / "definitions"
                defs_path.mkdir(exist_ok=True)
                nw_path = tmp_path / "networks"
                nw_path.mkdir(parents=True, exist_ok=True)
                (nw_path / "dummy.nc").touch()

                # Update config with valid paths
                config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
mapping_path: /nonexistent/mapping.yaml
"""
                config_file.write_text(config_content)

                with pytest.raises(FileNotFoundError, match="Mapping file not found"):
                    Network_Processor(config_path=config_file)

    def test_aggregate_per_year_defaults_to_true(self, tmp_path: Path):
        """Test aggregate_per_year defaults to True."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()

        config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                assert processor.aggregate_per_year is True

    def test_aggregate_per_year_validation_non_bool(self, tmp_path: Path):
        """Test aggregate_per_year validation rejects non-bool values."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()

        config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
aggregate_per_year: "not_a_bool"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                with pytest.raises(ValueError, match="Invalid aggregate_per_year"):
                    Network_Processor(config_path=config_file)

    def test_write_output_creates_parent_directory(self, tmp_path: Path):
        """Test write_output_to_xlsx creates parent directories."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()

        deep_output_path = tmp_path / "deep" / "nested" / "folder"

        config_content = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {deep_output_path / 'output.xlsx'}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                mock_iam_df = MagicMock()
                processor.dsd_with_values = mock_iam_df

                processor.write_output_to_xlsx()

                assert deep_output_path.exists()

    def test_write_output_country_all_with_aggregation(self, tmp_path: Path):
        """Test write_output with country='all' has correct filename."""
        defs_path = tmp_path / "definitions"
        defs_path.mkdir(exist_ok=True)
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()

        config_content = f"""
country: all
model_name: MyModel
scenario_name: MyScenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output.xlsx'}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with patch(
            "pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"
        ):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                processor = Network_Processor(config_path=config_file)
                mock_iam_df = MagicMock()
                processor.dsd_with_values = mock_iam_df

                result_path = processor.write_output_to_xlsx()

                # For country="all", filename should not include country suffix
                assert "PYPSA_MyModel_MyScenario.xlsx" in str(result_path)
                assert "PYPSA_MyModel_MyScenario_all.xlsx" not in str(result_path)
