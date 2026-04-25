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

    class _ElectricityStatisticsAccessor:
        """Minimal accessor to verify electricity-carrier extraction behavior."""

        def __init__(self, empty_dac: bool = False):
            self.empty_dac = empty_dac
            self.calls: list[dict] = []

        @staticmethod
        def _series_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_el",
        ) -> pd.Series:
            index = pd.MultiIndex.from_tuples(
                [tuple({"location": location, "unit": unit}[k] for k in groupby)],
                names=groupby,
            )
            return pd.Series(values, index=index, dtype=float)

        def withdrawal(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            aggregate_time: bool = True,
            groupby: list[str] | None = None,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "aggregate_time": aggregate_time,
                    "groupby": groupby,
                    "nice_names": nice_names,
                }
            )

            if groupby is None:
                groupby = ["location", "unit"]

            if carrier == ["agriculture electricity", "agriculture machinery electric"]:
                return self._series_from_groupby(groupby, [10.0])

            if bus_carrier == "low voltage" and components is None:
                index = pd.MultiIndex.from_tuples(
                    [
                        ("n1", "AT1 bus", "household demand", "AT1", "MWh_el"),
                        ("n2", "AT1 bus", "rural air heat pump", "AT1", "MWh_el"),
                        ("n3", "AT1 bus", "industry electricity", "AT1", "MWh_el"),
                        ("n4", "AT1 bus", "agriculture electricity", "AT1", "MWh_el"),
                        ("n5", "AT1 bus", "BEV charger", "AT1", "MWh_el"),
                        ("n6", "AT1 bus", "distribution losses", "AT1", "MWh_el"),
                        (
                            "n7",
                            "AT1 bus",
                            "urban central resistive heater",
                            "AT1",
                            "MWh_el",
                        ),
                    ],
                    names=["name", "bus", "carrier", "location", "unit"],
                )
                return pd.Series(
                    [7.0, 8.0, 100.0, 200.0, 300.0, 400.0, 500.0], index=index
                )

            if (
                bus_carrier == "low voltage"
                and carrier == "BEV charger"
                and components == "Link"
            ):
                return self._series_from_groupby(groupby, [40.0])

            if carrier == "industry electricity" and components == "Load":
                return self._series_from_groupby(groupby, [50.0])

            if bus_carrier == "AC" and carrier == "DAC" and components == "Link":
                if self.empty_dac:
                    return pd.Series(
                        dtype=float,
                        index=pd.MultiIndex.from_tuples([], names=groupby),
                    )
                return self._series_from_groupby(groupby, [60.0])

            return pd.Series(
                dtype=float,
                index=pd.MultiIndex.from_tuples([], names=groupby),
            )

    class _ElectricityNetwork:
        """Minimal network exposing the custom electricity statistics accessor."""

        def __init__(self, empty_dac: bool = False):
            self.statistics = (
                TestFinalEnergyByCarrierElectricity._ElectricityStatisticsAccessor(
                    empty_dac=empty_dac
                )
            )

    def _electricity_network(self, empty_dac: bool = False):
        return self._ElectricityNetwork(empty_dac=empty_dac)

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

    def test_filters_forbidden_low_voltage_carriers(self):
        """Residential/commercial low-voltage sum excludes forbidden carrier patterns."""
        result = Final_Energy_by_Carrier__Electricity(self._electricity_network())
        # Only household demand (7) and rural air heat pump (8) must remain from LV.
        assert 15.0 in result.values
        assert 100.0 not in result.values
        assert 200.0 not in result.values
        assert 300.0 not in result.values
        assert 400.0 not in result.values
        assert 500.0 not in result.values

    def test_includes_all_non_empty_contributions_in_order(self):
        """Result concatenates agriculture, res/com, transport, industry, and DAC."""
        result = Final_Energy_by_Carrier__Electricity(self._electricity_network())
        assert list(result.values) == [10.0, 15.0, 40.0, 50.0, 60.0]

    def test_ignores_empty_contributions_before_concat(self):
        """Empty contribution series are removed before concatenation."""
        result = Final_Energy_by_Carrier__Electricity(
            self._electricity_network(empty_dac=True)
        )
        assert list(result.values) == [10.0, 15.0, 40.0, 50.0]

    def test_issues_expected_withdrawal_queries(self):
        """Function requests the expected carrier/component combinations."""
        network = self._electricity_network()
        _ = Final_Energy_by_Carrier__Electricity(network)
        calls = network.statistics.calls
        assert len(calls) == 5

        assert calls[0]["carrier"] == [
            "agriculture electricity",
            "agriculture machinery electric",
        ]
        assert calls[0]["components"] == "Load"

        assert calls[1]["bus_carrier"] == "low voltage"
        assert calls[1]["components"] is None

        assert calls[2]["bus_carrier"] == "low voltage"
        assert calls[2]["carrier"] == "BEV charger"
        assert calls[2]["components"] == "Link"

        assert calls[3]["carrier"] == "industry electricity"
        assert calls[3]["components"] == "Load"

        assert calls[4]["bus_carrier"] == "AC"
        assert calls[4]["carrier"] == "DAC"
        assert calls[4]["components"] == "Link"


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Transportation
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorTransportation:
    """Test suite for Final_Energy_by_Sector__Transportation function."""

    def test_returns_series(self, mock_network: MockPyPSANetwork, energy_totals_csv):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_csv
        )
        assert isinstance(result, pd.Series)

    def test_has_location_and_unit_multiindex(
        self, mock_network: MockPyPSANetwork, energy_totals_csv
    ):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_csv
        )
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork, energy_totals_csv):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_csv
        )
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork, energy_totals_csv):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_csv
        )
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_multiple_locations(
        self, mock_network: MockPyPSANetwork, energy_totals_csv
    ):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_csv
        )
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(
        self, mock_network_collection: MockNetworkCollection, energy_totals_csv
    ):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Transportation(
                network, energy_totals=energy_totals_csv
            )
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert "location" in result.index.names
            assert "unit" in result.index.names
            assert len(result) > 0

    def test_raises_without_energy_totals(self, mock_network: MockPyPSANetwork):
        """Current implementation requires energy_totals to compute domestic shares."""
        with pytest.raises(ValueError):
            Final_Energy_by_Sector__Transportation(mock_network)


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
        Final_Energy_by_Sector__Agriculture,
    ]

    def test_transportation_returns_dataframe(
        self, mock_network: MockPyPSANetwork, energy_totals_csv
    ):
        """Transportation returns a DataFrame when aggregate_per_year=False."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network,
            aggregate_per_year=False,
            energy_totals=energy_totals_csv,
        )
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names
        assert isinstance(result.columns, pd.DatetimeIndex)
        assert len(result) > 0

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
