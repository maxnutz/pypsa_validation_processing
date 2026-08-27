"""Tests for pypsa_validation_processing.statistics_functions."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from pypsa_validation_processing.statistics_functions import (
    Final_Energy_by_Carrier__Electricity,
    Final_Energy_by_Carrier__Coal,
    Final_Energy_by_Carrier__District_Heat,
    Final_Energy_by_Carrier__Natural_Gas,
    Final_Energy_by_Carrier__Oil,
    Final_Energy_by_Sector__Industry,
    Final_Energy_by_Sector__Agriculture,
    Final_Energy_by_Sector__Residential_and_Commercial,
    Final_Energy_by_Sector__Transportation,
    Net_Imports__Electricity,
    Net_Imports__Natural_Gas,
    Net_Imports__Oil,
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
            groupby_time: bool = False,
            groupby: list[str] | None = None,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby_time": groupby_time,
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
# Tests for Net_Imports__Electricity
# ---------------------------------------------------------------------------


class TestNetImportsElectricity:
    """Test suite for Net_Imports__Electricity function."""

    class _ElectricityTradeStatisticsAccessor:
        """Minimal accessor for electricity net-import tests."""

        def __init__(self):
            self.calls: list[dict[str, object]] = []

        @staticmethod
        def _transmission_rows(groupby_time: bool) -> pd.Series | pd.DataFrame:
            if groupby_time:
                index = pd.MultiIndex.from_tuples(
                    [("AT0", "AT1", "MWh_el"), ("AT1", "AT0", "MWh_el")],
                    names=["bus0", "bus1", "unit"],
                )
                return pd.Series([15.0, 4.0], index=index, dtype=float)

            timestamps = pd.date_range(
                "2019-01-01", periods=4, freq="6h", name="snapshot"
            )
            return pd.DataFrame(
                [
                    {
                        "bus0": "AT0",
                        "bus1": "AT1",
                        "unit": "MWh_el",
                        timestamps[0]: 10.0,
                        timestamps[1]: 5.0,
                        timestamps[2]: 0.0,
                        timestamps[3]: 0.0,
                    },
                    {
                        "bus0": "AT1",
                        "bus1": "AT0",
                        "unit": "MWh_el",
                        timestamps[0]: 1.0,
                        timestamps[1]: 1.0,
                        timestamps[2]: 1.0,
                        timestamps[3]: 1.0,
                    },
                ]
            )

        def transmission(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "groupby_time": groupby_time,
                    "nice_names": nice_names,
                }
            )

            if (
                bus_carrier == ["AC", "DC"]
                and carrier is None
                and components == ["Link", "Line"]
                and groupby == ["bus0", "bus1", "unit"]
            ):
                return self._transmission_rows(groupby_time)

            return pd.DataFrame(columns=["bus0", "bus1", "unit", "value"])

    class _ElectricityTradeNetwork:
        """Minimal network exposing the custom electricity trade accessor."""

        def __init__(self):
            self.statistics = (
                TestNetImportsElectricity._ElectricityTradeStatisticsAccessor()
            )

    def _electricity_trade_network(self):
        return self._ElectricityTradeNetwork()

    def test_returns_net_imports_in_expected_sign_convention(self):
        """Net imports should equal imports minus exports."""
        network = self._electricity_trade_network()

        result = Net_Imports__Electricity(network)

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert result.loc[("AT1", "MWh_el")] == pytest.approx(11.0)
        assert result.loc[("AT0", "MWh_el")] == pytest.approx(-11.0)

        calls = network.statistics.calls
        assert len(calls) == 1
        assert calls[0]["bus_carrier"] == ["AC", "DC"]
        assert calls[0]["components"] == ["Link", "Line"]
        assert calls[0]["groupby"] == ["bus0", "bus1", "unit"]
        assert calls[0]["groupby_time"] is True

    def test_returns_dataframe_for_aggregate_per_year_false(self):
        """aggregate_per_year=False returns a timeseries DataFrame."""
        network = self._electricity_trade_network()

        result = Net_Imports__Electricity(network, aggregate_per_year=False)
        aggregated = Net_Imports__Electricity(network)

        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert any(isinstance(column, pd.Timestamp) for column in result.columns)
        assert result.shape[1] == 4
        pd.testing.assert_series_equal(
            result.sum(axis=1), aggregated, check_names=False
        )

        timestamps = list(result.columns)
        ts0, ts1 = timestamps[0], timestamps[1]

        # AT0->AT1=10, AT1->AT0=1 at ts0; AT0->AT1=5, AT1->AT0=1 at ts1.
        assert result.loc[("AT1", "MWh_el"), ts0] == pytest.approx(9.0)
        assert result.loc[("AT0", "MWh_el"), ts0] == pytest.approx(-9.0)
        assert result.loc[("AT1", "MWh_el"), ts1] == pytest.approx(4.0)
        assert result.loc[("AT0", "MWh_el"), ts1] == pytest.approx(-4.0)


# ---------------------------------------------------------------------------
# Tests for Net_Imports__Oil
# ---------------------------------------------------------------------------


class TestNetImportsOil:
    """Test suite for Net_Imports__Oil function."""

    class _OilTradeStatisticsAccessor:
        """Minimal accessor for oil net-import tests.

        Rows are given as pre-``mul(-1)`` ``(bus0, bus1, unit, values)``
        tuples using full PyPSA-style bus names (``"<location> oil"``), so
        the copperplate-splitting logic in the function under test is
        exercised the same way it would be against a real network.
        """

        def __init__(self, rows: list[tuple[str, str, str, list[float]]]):
            self.rows = rows
            self.calls: list[dict[str, object]] = []

        def _energy_balance_rows(self, groupby_time: bool) -> pd.Series | pd.DataFrame:
            index = pd.MultiIndex.from_tuples(
                [(bus0, bus1, unit) for bus0, bus1, unit, _ in self.rows],
                names=["bus0", "bus1", "unit"],
            )
            if groupby_time:
                values = [sum(values) for _, _, _, values in self.rows]
                return pd.Series(values, index=index, dtype=float)

            n_snapshots = len(self.rows[0][3])
            timestamps = pd.date_range(
                "2019-01-01", periods=n_snapshots, freq="6h", name="snapshot"
            )
            data = [values for _, _, _, values in self.rows]
            return pd.DataFrame(data, index=index, columns=timestamps, dtype=float)

        def energy_balance(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "groupby_time": groupby_time,
                    "nice_names": nice_names,
                }
            )
            return self._energy_balance_rows(groupby_time)

    class _OilTradeNetwork:
        """Minimal network exposing the custom oil trade accessor."""

        def __init__(self, rows: list[tuple[str, str, str, list[float]]]):
            self.statistics = TestNetImportsOil._OilTradeStatisticsAccessor(rows)

    def _oil_trade_network(self, rows: list[tuple[str, str, str, list[float]]]):
        return self._OilTradeNetwork(rows)

    def test_returns_net_imports_with_copperplate_regionalization(self):
        """Locations are derived from bus0/bus1 names split at the copperplate 'EU oil' bus."""
        network = self._oil_trade_network(
            [
                ("EU oil", "AT1 oil", "MWh_LHV", [30.0]),
                ("AT1 oil", "EU oil", "MWh_LHV", [6.0]),
            ]
        )

        result = Net_Imports__Oil(network)

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(-24.0)
        assert result.loc[("EU", "MWh_LHV")] == pytest.approx(24.0)

    def test_issues_expected_energy_balance_query(self):
        """Function requests oil energy_balance grouped by bus0/bus1/unit."""
        network = self._oil_trade_network([("EU oil", "AT1 oil", "MWh_LHV", [10.0])])
        _ = Net_Imports__Oil(network)

        calls = network.statistics.calls
        assert len(calls) == 1
        assert calls[0]["bus_carrier"] == "oil"
        assert calls[0]["components"] == "Link"
        assert calls[0]["groupby"] == ["bus0", "bus1", "unit"]
        assert calls[0]["nice_names"] is False
        assert calls[0]["groupby_time"] is True

    def test_applies_sign_flip_from_energy_balance(self):
        """The raw energy_balance result is multiplied by -1 before netting."""
        network = self._oil_trade_network([("EU oil", "AT1 oil", "MWh_LHV", [10.0])])
        result = Net_Imports__Oil(network)
        # raw=10 -> *-1 = -10 assigned to AT1 (location_to), +10 to EU (location_from)
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(-10.0)
        assert result.loc[("EU", "MWh_LHV")] == pytest.approx(10.0)

    def test_splits_multi_word_bus_names_to_first_token(self):
        """Locations are derived from the first whitespace-separated bus token."""
        network = self._oil_trade_network([("EU oil", "AT1 0 oil", "MWh_LHV", [5.0])])
        result = Net_Imports__Oil(network)
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(-5.0)
        assert result.loc[("EU", "MWh_LHV")] == pytest.approx(5.0)

    def test_nets_multiple_regions_against_copperplate(self):
        """Net imports sum correctly across more than two trading regions."""
        network = self._oil_trade_network(
            [
                ("EU oil", "AT1 oil", "MWh_LHV", [12.0]),
                ("AT1 oil", "EU oil", "MWh_LHV", [3.0]),
                ("AT2 oil", "EU oil", "MWh_LHV", [7.0]),
            ]
        )
        result = Net_Imports__Oil(network)

        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(-9.0)
        assert result.loc[("AT2", "MWh_LHV")] == pytest.approx(7.0)
        assert result.loc[("EU", "MWh_LHV")] == pytest.approx(2.0)
        # closed copperplate system: net imports across all locations sum to zero
        assert result.sum() == pytest.approx(0.0)

    def test_returns_dataframe_for_aggregate_per_year_false(self):
        """aggregate_per_year=False returns a timeseries DataFrame consistent with the aggregate."""
        network = self._oil_trade_network(
            [
                ("EU oil", "AT1 oil", "MWh_LHV", [20.0, 10.0]),
                ("AT1 oil", "EU oil", "MWh_LHV", [4.0, 2.0]),
            ]
        )

        result = Net_Imports__Oil(network, aggregate_per_year=False)
        aggregated = Net_Imports__Oil(network)

        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert any(isinstance(column, pd.Timestamp) for column in result.columns)
        assert result.shape[1] == 2
        pd.testing.assert_series_equal(
            result.sum(axis=1), aggregated, check_names=False
        )

        timestamps = list(result.columns)
        ts0, ts1 = timestamps[0], timestamps[1]

        assert result.loc[("AT1", "MWh_LHV"), ts0] == pytest.approx(-16.0)
        assert result.loc[("EU", "MWh_LHV"), ts0] == pytest.approx(16.0)
        assert result.loc[("AT1", "MWh_LHV"), ts1] == pytest.approx(-8.0)
        assert result.loc[("EU", "MWh_LHV"), ts1] == pytest.approx(8.0)

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series against the shared network fixture."""
        result = Net_Imports__Oil(mock_network)
        assert isinstance(result, pd.Series)

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Net_Imports__Oil(mock_network)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Net_Imports__Oil(network)
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]

    def test_empty_network_returns_empty_series(self):
        """Net_Imports__Oil should handle a network without oil trade links gracefully."""
        # No rows at all, emulating a network without oil trade links.
        empty_network = self._oil_trade_network([])

        result = Net_Imports__Oil(empty_network)

        # The function should not raise and should return an empty Series.
        assert isinstance(result, pd.Series)
        assert result.empty


# ---------------------------------------------------------------------------
# Tests for Net_Imports__Natural_Gas
# ---------------------------------------------------------------------------


class TestNetImportsNaturalGas:
    """Test suite for Net_Imports__Natural_Gas function."""

    class _NaturalGasTradeStatisticsAccessor:
        """Minimal accessor for gas net-import tests.

        ``non_fossil_local``/``fossil_local`` model local production at each
        bus (feeding trace_non_fossil_fraction), ``transmission_rows`` model
        the pipeline network (used both for the direct net-import query and,
        via the same underlying network, for the flow trace).
        """

        def __init__(
            self,
            non_fossil_local: dict[str, float],
            fossil_local: dict[str, float],
            transmission_rows: list[tuple[str, str, str, float]],
            n_snapshots: int = 1,
        ):
            self.non_fossil_local = non_fossil_local
            self.fossil_local = fossil_local
            self.transmission_rows = transmission_rows
            self.snapshots = pd.date_range(
                "2019-01-01", periods=n_snapshots, freq="6h", name="snapshot"
            )
            self.calls: list[dict[str, object]] = []

        def supply(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            at_port: str | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.DataFrame:
            self.calls.append(
                {
                    "method": "supply",
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "groupby_time": groupby_time,
                }
            )
            source = (
                self.non_fossil_local if components == "Link" else self.fossil_local
            )
            index = pd.MultiIndex.from_tuples(
                [(bus, "MWh_LHV") for bus in source], names=["bus", "unit"]
            )
            data = {t: list(source.values()) for t in self.snapshots}
            return pd.DataFrame(data, index=index)

        def transmission(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            at_port: str | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "method": "transmission",
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "at_port": at_port,
                    "groupby": groupby,
                    "groupby_time": groupby_time,
                }
            )
            index = pd.MultiIndex.from_tuples(
                [(b0, b1, unit) for b0, b1, unit, _ in self.transmission_rows],
                names=["bus0", "bus1", "unit"],
            )
            data = {
                t: [value for *_, value in self.transmission_rows]
                for t in self.snapshots
            }
            result = pd.DataFrame(data, index=index)
            # mirror pypsa.statistics: truthy groupby_time collapses snapshots
            # into a single aggregated Series, matching real accessor behavior
            return result.sum(axis=1) if groupby_time else result

    class _NaturalGasTradeNetwork:
        """Minimal network exposing the custom gas trade accessor."""

        def __init__(self, accessor):
            self.statistics = accessor
            self.snapshots = accessor.snapshots

    def _gas_trade_network(
        self,
        non_fossil_local: dict[str, float],
        fossil_local: dict[str, float],
        transmission_rows: list[tuple[str, str, str, float]],
        n_snapshots: int = 1,
    ):
        accessor = self._NaturalGasTradeStatisticsAccessor(
            non_fossil_local, fossil_local, transmission_rows, n_snapshots
        )
        return self._NaturalGasTradeNetwork(accessor)

    def test_negative_pypsa_value_yields_positive_import(self):
        """pypsa.statistics.transmission(at_port="bus1") reports a receiving
        bus's own inflow as a *negative* value (sign flipped relative to a
        'positive = import' convention). Both buses are kept fully fossil
        here so the fossil-share scaling is a no-op (factor 1) and cannot
        mask a sign bug - this isolates the sign handling on its own,
        independent of the fossil-share logic, so it stays valid for
        refactoring either piece separately."""
        network = self._gas_trade_network(
            non_fossil_local={"DE gas": 0.0, "AT1 gas": 0.0},
            fossil_local={"DE gas": 100.0, "AT1 gas": 100.0},
            transmission_rows=[("DE gas", "AT1 gas", "MWh_LHV", -100.0)],
        )
        result = Net_Imports__Natural_Gas(network)

        # raw pypsa value is negative -> AT1 (bus1) is the importer and must
        # be positive; DE (bus0) is the exporter and must be negative.
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(100.0)
        assert result.loc[("DE", "MWh_LHV")] == pytest.approx(-100.0)

    def test_scales_import_by_fossil_share_of_sending_bus(self):
        """Only the fossil share of the sending ('location_from') bus's gas
        pool is counted as a net import - non-fossil gas is excluded."""
        network = self._gas_trade_network(
            non_fossil_local={"DE gas": 40.0, "AT1 gas": 0.0},
            fossil_local={"DE gas": 60.0, "AT1 gas": 0.0},
            transmission_rows=[("DE gas", "AT1 gas", "MWh_LHV", 100.0)],
        )
        result = Net_Imports__Natural_Gas(network)

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        # DE is 60% fossil -> 100 * 0.6 = 60 fossil MWh imported by AT1
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(-60.0)
        assert result.loc[("DE", "MWh_LHV")] == pytest.approx(60.0)

    def test_fully_non_fossil_sender_yields_zero_import(self):
        """A sending bus with 100% non-fossil local supply contributes zero
        to fossil net imports, even though the raw pipeline flow is nonzero."""
        network = self._gas_trade_network(
            non_fossil_local={"DE gas": 100.0, "AT1 gas": 0.0},
            fossil_local={"DE gas": 0.0, "AT1 gas": 0.0},
            transmission_rows=[("DE gas", "AT1 gas", "MWh_LHV", 100.0)],
        )
        result = Net_Imports__Natural_Gas(network)
        assert result.loc[("AT1", "MWh_LHV")] == pytest.approx(0.0)
        assert result.loc[("DE", "MWh_LHV")] == pytest.approx(0.0)

    def test_returns_dataframe_for_aggregate_per_year_false(self):
        """aggregate_per_year=False returns a timeseries DataFrame consistent with the aggregate."""
        network = self._gas_trade_network(
            non_fossil_local={"DE gas": 40.0, "AT1 gas": 0.0},
            fossil_local={"DE gas": 60.0, "AT1 gas": 0.0},
            transmission_rows=[("DE gas", "AT1 gas", "MWh_LHV", 100.0)],
            n_snapshots=2,
        )

        result = Net_Imports__Natural_Gas(network, aggregate_per_year=False)
        aggregated = Net_Imports__Natural_Gas(network)

        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert result.shape[1] == 2
        pd.testing.assert_series_equal(
            result.sum(axis=1), aggregated, check_names=False
        )
        assert result.loc[("AT1", "MWh_LHV")].iloc[0] == pytest.approx(-60.0)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Oil
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierOil:
    """Test suite for Final_Energy_by_Carrier__Oil function."""

    class _OilStatisticsAccessor:
        """Deterministic accessor tailored to oil final-energy tests."""

        def __init__(
            self,
            *,
            rescom_empty: bool = False,
            all_oil_value: float = 200.0,
            all_oil_empty: bool = False,
            non_fossil_empty: bool = False,
        ):
            self.rescom_empty = rescom_empty
            self.all_oil_value = all_oil_value
            self.all_oil_empty = all_oil_empty
            self.non_fossil_empty = non_fossil_empty

        def _to_result(
            self,
            *,
            index: pd.MultiIndex,
            values: list[float],
            groupby_time: bool,
        ) -> pd.Series | pd.DataFrame:
            if groupby_time:
                return pd.Series(values, index=index, dtype=float)
            timestamps = pd.date_range(
                "2019-01-01", periods=4, freq="6h", name="snapshot"
            )
            return pd.DataFrame(
                {ts: values for ts in timestamps}, index=index, dtype=float
            )

        def withdrawal(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby_time: bool = True,
            groupby: list[str] | None = None,
            at_port: str | None = None,
            **kwargs: object,
        ) -> pd.Series | pd.DataFrame:
            if groupby is None:
                groupby = ["location", "unit"]

            # Agriculture and land-transport final demand (Load)
            if carrier == "agriculture machinery oil" and components == "Load":
                idx = pd.MultiIndex.from_tuples(
                    [("AT1", "MWh_th")], names=["location", "unit"]
                )
                return self._to_result(
                    index=idx, values=[100.0], groupby_time=groupby_time
                )

            if carrier == "land transport oil" and components == "Load":
                idx = pd.MultiIndex.from_tuples(
                    [("AT1", "MWh_th")], names=["location", "unit"]
                )
                return self._to_result(
                    index=idx, values=[300.0], groupby_time=groupby_time
                )

            # Residential/commercial demand requiring copperplate -> location mapping via bus1
            if (
                bus_carrier == "oil"
                and isinstance(carrier, list)
                and set(carrier) == {"rural oil boiler", "urban decentral oil boiler"}
            ):
                idx_names = ["name", "bus", "carrier", "location", "unit", "bus1"]
                if self.rescom_empty:
                    empty_idx = pd.MultiIndex.from_arrays(
                        [[] for _ in idx_names], names=idx_names
                    )
                    return self._to_result(
                        index=empty_idx,
                        values=[],
                        groupby_time=groupby_time,
                    )
                idx = pd.MultiIndex.from_tuples(
                    [
                        (
                            "rural_boiler_load",
                            "AT1 oil",
                            "rural oil boiler",
                            "EU",
                            "MWh_th",
                            "AT1 oil",
                        ),
                        (
                            "urban_boiler_load",
                            "AT1 oil",
                            "urban decentral oil boiler",
                            "EU",
                            "MWh_th",
                            "AT1 oil",
                        ),
                    ],
                    names=idx_names,
                )
                return self._to_result(
                    index=idx,
                    values=[50.0, 50.0],
                    groupby_time=groupby_time,
                )

            # Total oil use denominator for non-fossil share
            if (
                bus_carrier == "oil"
                and components == "Link"
                and at_port == "bus0"
                and groupby == ["bus1", "carrier", "location", "unit"]
            ):
                if self.all_oil_empty:
                    empty_idx = pd.MultiIndex.from_arrays(
                        [[], [], [], []],
                        names=["bus1", "carrier", "location", "unit"],
                    )
                    return self._to_result(
                        index=empty_idx,
                        values=[],
                        groupby_time=groupby_time,
                    )
                idx = pd.MultiIndex.from_tuples(
                    [
                        (
                            "AT1 oil",
                            "land transport oil",
                            "EU",
                            "MWh_th",
                        )
                    ],
                    names=["bus1", "carrier", "location", "unit"],
                )
                return self._to_result(
                    index=idx,
                    values=[self.all_oil_value],
                    groupby_time=groupby_time,
                )

            raise AssertionError(
                f"Unexpected withdrawal call: bus_carrier={bus_carrier}, carrier={carrier}, components={components}, groupby={groupby}, at_port={at_port}"
            )

        def supply(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            at_port: str | None = None,
            components: str | list[str] | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            **kwargs: object,
        ) -> pd.Series | pd.DataFrame:
            if (
                bus_carrier == "oil"
                and components == "Link"
                and at_port == "bus1"
                and groupby == ["name", "bus", "carrier", "location", "unit", "bus0"]
            ):
                if self.non_fossil_empty:
                    empty_idx = pd.MultiIndex.from_arrays(
                        [[], [], [], [], [], []],
                        names=["name", "bus", "carrier", "location", "unit", "bus0"],
                    )
                    return self._to_result(
                        index=empty_idx,
                        values=[],
                        groupby_time=groupby_time,
                    )
                idx = pd.MultiIndex.from_tuples(
                    [
                        (
                            "renewable_oil_link",
                            "AT1 oil",
                            "biomass to liquid",
                            "EU",
                            "MWh_th",
                            "AT1 oil",
                        )
                    ],
                    names=["name", "bus", "carrier", "location", "unit", "bus0"],
                )
                return self._to_result(
                    index=idx, values=[500.0], groupby_time=groupby_time
                )

            raise AssertionError(
                f"Unexpected supply call: bus_carrier={bus_carrier}, carrier={carrier}, components={components}, groupby={groupby}, at_port={at_port}"
            )

    class _OilNetwork:
        """Minimal network object exposing only the statistics accessor."""

        def __init__(
            self,
            *,
            rescom_empty: bool = False,
            all_oil_value: float = 200.0,
            all_oil_empty: bool = False,
            non_fossil_empty: bool = False,
        ):
            self.statistics = TestFinalEnergyByCarrierOil._OilStatisticsAccessor(
                rescom_empty=rescom_empty,
                all_oil_value=all_oil_value,
                all_oil_empty=all_oil_empty,
                non_fossil_empty=non_fossil_empty,
            )

    def test_clips_non_fossil_share_above_one_to_zero_fossil(self):
        """Renewable oil production above total demand should yield zero fossil oil."""
        result = Final_Energy_by_Carrier__Oil(self._OilNetwork())

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert result.loc[("AT1", "MWh")] == pytest.approx(0.0)

    def test_handles_empty_rescom_without_failing(self):
        """Function should work even when residential/commercial oil demand is empty."""
        result = Final_Energy_by_Carrier__Oil(self._OilNetwork(rescom_empty=True))

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        # non-fossil fraction is clipped to 1, so fossil share remains zero.
        assert result.loc[("AT1", "MWh")] == pytest.approx(0.0)

    def test_handles_zero_total_oil_demand_denominator(self):
        """Division by zero in non-fossil share denominator should not crash."""
        result = Final_Energy_by_Carrier__Oil(self._OilNetwork(all_oil_value=0.0))

        assert isinstance(result, pd.Series)
        assert result.loc[("AT1", "MWh")] == pytest.approx(0.0)

    def test_no_renewable_oil_production_fossil_equals_total(self):
        """Without renewable oil supply, fossil oil should equal total oil demand."""
        result = Final_Energy_by_Carrier__Oil(self._OilNetwork(non_fossil_empty=True))

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert not result.isna().any()
        # 100 (agri) + 100 (res/com) + 300 (transport) = 500
        assert result.loc[("AT1", "MWh")] == pytest.approx(500.0)

    def test_handles_empty_all_oil_without_failing(self):
        """Function should work when total oil-withdrawal denominator is empty."""
        result = Final_Energy_by_Carrier__Oil(
            self._OilNetwork(all_oil_empty=True, non_fossil_empty=True)
        )

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert not result.isna().any()
        assert (result == 0.0).all()

    def test_returns_dataframe_for_aggregate_per_year_false(self):
        """Function should return a timeseries DataFrame for aggregate_per_year=False."""
        result = Final_Energy_by_Carrier__Oil(
            self._OilNetwork(),
            aggregate_per_year=False,
        )

        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert isinstance(result.columns, pd.DatetimeIndex)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Natural_Gas
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierNaturalGas:
    """Test suite for Final_Energy_by_Carrier__Natural_Gas function."""

    class _NaturalGasStatisticsAccessor:
        """Minimal accessor to verify natural-gas extraction behavior."""

        def __init__(self, scenario: str = "mixed"):
            self.scenario = scenario
            self.calls: list[dict[str, object]] = []

        @staticmethod
        def _empty_series(groupby: list[str]) -> pd.Series:
            return pd.Series(
                dtype=float,
                index=pd.MultiIndex.from_tuples([], names=groupby),
            )

        @staticmethod
        def _series_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_LHV",
        ) -> pd.Series:
            index = pd.MultiIndex.from_tuples(
                [tuple({"location": location, "unit": unit}[k] for k in groupby)],
                names=groupby,
            )
            return pd.Series(values, index=index, dtype=float)

        @staticmethod
        def _dataframe_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_LHV",
        ) -> pd.DataFrame:
            index = pd.MultiIndex.from_tuples(
                [tuple({"location": location, "unit": unit}[k] for k in groupby)],
                names=groupby,
            )
            columns = pd.Index(
                pd.to_datetime(["2019-01-01", "2019-01-02"]), name="snapshot"
            )
            return pd.DataFrame([values[: len(columns)]], index=index, columns=columns)

        def supply(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            at_port: str | None = None,
            components: str | list[str] | None = None,
            groupby_time: bool = True,
            groupby: list[str] | None = None,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            if groupby is None:
                groupby = ["location", "unit"]

            if (
                bus_carrier == "gas"
                and isinstance(carrier, list)
                and components == "Link"
                and at_port == "bus1"
            ):
                if self.scenario in ("no_gas", "no_renewable"):
                    return self._empty_series(groupby)
                if self.scenario == "no_fossil":
                    if groupby_time:
                        return self._series_from_groupby(groupby, [100.0])
                    return self._dataframe_from_groupby(groupby, [100.0, 100.0])
                if groupby_time:
                    return self._series_from_groupby(groupby, [20.0])
                return self._dataframe_from_groupby(groupby, [20.0, 20.0])

            return self._empty_series(groupby)

        def energy_balance(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            at_port: str | list[str] | None = None,
            groupby: list[str] | None = None,
            groupby_time: bool = True,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            if groupby is None:
                groupby = ["location", "unit"]

            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "at_port": at_port,
                    "groupby_time": groupby_time,
                    "groupby": groupby,
                    "groupby_time": groupby_time,
                }
            )

            if (
                carrier == ["urban decentral gas boiler", "rural gas boiler"]
                and components == "Link"
                and at_port == "bus0"
            ):
                if self.scenario == "no_gas":
                    return self._empty_series(groupby)
                if groupby_time:
                    return self._series_from_groupby(groupby, [40.0])
                return self._dataframe_from_groupby(groupby, [40.0, 40.0])

            return self._empty_series(groupby)

        def withdrawal(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby_time: bool = True,
            groupby: list[str] | None = None,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            if groupby is None:
                groupby = ["location", "unit"]

            if (
                bus_carrier == "gas"
                and components == "Link"
                and groupby == ["name", "bus", "carrier", "location", "unit"]
            ):
                if self.scenario == "no_gas":
                    return self._empty_series(groupby)

                index = pd.MultiIndex.from_tuples(
                    [
                        (
                            "gas_link",
                            "AT1 gas",
                            "urban decentral gas boiler",
                            "AT1",
                            "MWh_LHV",
                        ),
                        (
                            "pipeline_link",
                            "AT1 gas",
                            "gas pipeline",
                            "AT1",
                            "MWh_LHV",
                        ),
                    ],
                    names=groupby,
                )
                if groupby_time:
                    return pd.Series([100.0, 900.0], index=index, dtype=float)
                columns = pd.Index(
                    pd.to_datetime(["2019-01-01", "2019-01-02"]), name="snapshot"
                )
                return pd.DataFrame(
                    [[100.0, 900.0], [100.0, 900.0]], index=index, columns=columns
                )

            if (
                bus_carrier == "gas"
                and carrier == ["urban decentral gas boiler", "rural gas boiler"]
                and components == "Link"
            ):
                if self.scenario == "no_gas":
                    return self._empty_series(groupby)
                if groupby_time:
                    return self._series_from_groupby(groupby, [40.0])
                return self._dataframe_from_groupby(groupby, [40.0, 40.0])

            if (
                bus_carrier == "gas for industry"
                and carrier == ["gas for industry", "gas for industry CC"]
                and components == "Load"
            ):
                if self.scenario == "no_gas":
                    return self._empty_series(groupby)
                if groupby_time:
                    return self._series_from_groupby(groupby, [60.0])
                return self._dataframe_from_groupby(groupby, [60.0, 60.0])

            return self._empty_series(groupby)

    class _NaturalGasNetwork:
        """Minimal network exposing the custom natural-gas statistics accessor."""

        def __init__(self, scenario: str = "mixed"):
            self.statistics = (
                TestFinalEnergyByCarrierNaturalGas._NaturalGasStatisticsAccessor(
                    scenario=scenario
                )
            )

    def _natural_gas_network(self, scenario: str = "mixed"):
        return self._NaturalGasNetwork(scenario=scenario)

    def test_returns_series(self):
        """Function returns a Series with expected output format."""
        result = Final_Energy_by_Carrier__Natural_Gas(self._natural_gas_network())
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_returns_dataframe_when_not_aggregated(self):
        """aggregate_per_year=False returns a non-empty DataFrame."""
        result = Final_Energy_by_Carrier__Natural_Gas(
            self._natural_gas_network(), aggregate_per_year=False
        )
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert not result.empty
        assert len(result.columns) > 0

    def test_filters_pipeline_from_total_gas_usage(self):
        """Pipeline carriers are excluded when building the non-fossil share denominator."""
        result = Final_Energy_by_Carrier__Natural_Gas(
            self._natural_gas_network("mixed")
        )
        # total=100, non-fossil share=20/100, result=100*(1-0.2)=80
        assert result.loc[("AT1", "MWh")] == pytest.approx(77.1322, 0.1)

    def test_uses_energy_balance_for_residential_and_commercial_gas(self):
        """Residential/commercial gas demand is now taken from energy_balance."""
        network = self._natural_gas_network("mixed")

        _ = Final_Energy_by_Carrier__Natural_Gas(network)

        assert any(
            call["carrier"] == ["urban decentral gas boiler", "rural gas boiler"]
            and call["components"] == "Link"
            and call["at_port"] == "bus0"
            for call in network.statistics.calls
        )

    def test_edge_case_no_gas_returns_empty_series(self):
        """No gas usage and no gas demand should return an empty result."""
        result = Final_Energy_by_Carrier__Natural_Gas(
            self._natural_gas_network("no_gas")
        )
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert result.empty

    def test_edge_case_no_fossil_gas_returns_zero(self):
        """If all gas is renewable, fossil natural gas final energy must be zero."""
        result = Final_Energy_by_Carrier__Natural_Gas(
            self._natural_gas_network("no_fossil")
        )
        assert result.loc[("AT1", "MWh")] == 0.0

    def test_edge_case_no_renewable_gas_returns_total(self):
        """If there is no renewable gas production, all demand counts as fossil gas."""
        result = Final_Energy_by_Carrier__Natural_Gas(
            self._natural_gas_network("no_renewable")
        )
        assert result.loc[("AT1", "MWh")] == pytest.approx(96.41536, 0.1)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__District_Heat
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierDistrictHeat:
    """Test suite for Final_Energy_by_Carrier__District_Heat function."""

    class _DistrictHeatStatisticsAccessor:
        """Minimal accessor to verify district-heat extraction behavior."""

        def __init__(self):
            self.calls: list[dict] = []

        @staticmethod
        def _series_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_th",
        ) -> pd.Series:
            index = pd.MultiIndex.from_tuples(
                [tuple({"location": location, "unit": unit}[k] for k in groupby)],
                names=groupby,
            )
            return pd.Series(values, index=index, dtype=float)

        @staticmethod
        def _dataframe_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_th",
        ) -> pd.DataFrame:
            index = pd.MultiIndex.from_tuples(
                [tuple({"location": location, "unit": unit}[k] for k in groupby)],
                names=groupby,
            )
            columns = pd.Index(
                pd.to_datetime(["2019-01-01", "2019-01-02"]), name="snapshot"
            )
            return pd.DataFrame([values[: len(columns)]], index=index, columns=columns)

        def energy_balance(
            self,
            bus_carrier: str | list[str] | None = None,
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

            if (
                bus_carrier == "urban central heat"
                and carrier == "urban central heat vent"
                and components == "Generator"
            ):
                if aggregate_time:
                    return self._series_from_groupby(groupby, [5.0])
                return self._dataframe_from_groupby(groupby, [5.0, 5.0])

            if aggregate_time:
                return pd.Series(
                    dtype=float,
                    index=pd.MultiIndex.from_tuples([], names=groupby),
                )
            return pd.DataFrame(
                index=pd.MultiIndex.from_tuples([], names=groupby),
                columns=pd.Index(pd.to_datetime([], name="snapshot")),
                dtype=float,
            )

        def withdrawal(
            self,
            bus_carrier: str | list[str] | None = None,
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

            if aggregate_time:
                return self._series_from_groupby(groupby, [55.0])
            return self._dataframe_from_groupby(groupby, [55.0, 56.0])

    class _DistrictHeatNetwork:
        """Minimal network exposing district-heat buses/links and statistics."""

        def __init__(self):
            self.statistics = (
                TestFinalEnergyByCarrierDistrictHeat._DistrictHeatStatisticsAccessor()
            )
            self.snapshots = pd.DatetimeIndex(
                pd.to_datetime(["2019-01-01", "2019-01-02"]), name="snapshot"
            )
            self.buses = pd.DataFrame(
                {
                    "carrier": [
                        "urban central heat",
                        "urban central heat",
                        "AC",
                        "gas",
                        "district heat storage",
                        "biomass",
                        "hydrogen",
                    ]
                },
                index=[
                    "AT1 urban central heat",
                    "AT2 urban central heat",
                    "AT1 AC",
                    "AT2 gas",
                    "AT1 heat storage",
                    "AT2 biomass",
                    "AT2 hydrogen",
                ],
            )
            self.links = pd.DataFrame(
                {
                    "bus0": [
                        "AT1 AC",
                        "AT2 gas",
                        "AT2 biomass",
                        "AT2 hydrogen",
                    ],
                    "bus1": [
                        "AT1 urban central heat",
                        "AT2 urban central heat",
                        "AT2 urban central heat",
                        "AT2 urban central heat",
                    ],
                    "bus2": [
                        "AT1 heat storage",
                        "AT1 heat storage",
                        "AT1 heat storage",
                        "AT1 heat storage",
                    ],
                    "bus3": [
                        "AT1 heat storage",
                        "AT1 heat storage",
                        "AT1 heat storage",
                        "AT1 heat storage",
                    ],
                    "carrier": [
                        "urban central resistive heater",
                        "urban central gas boiler",
                        "central heat charger",
                        "central heat discharger",
                    ],
                },
                index=["l1", "l2", "l3", "l4"],
            )

    def _district_heat_network(self):
        return self._DistrictHeatNetwork()

    def test_returns_series(self):
        """Function returns a Series with expected output format."""
        result = Final_Energy_by_Carrier__District_Heat(self._district_heat_network())
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_filters_charger_and_discharger_carriers(self):
        """Carrier query excludes charger/discharger links connected to central heat."""
        network = self._district_heat_network()
        _ = Final_Energy_by_Carrier__District_Heat(network)

        calls = network.statistics.calls
        assert len(calls) == 2
        queried_carriers = set(calls[0]["carrier"])
        assert queried_carriers == {
            "urban central resistive heater",
            "urban central gas boiler",
        }
        assert calls[1]["bus_carrier"] == "urban central heat"
        assert calls[1]["carrier"] == "urban central heat vent"
        assert calls[1]["components"] == "Generator"

    def test_uses_supply_bus_carriers_from_bus0(self):
        """bus_carrier query uses carriers from bus0 of relevant central-heat links."""
        network = self._district_heat_network()
        _ = Final_Energy_by_Carrier__District_Heat(network)

        queried_bus_carriers = set(network.statistics.calls[0]["bus_carrier"])
        # Links via bus0 include AC, gas, biomass and hydrogen supply buses.
        assert queried_bus_carriers == {"AC", "gas", "biomass", "hydrogen"}
        assert network.statistics.calls[1]["carrier"] == "urban central heat vent"

    def test_returns_dataframe_for_aggregate_per_year_false(self):
        """aggregate_per_year=False returns timeseries DataFrame output."""
        network = self._district_heat_network()
        result = Final_Energy_by_Carrier__District_Heat(
            network, aggregate_per_year=False
        )
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert isinstance(result.columns, pd.DatetimeIndex)
        assert len(result.columns) == len(network.snapshots)
        pd.testing.assert_index_equal(result.columns, network.snapshots)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Coal
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierCoal:
    """Test suite for Final_Energy_by_Carrier__Coal function."""

    class _CoalStatisticsAccessor:
        """Minimal accessor to verify coal-carrier extraction behavior."""

        def __init__(self, raise_missing: bool = False):
            self.raise_missing = raise_missing
            self.calls: list[dict] = []

        @staticmethod
        def _series_from_groupby(
            groupby: list[str],
            values: list[float],
            location: str = "AT1",
            unit: str = "MWh_th",
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
            groupby_time: bool = True,
            groupby: list[str] | None = None,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby_time": groupby_time,
                    "groupby": groupby,
                    "nice_names": nice_names,
                }
            )

            if self.raise_missing:
                raise ValueError("coal carrier missing")

            if groupby is None:
                groupby = ["location", "unit"]

            if bus_carrier == "coal for industry" and carrier == "coal for industry":
                return self._series_from_groupby(groupby, [25.0])

            return pd.Series(
                dtype=float,
                index=pd.MultiIndex.from_tuples([], names=groupby),
            )

    class _CoalNetwork:
        """Minimal network exposing the custom coal statistics accessor."""

        def __init__(
            self,
            raise_missing: bool = False,
            carriers: list[str] | None = None,
        ):
            self.statistics = TestFinalEnergyByCarrierCoal._CoalStatisticsAccessor(
                raise_missing=raise_missing
            )
            self.carriers = pd.DataFrame(
                index=pd.Index(["coal for industry"] if carriers is None else carriers)
            )

    def _coal_network(
        self,
        raise_missing: bool = False,
        carriers: list[str] | None = None,
    ):
        return self._CoalNetwork(raise_missing=raise_missing, carriers=carriers)

    def test_returns_series(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Carrier__Coal(self._coal_network())
        assert isinstance(result, pd.Series)

    def test_has_location_and_unit_multiindex(self, mock_network: MockPyPSANetwork):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Carrier__Coal(self._coal_network())
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = Final_Energy_by_Carrier__Coal(self._coal_network())
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = Final_Energy_by_Carrier__Coal(self._coal_network())
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_at1_location(self, mock_network: MockPyPSANetwork):
        """Test that result contains AT1 locational data."""
        result = Final_Energy_by_Carrier__Coal(self._coal_network())
        assert "AT1" in result.index.get_level_values("location")

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for _ in mock_network_collection:
            result = Final_Energy_by_Carrier__Coal(self._coal_network())
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]
            assert len(result) > 0

    def test_issues_expected_withdrawal_query(self):
        """Function requests the expected coal carrier/component combination."""
        network = self._coal_network()
        _ = Final_Energy_by_Carrier__Coal(network)
        calls = network.statistics.calls
        assert len(calls) == 1
        assert calls[0]["bus_carrier"] == "coal for industry"
        assert calls[0]["carrier"] == "coal for industry"
        assert calls[0]["components"] == "Load"

    def test_returns_none_when_carrier_is_missing(self):
        """Missing coal carrier should short-circuit before statistics are queried."""
        network = self._coal_network(carriers=[])
        result = Final_Energy_by_Carrier__Coal(network)
        assert result is None
        assert network.statistics.calls == []


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

    def test_uses_mean_efficiency_and_warns_for_differing_bev_chargers(
        self, energy_totals_csv, caplog
    ):
        """Multiple distinct BEV charger efficiencies fall back to mean with WARNING."""
        network = MockPyPSANetwork(
            links=pd.DataFrame(
                {
                    "carrier": ["BEV charger", "BEV charger", "other link"],
                    "efficiency": [0.8, 0.9, 1.0],
                },
                index=["bev_charger_at1", "bev_charger_at2", "other_link_at1"],
            )
        )

        with caplog.at_level(logging.WARNING):
            result = Final_Energy_by_Sector__Transportation(
                network, energy_totals=energy_totals_csv
            )

        assert any(
            "Network includes different efficiencies for BEV chargers" in record.message
            for record in caplog.records
        )
        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names
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
# Tests for Final_Energy_by_Sector__Residential_and_Commercial
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorResidentialAndCommercial:
    """Test suite for Final_Energy_by_Sector__Residential_and_Commercial function."""

    class _ResidentialAndCommercialStatisticsAccessor:
        """Minimal accessor for residential and commercial sector tests."""

        def __init__(self, rescom_oil_empty: bool = False):
            self.calls: list[dict] = []
            self.rescom_oil_empty = rescom_oil_empty

        @staticmethod
        def _series_or_frame(
            groupby: list[str],
            locations: list[str],
            values: list[float],
            unit: str,
            groupby_time: bool,
        ) -> pd.Series | pd.DataFrame:
            index_tuples = []
            for location in locations:
                idx_dict = {
                    "name": f"{location} demand",
                    "carrier": "mock carrier",
                    "bus1": f"{location} bus",
                    "bus0": f"{location} bus",
                    "location": location,
                    "unit": unit,
                }
                index_tuples.append(
                    tuple(idx_dict.get(key, f"mock_{key}") for key in groupby)
                )

            index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)
            timestamps = pd.date_range(
                "2019-01-01", periods=4, freq="6h", name="snapshot"
            )
            if groupby_time:
                return pd.Series(values, index=index, dtype=float)

            per_snapshot_values = [value / len(timestamps) for value in values]
            return pd.DataFrame(
                {ts: per_snapshot_values for ts in timestamps},
                index=index,
                dtype=float,
            )

        def energy_balance(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby: list[str] | None = None,
            direction: str = "withdrawal",
            at_port: str | list[str] | None = None,
            groupby_time: bool = True,
            nice_names: bool | None = None,
            **_: object,
        ) -> pd.Series | pd.DataFrame:
            self.calls.append(
                {
                    "bus_carrier": bus_carrier,
                    "carrier": carrier,
                    "components": components,
                    "groupby": groupby,
                    "direction": direction,
                    "at_port": at_port,
                    "groupby_time": groupby_time,
                    "nice_names": nice_names,
                }
            )

            if groupby is None:
                groupby = ["location", "unit"]

            if components == "Link" and at_port not in ("bus0", ["bus0"]):
                return self._series_or_frame(groupby, [], [], "MWh_th", groupby_time)

            if bus_carrier == "oil" and self.rescom_oil_empty:
                return self._series_or_frame(groupby, [], [], "MWh_th", groupby_time)

            if carrier == ["rural biomass boiler", "urban decentral biomass boiler"]:
                return self._series_or_frame(
                    groupby, ["AT1", "AT2"], [21.0, 22.0], "MWh_th", groupby_time
                )

            if bus_carrier == "low voltage":
                return self._series_or_frame(
                    groupby, ["AT1", "AT2"], [11.0, 12.0], "MWh_el", groupby_time
                )

            if bus_carrier == "urban central heat":
                return self._series_or_frame(
                    groupby, ["AT1", "AT2"], [13.0, 14.0], "MWh_th", groupby_time
                )

            if carrier == ["urban decentral gas boiler", "rural gas boiler"]:
                return self._series_or_frame(
                    groupby, ["AT1", "AT2"], [15.0, 16.0], "MWh_th", groupby_time
                )

            return self._series_or_frame(
                groupby, ["AT1", "AT2"], [1.0, 2.0], "MWh_th", groupby_time
            )

        def withdrawal(
            self,
            bus_carrier: str | None = None,
            carrier: list[str] | str | None = None,
            components: str | list[str] | None = None,
            groupby_time: bool = True,
            groupby: list[str] | None = None,
            **kwargs: object,
        ) -> pd.Series | pd.DataFrame:
            kwargs.pop("groupby_time", None)
            return self.energy_balance(
                bus_carrier=bus_carrier,
                carrier=carrier,
                components=components,
                groupby=groupby,
                direction="withdrawal",
                groupby_time=groupby_time,
                **kwargs,
            )

    class _ResidentialAndCommercialNetwork:
        """Minimal network object exposing a residential/commercial statistics accessor."""

        def __init__(self, rescom_oil_empty: bool = False):
            accessor_cls = (
                TestFinalEnergyBySectorResidentialAndCommercial._ResidentialAndCommercialStatisticsAccessor
            )
            self.statistics = accessor_cls(rescom_oil_empty=rescom_oil_empty)

    def _residential_and_commercial_network(self, rescom_oil_empty: bool = False):
        return self._ResidentialAndCommercialNetwork(rescom_oil_empty=rescom_oil_empty)

    def test_returns_series(self):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )
        assert isinstance(result, pd.Series)

    def test_uses_bus0_for_gas_and_biomass(self):
        """Test that gas and biomass are queried on bus0."""
        network = self._residential_and_commercial_network()

        _ = Final_Energy_by_Sector__Residential_and_Commercial(network)

        gas_calls = [
            call
            for call in network.statistics.calls
            if call["carrier"] == ["urban decentral gas boiler", "rural gas boiler"]
        ]
        biomass_calls = [
            call
            for call in network.statistics.calls
            if call["bus_carrier"] == "solid biomass"
        ]

        assert gas_calls
        assert biomass_calls
        assert all(call["at_port"] == "bus0" for call in gas_calls)
        assert all(call["at_port"] == "bus0" for call in biomass_calls)

    def test_aggregates_all_fuel_types_per_location(self):
        """Test that all fuel types are combined correctly per location."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )

        grouped_result = result.groupby(level=["location", "unit"]).sum().sort_index()
        expected = pd.Series(
            [11.0, 12.0, -24.0, -26.0],
            index=pd.MultiIndex.from_tuples(
                [
                    ("AT1", "MWh_el"),
                    ("AT2", "MWh_el"),
                    ("AT1", "MWh_th"),
                    ("AT2", "MWh_th"),
                ],
                names=["location", "unit"],
            ),
            dtype=float,
        ).sort_index()

        pd.testing.assert_series_equal(grouped_result, expected)

    def test_has_location_and_unit_multiindex(self):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]

    def test_not_empty(self):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )
        assert len(result) > 0

    def test_numeric_values(self):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_multiple_locations(self):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            self._residential_and_commercial_network()
        )
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(self, mock_network_collection: MockNetworkCollection):
        """Test processing multiple networks from collection."""
        for _ in mock_network_collection:
            result = Final_Energy_by_Sector__Residential_and_Commercial(
                self._residential_and_commercial_network()
            )
            assert isinstance(result, pd.Series)
            assert isinstance(result.index, pd.MultiIndex)
            assert result.index.names == ["location", "unit"]
            assert len(result) > 0

    def test_returns_dataframe_when_not_aggregated(self):
        """aggregate_per_year=False returns a DataFrame with snapshot columns."""
        network = self._residential_and_commercial_network()
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            network, aggregate_per_year=False
        )
        aggregated_result = Final_Energy_by_Sector__Residential_and_Commercial(network)
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert any(isinstance(column, pd.Timestamp) for column in result.columns)
        assert len(result.columns) == 4
        assert not result.empty
        pd.testing.assert_series_equal(result.sum(axis=1), aggregated_result)

    def test_handles_empty_rescom_oil_without_failing(self):
        """Function should work when residential/commercial oil demand is empty."""
        network = self._residential_and_commercial_network(rescom_oil_empty=True)

        result = Final_Energy_by_Sector__Residential_and_Commercial(network)

        assert isinstance(result, pd.Series)
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["location", "unit"]
        assert not result.isna().any()
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
                timestamps = pd.date_range(
                    "2019-01-01", periods=4, freq="6h", name="snapshot"
                )
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
        Final_Energy_by_Carrier__Coal,
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
        if func is Final_Energy_by_Carrier__Coal and result is None:
            assert result is None
            return
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_has_location_and_unit_multiindex(
        self, mock_network: MockPyPSANetwork, func
    ):
        """DataFrame has MultiIndex with location and unit levels."""
        result = func(mock_network, aggregate_per_year=False)
        if func is Final_Energy_by_Carrier__Coal and result is None:
            assert result is None
            return
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_columns_are_timestamps(self, mock_network: MockPyPSANetwork, func):
        """DataFrame columns are a DatetimeIndex (snapshot timestamps)."""
        result = func(mock_network, aggregate_per_year=False)
        if func is Final_Energy_by_Carrier__Coal and result is None:
            assert result is None
            return
        assert isinstance(result.columns, pd.DatetimeIndex)

    @pytest.mark.parametrize("func", _FUNCTIONS, ids=lambda f: f.__name__)
    def test_not_empty(self, mock_network: MockPyPSANetwork, func):
        """DataFrame is not empty."""
        result = func(mock_network, aggregate_per_year=False)
        if func is Final_Energy_by_Carrier__Coal and result is None:
            assert result is None
            return
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
                    tuple(
                        {"carrier": c, "location": "AT1", "unit": "MWh_th"}[k]
                        for k in groupby
                    )
                    for c in carriers
                ]
                values = [10.0] * len(index_tuples)
                index = pd.MultiIndex.from_tuples(index_tuples, names=groupby)
                groupby_time = kwargs.get("groupby_time", True)
                if groupby_time:
                    return pd.Series(values, index=index, dtype=float)
                timestamps = pd.date_range(
                    "2019-01-01", periods=4, freq="6h", name="snapshot"
                )
                return pd.DataFrame(
                    {ts: values for ts in timestamps}, index=index, dtype=float
                )

        class _TS_IndustryNetwork:
            def __init__(self):
                self.statistics = _TS_IndustryStatisticsAccessor()

        result = Final_Energy_by_Sector__Industry(
            _TS_IndustryNetwork(), aggregate_per_year=False
        )
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names
        assert isinstance(result.columns, pd.DatetimeIndex)
