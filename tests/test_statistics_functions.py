"""Tests for pypsa_validation_processing.statistics_functions."""

from __future__ import annotations

import pandas as pd
import pytest

from pypsa_validation_processing.statistics_functions import (
    Final_Energy_by_Carrier__Electricity,
    Final_Energy_by_Sector__Industry,
    Final_Energy_by_Sector__Transportation,
)

from conftest import MockPyPSANetwork, MockNetworkCollection


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Electricity
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierElectricity:
    """Test suite for Final_Energy_by_Carrier__Electricity function."""

    def test_returns_dataframe(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas DataFrame or Series."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert isinstance(result, (pd.DataFrame, pd.Series))

    def test_has_country_and_unit_index(self, mock_network: MockPyPSANetwork):
        """Test that result has country and unit in the index."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert "country" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_austria(self, mock_network: MockPyPSANetwork):
        """Test that result contains Austria (AT) data."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert "AT" in result.index.get_level_values("country")

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Carrier__Electricity(network)
            assert isinstance(result, (pd.DataFrame, pd.Series))
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Transportation
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorTransportation:
    """Test suite for Final_Energy_by_Sector__Transportation function."""

    def test_returns_dataframe(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas DataFrame or Series."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert isinstance(result, (pd.DataFrame, pd.Series))

    def test_has_country_and_unit_index(self, mock_network: MockPyPSANetwork):
        """Test that result has country and unit in the index."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert "country" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_austria(self, mock_network: MockPyPSANetwork):
        """Test that result contains Austria (AT) data."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert "AT" in result.index.get_level_values("country")

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Transportation(network)
            assert isinstance(result, (pd.DataFrame, pd.Series))
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Industry
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorIndustry:
    """Test suite for Final_Energy_by_Sector__Industry function."""

    def test_returns_dataframe(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas DataFrame or Series."""
        result = Final_Energy_by_Sector__Industry(mock_network)
        assert isinstance(result, (pd.DataFrame, pd.Series))

    def test_has_country_and_unit_index(self, mock_network: MockPyPSANetwork):
        """Test that result has country and unit in the index."""
        result = Final_Energy_by_Sector__Industry(mock_network)
        assert "country" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Industry(mock_network)
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Industry(mock_network)
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_austria(self, mock_network: MockPyPSANetwork):
        """Test that result contains Austria (AT) data."""
        result = Final_Energy_by_Sector__Industry(mock_network)
        assert "AT" in result.index.get_level_values("country")

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Industry(network)
            assert isinstance(result, (pd.DataFrame, pd.Series))
            assert len(result) > 0
