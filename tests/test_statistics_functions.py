"""Tests for pypsa_validation_processing.statistics_functions."""

from __future__ import annotations

import pandas as pd
import pytest

from pypsa_validation_processing.statistics_functions import (
    Final_Energy_by_Carrier__Electricity,
    Final_Energy_by_Sector__Industry,
    Final_Energy_by_Sector__Agriculture,
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

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

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

    def test_contains_multiple_locations(self, mock_network: MockPyPSANetwork):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Carrier__Electricity(mock_network)
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Carrier__Electricity(network)
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]
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

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

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

    def test_contains_multiple_locations(self, mock_network: MockPyPSANetwork):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Sector__Transportation(mock_network)
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Transportation(network)
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Agriculture
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorAgriculture:
    """Test suite for Final_Energy_by_Sector__Agriculture function."""

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert isinstance(result, pd.Series)

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_multiple_locations(self, mock_network: MockPyPSANetwork):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Agriculture(network)
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]
            assert len(result) > 0

    def test_without_carbon_capture_carriers(self, mock_network: MockPyPSANetwork):
        """Test that function works correctly when no CC carriers are present."""
        # Ensure carriers index is empty (no CC carriers)
        mock_network.carriers = pd.DataFrame(index=[])
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_with_carbon_capture_carriers(self, mock_network: MockPyPSANetwork):
        """Test that efficiency loss from CC carriers is added to result."""
        # Add carbon capture carriers to the network
        mock_network.carriers = pd.DataFrame(
            index=["agriculture machinery oil CC", "agriculture machinery oil"]
        )
        result = Final_Energy_by_Sector__Agriculture(mock_network)
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        # Result should still have valid data
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
            groupby_time: bool = True,
        ) -> pd.Series | pd.DataFrame:
            """Return deterministic Series matching the requested grouping."""
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "direction": direction,
                    "at_port": at_port,
                    "groupby_time": groupby_time,
                }
            )

            if groupby is None:
                groupby = ["carrier", "location", "unit"]

            carriers = carrier if isinstance(carrier, list) else [carrier or "default"]
            index_tuples = []
            values = []

            for c in carriers:
                idx_dict = {
                    "carrier": c,
                    "location": "AT1",
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

            index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)
            if groupby_time:
                return pd.Series(values, index=index, dtype=float)
            else:
                timestamps = pd.date_range("2019-01-01", periods=4, freq="6h", name="snapshot")
                return pd.DataFrame(
                    {ts: values for ts in timestamps},
                    index=index,
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

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

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

    def test_contains_at1_location(self, mock_network: MockPyPSANetwork):
        """Test that result contains AT1 locational data."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        assert "AT1" in result.index.get_level_values("location")

    def test_adds_cc_efficiency_losses(self):
        """Test that CC link losses are added to load statistics."""
        result = Final_Energy_by_Sector__Industry(self._industry_network())
        # 8 load carriers at 100 each + 3 CC losses at (10-7) each = 809
        assert result.loc[("AT1", "MWh_th")] == 809.0

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
            assert result.index.names == ["location", "unit"]
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for aggregate_per_year=False (timeseries output)
# ---------------------------------------------------------------------------


class TestAggregatePerYearFalse:
    """Tests verifying that all statistics functions return a DataFrame with
    snapshot columns when called with ``aggregate_per_year=False``."""

    _FUNCTIONS = [
        Final_Energy_by_Carrier__Electricity,
        Final_Energy_by_Sector__Transportation,
        Final_Energy_by_Sector__Agriculture,
    ]

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_returns_dataframe(self, mock_network: MockPyPSANetwork, func):
        """Function returns a DataFrame (not a Series) when aggregate_per_year=False."""
        result = func(mock_network, aggregate_per_year=False)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork, func):
        """DataFrame has MultiIndex with location and unit levels."""
        result = func(mock_network, aggregate_per_year=False)
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_columns_are_timestamps(self, mock_network: MockPyPSANetwork, func):
        """DataFrame columns are a DatetimeIndex (snapshot timestamps)."""
        result = func(mock_network, aggregate_per_year=False)
        assert isinstance(result.columns, pd.DatetimeIndex)

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_not_empty(self, mock_network: MockPyPSANetwork, func):
        """DataFrame is not empty."""
        result = func(mock_network, aggregate_per_year=False)
        assert not result.empty

    def test_industry_returns_dataframe(self):
        """Final_Energy_by_Sector__Industry returns DataFrame for aggregate_per_year=False."""

        class _TS_IndustryStatisticsAccessor:
            def energy_balance(self, **kwargs):
                groupby = kwargs.get("groupby", ["carrier", "location", "unit"])
                carriers = kwargs.get("carrier") or ["default"]
                if isinstance(carriers, str):
                    carriers = [carriers]
                index_tuples = [
                    tuple({"carrier": c, "location": "AT1", "unit": "MWh_th"}[k] for k in groupby)
                    for c in carriers
                ]
                values = [10.0] * len(index_tuples)
                index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)
                groupby_time = kwargs.get("groupby_time", True)
                if groupby_time:
                    return pd.Series(values, index=index, dtype=float)
                timestamps = pd.date_range("2019-01-01", periods=4, freq="6h", name="snapshot")
                return pd.DataFrame({ts: values for ts in timestamps}, index=index, dtype=float)

        class _TS_IndustryNetwork:
            def __init__(self):
                self.statistics = _TS_IndustryStatisticsAccessor()

        result = Final_Energy_by_Sector__Industry(_TS_IndustryNetwork(), aggregate_per_year=False)
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names
        assert isinstance(result.columns, pd.DatetimeIndex)
