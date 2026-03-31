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

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert isinstance(result, pd.Series)

    def test_has_country_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with country and unit levels."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["country", "unit"]

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
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["country", "unit"]
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Transportation
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorTransportation:
    """Test suite for Final_Energy_by_Sector__Transportation function."""

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert isinstance(result, pd.Series)

    def test_has_country_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with country and unit levels."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["country", "unit"]

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
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["country", "unit"]
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Industry
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorIndustry:
    """Test suite for Final_Energy_by_Sector__Industry function."""

    class _IndustryStatisticsAccessor:
        """Minimal accessor for industry tests supporting link port queries."""

        def __init__(self):
            self.calls: list[dict] = []

        def energy_balance(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby: list[str] | None = None,
            direction: str = "withdrawal",
            at_port: list[str] | None = None,
        ) -> pd.Series:
            """Return deterministic Series matching the requested grouping."""
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "direction": direction,
                    "at_port": at_port,
                }
            )

            if groupby is None:
                groupby = ["carrier", "country", "unit"]

            carriers = carrier if isinstance(carrier, list) else [carrier or "default"]
            index_tuples = []
            values = []

            for c in carriers:
                idx_dict = {
                    "carrier": c,
                    "country": "AT",
                    "unit": "MWh_th",
                }
                index_tuples.append(tuple(idx_dict[key] for key in groupby))
                if components == "Load":
                    values.append(100.0)
                elif components == "Link" and at_port == ["bus0"]:
                    values.append(10.0)
                elif components == "Link" and at_port == ["bus1"]:
                    values.append(7.0)
                else:
                    values.append(0.0)

            return pd.Series(
                values,
                index=pd.MultiIndex.from_tuples(index_tuples, names=groupby),
                dtype=float,
            )

    class _IndustryNetwork:
        """Minimal network object exposing an industry-specific statistics accessor."""

        def __init__(self):
            self.statistics = (
                TestFinalEnergyBySectorIndustry._IndustryStatisticsAccessor()
            )

    def _industry_network(self):
        return self._IndustryNetwork()

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert isinstance(result, pd.Series)

    def test_has_country_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with country and unit levels."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["country", "unit"]

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_austria(self, mock_network: MockPyPSANetwork):
        """Test that result contains Austria (AT) data."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert "AT" in result.index.get_level_values("country")

    def test_adds_cc_efficiency_losses(self):
        """Test that CC link losses are added to load statistics."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        # 8 load carriers at 100 each + 3 CC losses at (10-7) each = 809
        assert result.loc[("AT", "MWh_th")] == 809.0

    def test_uses_both_link_ports_for_cc_losses(self):
        """Test that CC losses are computed from bus0 and bus1 link balances."""
        network = self._industry_network()
        _ = Final_Energy_by_Sector__Industry(network)

        link_calls = [
            call
            for call in network.statistics.calls
            if call["components"] == "Link" and call["at_port"] in (["bus0"], ["bus1"])
        ]
        assert len(link_calls) == 2
        assert {tuple(call["at_port"]) for call in link_calls} == {("bus0",), ("bus1",)}

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for _ in mock_network_collection:
            result = Final_Energy_by_Sector__Industry(self._industry_network())
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["country", "unit"]
            assert len(result) > 0
