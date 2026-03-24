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
    ) -> pd.Series:
        """Mock energy_balance method for PyPSA Network.statistics.

        Returns a pandas Series with MultiIndex including 'country' and 'unit'
        to match the expected output structure.

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

        Returns
        -------
        pd.Series
            Series with MultiIndex containing 'country' and 'unit' levels
        """
        # Default groupby if not specified
        if groupby is None:
            groupby = ["carrier", "country", "unit"]

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
            for country in ["AT", "DE"]:
                for unit in ["MWh_el", "MWh_th"]:
                    # Create index tuple based on groupby keys
                    idx_dict = {
                        "carrier": c,
                        "country": country,
                        "unit": unit,
                    }
                    idx_tuple = tuple(idx_dict[key] for key in groupby)
                    index_tuples.append(idx_tuple)
                    # Mock value: roughly realistic energy value
                    values.append(1000.0)

        # Create MultiIndex Series
        index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)
        return pd.Series(values, index=index, dtype=float)


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
