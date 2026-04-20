"""Shared test fixtures and configuration for pypsa_validation_processing tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


class MockStatisticsAccessor:
    """Mock PyPSA Statistics accessor for testing.

    This mock provides the energy_balance method that returns realistic
    pandas Series with MultiIndex structure matching PyPSA output.
    """

    def __init__(self, network_data: dict | None = None):
        """Initialize with optional predefined network data."""
        self.network_data = network_data or {}

    def energy_balance(
        self,
        bus_carrier: str | None = None,
        carrier: list[str] | str | None = None,
        components: str | list[str] | None = None,
        groupby: list[str] | None = None,
        direction: str = "withdrawal",
        at_port: list[str] | None = None,
        groupby_time: bool = True,
    ) -> pd.Series | pd.DataFrame:
        """Mock energy_balance method for PyPSA Network.statistics.

        Returns a pandas Series (when ``groupby_time=True``) or DataFrame with
        timestamp columns (when ``groupby_time=False``) with MultiIndex
        including 'location' and 'unit' to match the expected output structure.

        Parameters
        ----------
        bus_carrier : str | None
            Bus carrier filter (e.g., "AC" for AC bus)
        carrier : list[str] | str | None
            Carrier filter
        components : str | list[str] | None
            Components to include
        groupby : list[str] | None
            Grouping keys for the result
        direction : str
            Direction of energy flow ("withdrawal" or "supply")
        at_port : list[str] | None
            Port filter (e.g., "bus0" or "bus1" for Links)
        groupby_time : bool
            If ``True`` (default) return an aggregated Series.
            If ``False`` return a DataFrame with 4 hourly timestamps as columns.

        Returns
        -------
        pd.Series | pd.DataFrame
            Series (``groupby_time=True``) or DataFrame (``groupby_time=False``)
            with MultiIndex containing 'location' and 'unit' levels.
        """
        # Default groupby if not specified
        if groupby is None:
            groupby = ["carrier", "location", "unit"]

        # Create mock data structure based on groupby
        index_tuples = []
        values = []

        # Generate mock data with different carriers based on input
        if isinstance(carrier, list):
            carriers = carrier
        elif isinstance(carrier, str):
            carriers = [carrier]
        elif bus_carrier == "AC":
            carriers = ["wind", "solar", "hydro"]
        else:
            carriers = ["electricity"]

        for c in carriers:
            for location in ["AT1", "AT2", "AT3"]:
                for unit in ["MWh_el", "MWh_th"]:
                    # Create index tuple based on groupby keys
                    idx_dict = {
                        "carrier": c,
                        "location": location,
                        "unit": unit,
                    }
                    idx_tuple = tuple(idx_dict[key] for key in groupby)
                    index_tuples.append(idx_tuple)
                    # Mock value: roughly realistic energy value
                    values.append(1000.0)

        # Create MultiIndex
        index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)

        if groupby_time:
            return pd.Series(values, index=index, dtype=float)
        else:
            # Return DataFrame with 4 hourly timestamps as columns
            timestamps = pd.date_range("2019-01-01", periods=4, freq="6h", name="snapshot")
            return pd.DataFrame(
                {ts: values for ts in timestamps},
                index=index,
                dtype=float,
            )


class MockPyPSANetwork:
    """Minimal mock PyPSA Network for unit testing.

    Provides the interface required by statistics_functions without
    needing actual network files.
    """

    def __init__(self, name: str = "test_network", **kwargs):
        """Initialize mock network.

        Parameters
        ----------
        name : str
            Name of the network
        **kwargs
            Additional attributes to set on the network
        """
        self.name = name
        self.meta = {
            "wildcards": {"planning_horizons": 2020},
        }
        self.statistics = MockStatisticsAccessor()
        # Add carriers attribute with empty index by default
        self.carriers = pd.DataFrame(index=[])

        # Set any additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockNetworkCollection:
    """Mock PyPSA NetworkCollection for testing.

    Simulates a collection of networks that can be indexed and iterated.
    """

    def __init__(self, networks: list[MockPyPSANetwork] | None = None):
        """Initialize mock collection.

        Parameters
        ----------
        networks : list[MockPyPSANetwork] | None
            List of networks in the collection. If None, creates default networks.
        """
        self.networks = networks or [
            MockPyPSANetwork(name="network_2020"),
            MockPyPSANetwork(name="network_2030"),
        ]

    def __len__(self) -> int:
        return len(self.networks)

    def __getitem__(self, index: int) -> MockPyPSANetwork:
        return self.networks[index]

    def __iter__(self):
        return iter(self.networks)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_network() -> MockPyPSANetwork:
    """Fixture providing a single mock PyPSA Network."""
    return MockPyPSANetwork(name="test_network")


@pytest.fixture
def mock_network_collection() -> MockNetworkCollection:
    """Fixture providing a mock PyPSA NetworkCollection."""
    return MockNetworkCollection()


@pytest.fixture
def mock_pypsa_network_with_metadata() -> MockPyPSANetwork:
    """Fixture providing a mock network with realistic metadata."""
    network = MockPyPSANetwork(
        name="AT_KN2040_test",
    )
    network.meta = {
        "wildcards": {
            "planning_horizons": 2030,
            "sector_opts": "355H",
        },
        "scenarios": ["test_scenario"],
    }
    return network


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Fixture providing a temporary config file for testing."""
    config_content = """
country: AT
model_name: AT_KN2040
scenario_name: test
definitions_path: /tmp/definitions
network_results_path: /tmp/network_results
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file
