"""Tests for pypsa_validation_processing.statistics_functions."""

from __future__ import annotations

import logging

import pandas as pd
import pypsa
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
    Net_Imports__Oil,
)

from pypsa_validation_processing.utils import (
    COPPERPLATE_LOCATION,
    MissingInputError,
    UNITS_MAPPING,
    apply_coke_correction,
    remap_unit_index,
)

from conftest import MockPyPSANetwork, MockNetworkCollection

# ---------------------------------------------------------------------------
# Shared helpers for tests on real pypsa networks (WP4)
# ---------------------------------------------------------------------------

WEIGHT = 3.0


def _real_network(n_snapshots: int = 2) -> pypsa.Network:
    """Return an empty network with 3-hour snapshots weighted by ``WEIGHT``."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=n_snapshots, freq="3h"))
    n.snapshot_weightings.loc[:, :] = WEIGHT
    return n


def _add_bus(
    n: pypsa.Network, name: str, carrier: str, unit: str, location: str
) -> None:
    """Add a bus with carrier, unit and location."""
    n.add("Bus", name, carrier=carrier, unit=unit, location=location)


def _add_dispatched(
    n: pypsa.Network,
    component: str,
    name: str,
    dispatch: dict[str, list[float]],
    **attrs: object,
) -> None:
    """Add a component and set its dispatch time series (e.g. ``p``, ``p0``, ``p1``)."""
    n.add(component, name, **attrs)
    for attr, values in dispatch.items():
        n.components[component].dynamic[attr][name] = values


def _check_c6_format(
    result: pd.Series | pd.DataFrame, n: pypsa.Network, aggregate_per_year: bool
) -> None:
    """C6-AC1 / C6-AC2: type, index levels, units, locations, numeric values."""
    assert isinstance(result, pd.Series if aggregate_per_year else pd.DataFrame)
    assert isinstance(result.index, pd.MultiIndex)
    assert {"location", "unit"} <= set(result.index.names)
    assert len(result) > 0
    units = result.index.get_level_values("unit")
    assert all(u and u in UNITS_MAPPING for u in units)
    locations = set(result.index.get_level_values("location"))
    assert locations <= set(n.buses.location) and "" not in locations
    if aggregate_per_year:
        assert pd.api.types.is_numeric_dtype(result)
    else:
        assert set(result.columns) <= set(n.snapshots)
        assert all(pd.api.types.is_numeric_dtype(d) for d in result.dtypes)


def _check_flow_consistency(func, n: pypsa.Network, **kwargs: object) -> None:
    """C6-AC3 (flow): weighted column sum of the False result equals True."""
    yearly = func(n, aggregate_per_year=True, **kwargs)
    series = func(n, aggregate_per_year=False, **kwargs)
    weighted = series.mul(n.snapshot_weightings.objective, axis=1).sum(axis=1)
    # rows dropped by groupby_time=True are refilled with the normalised unit
    # (C6.13), while False keeps pypsa's label (C6.10); C8 normalises both
    pd.testing.assert_series_equal(
        remap_unit_index(weighted).sort_index(),
        remap_unit_index(yearly).sort_index(),
        check_names=False,
    )


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Electricity
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierElectricity:
    """Spec Final_Energy_by_Carrier__Electricity.md AC1-AC7."""

    @staticmethod
    def _base_network() -> pypsa.Network:
        """Two snapshots of weighting 1; buses at A, an empty location B."""
        n = _real_network()
        n.snapshot_weightings.loc[:, :] = 1.0
        _add_bus(n, "A", "AC", "MWh_el", "A")
        _add_bus(n, "B", "AC", "MWh_el", "B")
        _add_bus(n, "A low voltage", "low voltage", "MWh_el", "A")
        _add_bus(n, "A EV battery", "EV battery", "MWh_el", "A")
        return n

    @staticmethod
    def _link(n, name, carrier, bus0, bus1, p0, p1) -> None:
        _add_dispatched(
            n, "Link", name, {"p0": p0, "p1": p1}, bus0=bus0, bus1=bus1, carrier=carrier
        )

    def _ac3_network(self, v2g: bool = False) -> pypsa.Network:
        n = self._base_network()
        lv = "A low voltage"
        for bus, carrier in [
            ("A rural heat", "rural heat"),
            ("A home battery", "home battery"),
            ("A urban central heat", "urban central heat"),
        ]:
            _add_bus(n, bus, carrier, "MWh_th", "A")
        for name, p in [
            ("electricity", 10.0),
            ("industry electricity", 5.0),
            ("agriculture electricity", 1.0),
            ("agriculture machinery electric", 1.0),
        ]:
            _add_dispatched(n, "Load", f"A {name}", {"p": [p, p]}, bus=lv, carrier=name)
        self._link(
            n,
            "A BEV charger",
            "BEV charger",
            lv,
            "A EV battery",
            [2.0, 2.0],
            [-2.0, -2.0],
        )
        # heat pumps in PyPSA-AT: bus0 = heat bus, bus1 = low voltage
        self._link(
            n,
            "A rural air heat pump",
            "rural air heat pump",
            "A rural heat",
            lv,
            [-9.0, -9.0],
            [3.0, 3.0],
        )
        self._link(
            n, "A DAC", "DAC", "A", "A urban central heat", [1.0, 1.0], [0.0, 0.0]
        )
        self._link(
            n,
            "A distribution",
            "electricity distribution grid",
            lv,
            "A",
            [4.0, 4.0],
            [-4.0, -4.0],
        )
        self._link(
            n,
            "A home battery charger",
            "home battery charger",
            lv,
            "A home battery",
            [2.0, 2.0],
            [-2.0, -2.0],
        )
        self._link(
            n,
            "A urban central resistive heater",
            "urban central resistive heater",
            lv,
            "A urban central heat",
            [2.0, 2.0],
            [-2.0, -2.0],
        )
        if v2g:
            self._link(n, "A V2G", "V2G", "A EV battery", lv, [1.0, 1.0], [-1.0, -1.0])
        return n

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_zero_fill(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format; empty location B gets 0.0."""
        n = self._ac3_network()
        result = Final_Energy_by_Carrier__Electricity(
            n, aggregate_per_year=aggregate_per_year
        )
        _check_c6_format(result, n, aggregate_per_year)
        values = result.droplevel("unit")
        assert set(values.index) == {"A", "B"}
        assert (values.loc[["B"]] == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3 / AC5: 46 at A; grid, home battery, central heater excluded."""
        result = Final_Energy_by_Carrier__Electricity(self._ac3_network())
        assert result.droplevel("unit")["A"] == pytest.approx(46.0)
        assert (result >= 0).all()

    def test_ac3_with_v2g(self):
        """AC3: a V2G feed-in of 1 per snapshot is subtracted: 44."""
        result = Final_Energy_by_Carrier__Electricity(self._ac3_network(v2g=True))
        assert result.droplevel("unit")["A"] == pytest.approx(44.0)

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._ac3_network(v2g=True)
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(Final_Energy_by_Carrier__Electricity, n)

    def test_v2g_not_clipped(self):
        """AC7: BEV 4 / 0 and V2G 0 / 3 give snapshot values 4 / −3, yearly 1."""
        n = self._base_network()
        lv = "A low voltage"
        self._link(
            n,
            "A BEV charger",
            "BEV charger",
            lv,
            "A EV battery",
            [4.0, 0.0],
            [-4.0, 0.0],
        )
        self._link(n, "A V2G", "V2G", "A EV battery", lv, [0.0, 3.0], [0.0, -3.0])
        series = Final_Energy_by_Carrier__Electricity(n, aggregate_per_year=False)
        yearly = Final_Energy_by_Carrier__Electricity(n)
        assert series.droplevel("unit").loc["A"].tolist() == pytest.approx([4.0, -3.0])
        assert yearly.droplevel("unit")["A"] == pytest.approx(1.0)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_network_without_carriers(self, aggregate_per_year):
        """AC6: no low voltage bus and no DAC → 0.0 for every location."""
        n = _real_network()
        _add_bus(n, "A", "AC", "MWh_el", "A")
        _add_bus(n, "EU gas", "gas", "MWh_LHV", "EU")
        result = Final_Energy_by_Carrier__Electricity(
            n, aggregate_per_year=aggregate_per_year
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert set(result.index.get_level_values("location")) == {"A", "EU"}
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Net_Imports__Electricity
# ---------------------------------------------------------------------------


class TestNetImportsElectricity:
    """Test suite for Net_Imports__Electricity (spec AC1-AC7, C6-AC1/2/3/6)."""

    WEIGHT = 3.0

    @classmethod
    def _network(cls, locations: tuple[str, ...] = ("A", "B", "C")) -> pypsa.Network:
        """Return a network with two 3-hour snapshots and one AC bus per location."""
        n = pypsa.Network()
        n.set_snapshots(pd.date_range("2025-01-01", periods=2, freq="3h"))
        n.snapshot_weightings.loc[:, :] = cls.WEIGHT
        for location in locations:
            n.add("Bus", location, carrier="AC", unit="MWh_el", location=location)
        return n

    @staticmethod
    def _add_branch(
        n: pypsa.Network,
        component: str,
        name: str,
        p0: list[float],
        efficiency: float = 1.0,
        **attrs: object,
    ) -> None:
        """Add a Line or Link with dispatch *p0* and ``p1 = -efficiency * p0``."""
        if component == "Link":
            attrs["efficiency"] = efficiency
        n.add(component, name, **attrs)
        dispatch = n.lines_t if component == "Line" else n.links_t
        dispatch.p0[name] = p0
        dispatch.p1[name] = [-efficiency * v for v in p0]

    def _ac3_network(self) -> pypsa.Network:
        """Line A→B with p0 = 10, DC link C→A with p0 = 5 and efficiency 0.9."""
        n = self._network()
        self._add_branch(
            n, "Line", "A-B", [10.0, 0.0], bus0="A", bus1="B", carrier="AC", x=0.1
        )
        self._add_branch(
            n,
            "Link",
            "C-A",
            [5.0, 0.0],
            efficiency=0.9,
            bus0="C",
            bus1="A",
            carrier="DC",
        )
        return n

    @staticmethod
    def _check_format(result: pd.Series | pd.DataFrame, n: pypsa.Network) -> None:
        """C6-AC1 / C6-AC2 checks shared by both modes."""
        assert isinstance(result.index, pd.MultiIndex)
        assert {"location", "unit"} <= set(result.index.names)
        assert len(result) > 0
        units = result.index.get_level_values("unit")
        assert all(u and u in UNITS_MAPPING for u in units)
        locations = result.index.get_level_values("location")
        assert set(locations) <= set(n.buses.location) and "" not in set(locations)

    def test_ac3_yearly_values(self):
        """AC3: A = −10 + 4.5, B = 10, C = −5 per snapshot, weighted per C6.10."""
        n = self._ac3_network()
        result = Net_Imports__Electricity(n)

        assert isinstance(result, pd.Series)
        self._check_format(result, n)
        values = result.droplevel("unit")
        assert values["A"] == pytest.approx(-5.5 * self.WEIGHT)
        assert values["B"] == pytest.approx(10.0 * self.WEIGHT)
        assert values["C"] == pytest.approx(-5.0 * self.WEIGHT)
        assert set(result.index.get_level_values("unit")) == {"MWh_el"}

    def test_ac3_timeseries(self):
        """AC2/AC3: aggregate_per_year=False gives unweighted snapshot values."""
        n = self._ac3_network()
        result = Net_Imports__Electricity(n, aggregate_per_year=False)

        assert isinstance(result, pd.DataFrame)
        self._check_format(result, n)
        assert set(result.columns) <= set(n.snapshots)
        assert all(pd.api.types.is_numeric_dtype(d) for d in result.dtypes)
        first = result.droplevel("unit")[n.snapshots[0]]
        assert first["A"] == pytest.approx(-5.5)
        assert first["B"] == pytest.approx(10.0)
        assert first["C"] == pytest.approx(-5.0)

    def test_flow_consistency(self):
        """AC4 / C6-AC3: weighted column sum of the False result equals True."""
        n = self._ac3_network()
        yearly = Net_Imports__Electricity(n)
        series = Net_Imports__Electricity(n, aggregate_per_year=False)

        weighted = series.mul(n.snapshot_weightings.objective, axis=1).sum(axis=1)
        pd.testing.assert_series_equal(
            weighted.sort_index(), yearly.sort_index(), check_names=False
        )

    def test_sum_over_locations_is_minus_losses(self):
        """AC5: the sum over all locations equals −(link losses)."""
        n = self._ac3_network()
        result = Net_Imports__Electricity(n)
        assert result.sum() == pytest.approx(-0.5 * self.WEIGHT)

    def test_lossless_line_is_antisymmetric(self):
        """Edge case: NI(A) = −NI(B) for a lossless line A–B."""
        n = self._network(("A", "B"))
        self._add_branch(
            n, "Line", "A-B", [4.0, -2.0], bus0="A", bus1="B", carrier="AC", x=0.1
        )
        values = Net_Imports__Electricity(n).droplevel("unit")
        assert values["A"] == pytest.approx(-values["B"])
        assert values["B"] == pytest.approx(2.0 * self.WEIGHT)

    def test_distribution_grid_link_is_ignored(self):
        """AC7: an `electricity distribution grid` link does not change the result."""
        n = self._ac3_network()
        expected = Net_Imports__Electricity(n)
        n.add("Bus", "B low voltage", carrier="low voltage", location="B")
        self._add_branch(
            n,
            "Link",
            "B distribution",
            [7.0, 7.0],
            bus0="B",
            bus1="B low voltage",
            carrier="electricity distribution grid",
        )
        pd.testing.assert_series_equal(Net_Imports__Electricity(n), expected)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_location_without_branches_is_zero(self, aggregate_per_year):
        """C6-AC6: a location without branches is present with 0.0."""
        n = self._ac3_network()
        n.add("Bus", "D", carrier="AC", unit="MWh_el", location="D")
        result = Net_Imports__Electricity(n, aggregate_per_year=aggregate_per_year)

        self._check_format(result, n)
        assert set(result.index.get_level_values("location")) == {"A", "B", "C", "D"}
        assert (result.xs("D", level="location") == 0.0).all(axis=None)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_network_without_branches(self, aggregate_per_year):
        """C6-AC6 / C6.13: no Lines and no DC links → 0.0 for every location."""
        n = self._network()
        result = Net_Imports__Electricity(n, aggregate_per_year=aggregate_per_year)

        expected_type = pd.Series if aggregate_per_year else pd.DataFrame
        assert isinstance(result, expected_type)
        self._check_format(result, n)
        assert set(result.index.get_level_values("location")) == {"A", "B", "C"}
        assert (result == 0.0).all(axis=None)
        if not aggregate_per_year:
            assert list(result.columns) == list(n.snapshots)


# ---------------------------------------------------------------------------
# Tests for Net_Imports__Oil
# ---------------------------------------------------------------------------


class TestNetImportsOil:
    """Spec Net_Imports__Oil.md AC1-AC7."""

    @staticmethod
    def _network(
        boiler: float = 40.0, store: float = 0.0, n_snapshots: int = 1
    ) -> pypsa.Network:
        """AC3 mock: EU oil copperplate, refining 80 at EU, Fischer-Tropsch 20 at A."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots
        _add_bus(n, "EU oil", "oil", "MWh_th", COPPERPLATE_LOCATION)
        _add_bus(n, "EU oil primary", "oil primary", "MWh_th", COPPERPLATE_LOCATION)
        for loc in ("A", "B", "C"):
            _add_bus(n, loc, "AC", "MWh_el", loc)
        _add_bus(n, "A land transport oil", "land transport oil", "MWh_th", "A")
        _add_bus(n, "B rural heat", "rural heat", "MWh_th", "B")

        def link(name, carrier, bus0, bus1, p0, p1):
            _add_dispatched(
                n,
                "Link",
                name,
                {"p0": [p0 * v for v in ones], "p1": [p1 * v for v in ones]},
                bus0=bus0,
                bus1=bus1,
                carrier=carrier,
            )

        link("EU oil refining", "oil refining", "EU oil primary", "EU oil", 80.0, -80.0)
        link("A Fischer-Tropsch", "Fischer-Tropsch", "A", "EU oil", 30.0, -20.0)
        link(
            "A land transport oil",
            "land transport oil",
            "EU oil",
            "A land transport oil",
            60.0,
            -60.0,
        )
        link(
            "B rural oil boiler",
            "rural oil boiler",
            "EU oil",
            "B rural heat",
            boiler,
            -0.9 * boiler,
        )
        if store:
            # Store p > 0 discharges to the bus; charging is negative p
            _add_dispatched(
                n,
                "Store",
                "EU oil Store",
                {"p": [-store * v for v in ones]},
                bus="EU oil",
                carrier="oil",
            )
        return n

    @staticmethod
    def _values(n: pypsa.Network, **kwargs: object) -> pd.Series:
        return Net_Imports__Oil(n, **kwargs).droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format; C without oil consumers gets 0.0."""
        n = self._network()
        result = Net_Imports__Oil(n, aggregate_per_year=aggregate_per_year)
        _check_c6_format(result, n, aggregate_per_year)
        values = result.droplevel("unit")
        assert set(values.index) == {"A", "B", "C", COPPERPLATE_LOCATION}
        assert (values.loc[["C"]] == 0.0).all(axis=None)

    def test_ac3_values(self):
        """AC3: f_oil = 0.8; A 48, B 32, EU −80, consumers attributed per D1."""
        values = self._values(self._network())
        assert values["A"] == pytest.approx(48.0)
        assert values["B"] == pytest.approx(32.0)
        assert values[COPPERPLATE_LOCATION] == pytest.approx(-80.0)

    def test_ac7_store_charging(self):
        """AC5 / AC7: Store charging 10 at EU: A 48, B 24, EU −72; sum 0."""
        values = self._values(self._network(boiler=30.0, store=10.0))
        assert values["A"] == pytest.approx(48.0)
        assert values["B"] == pytest.approx(24.0)
        assert values[COPPERPLATE_LOCATION] == pytest.approx(-72.0)
        assert values.sum() == pytest.approx(0.0)

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._network(boiler=30.0, store=10.0, n_snapshots=2)
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(Net_Imports__Oil, n)

    def test_no_fossil_supply(self):
        """Edge case: f_oil = 0 gives 0.0 for every regional location."""
        n = self._network()
        n.links_t.p0["EU oil refining"] = [0.0]
        n.links_t.p1["EU oil refining"] = [0.0]
        values = self._values(n)
        assert (values.loc[["A", "B", "C"]] == 0.0).all()

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_oil_bus(self, aggregate_per_year):
        """Edge case / AC6: no oil bus gives 0.0 for every location."""
        n = _real_network()
        _add_bus(n, "A", "AC", "MWh_el", "A")
        result = Net_Imports__Oil(n, aggregate_per_year=aggregate_per_year)
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


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
    """Spec Final_Energy_by_Carrier__District_Heat.md AC1-AC10."""

    CONFIG = {"sector": {"district_heating": {"district_heating_loss": 0.15}}}

    @staticmethod
    def _ac3_network(n_snapshots: int = 1) -> pypsa.Network:
        """AC3 mock at location A (plus empty location B, copperplate EU)."""
        n = _real_network(n_snapshots)
        ones = [1.0] * n_snapshots
        for loc in ("A", "B"):
            _add_bus(n, loc, "AC", "MWh_el", loc)
        _add_bus(n, "A urban central heat", "urban central heat", "MWh_th", "A")
        _add_bus(n, "A urban decentral heat", "urban decentral heat", "MWh_th", "A")
        _add_bus(n, "A water pits", "urban central water pits", "MWh_th", "A")
        _add_bus(
            n,
            f"{COPPERPLATE_LOCATION} coal",
            "coal",
            "MWh_LHV",
            COPPERPLATE_LOCATION,
        )
        heat = "A urban central heat"
        _add_dispatched(
            n,
            "Load",
            "A uc heat",
            {"p": [115.0 * v for v in ones]},
            bus=heat,
            carrier="urban central heat",
        )
        _add_dispatched(
            n,
            "Load",
            "A lt ind",
            {"p": [10.0 * v for v in ones]},
            bus=heat,
            carrier="low-temperature heat for industry",
        )
        _add_dispatched(
            n,
            "Load",
            "A lt ind dec",
            {"p": [7.0 * v for v in ones]},
            bus="A urban decentral heat",
            carrier="low-temperature heat for industry",
        )
        _add_dispatched(
            n,
            "Link",
            "A DAC",
            {"p0": [2.0 * v for v in ones], "p1": [5.0 * v for v in ones]},
            bus0="A",
            bus1=heat,
            carrier="DAC",
            efficiency=-2.5,
        )
        _add_dispatched(
            n,
            "Link",
            "A pits charger",
            {"p0": [20.0 * v for v in ones], "p1": [-20.0 * v for v in ones]},
            bus0=heat,
            bus1="A water pits",
            carrier="urban central water pits charger",
        )
        _add_dispatched(
            n,
            "Generator",
            "A vent",
            {"p": [-3.0 * v for v in ones]},
            bus=heat,
            carrier="urban central heat vent",
            p_min_pu=-1,
            p_max_pu=0,
        )
        _add_dispatched(
            n,
            "Link",
            "A urban central coal CHP",
            {
                "p0": [300.0 * v for v in ones],
                "p1": [-100.0 * v for v in ones],
                "p2": [-150.0 * v for v in ones],
            },
            bus0="EU coal",
            bus1="A",
            bus2=heat,
            carrier="urban central coal CHP",
            efficiency=0.33,
            efficiency2=0.5,
        )
        return n

    def _values(self, n: pypsa.Network, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Carrier__District_Heat(n, config=self.CONFIG, **kwargs)
        return result.droplevel("unit")

    def test_ac3_value(self):
        """AC3: 115/1.15 + 10 + 5 = 115 at A; decentral, charger, vent excluded."""
        n = self._ac3_network()
        result = Final_Energy_by_Carrier__District_Heat(n, config=self.CONFIG)
        _check_c6_format(result, n, aggregate_per_year=True)
        assert self._values(n)["A"] == pytest.approx(115.0 * WEIGHT)

    def test_timeseries_format_and_flow_consistency(self):
        """AC2 / AC4: DataFrame per snapshot, weighted sum equals yearly value."""
        n = self._ac3_network(n_snapshots=2)
        result = Final_Energy_by_Carrier__District_Heat(
            n, aggregate_per_year=False, config=self.CONFIG
        )
        _check_c6_format(result, n, aggregate_per_year=False)
        assert result.droplevel("unit").loc["A"].tolist() == pytest.approx(
            [115.0, 115.0]
        )
        _check_flow_consistency(
            Final_Energy_by_Carrier__District_Heat, n, config=self.CONFIG
        )

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_every_location_non_negative(self, aggregate_per_year):
        """AC5 / AC6 / AC10: B and copperplate present with 0.0, values >= 0."""
        n = self._ac3_network()
        values = self._values(n, aggregate_per_year=aggregate_per_year)
        assert set(values.index) == {"A", "B", COPPERPLATE_LOCATION}
        assert (values.loc[["B", COPPERPLATE_LOCATION]] == 0.0).all(axis=None)
        assert (values >= 0).all(axis=None)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_copperplate_location_is_zero(self, aggregate_per_year):
        """AC10: fuel withdrawn at copperplate EU by a heat-supplying CHP is not
        counted; the copperplate location has no district heat."""
        n = self._ac3_network(n_snapshots=2)
        assert (n.links_t.p0["A urban central coal CHP"] != 0).all()
        assert n.buses.loc["EU coal", "location"] == COPPERPLATE_LOCATION
        values = self._values(n, aggregate_per_year=aggregate_per_year)
        assert COPPERPLATE_LOCATION in values.index
        assert (values.loc[[COPPERPLATE_LOCATION]] == 0.0).all(axis=None)

    def test_independent_of_supply_efficiency(self):
        """AC7: changing the CHP efficiency leaves the result unchanged."""
        n = self._ac3_network()
        expected = self._values(n)
        n.links.loc["A urban central coal CHP", "efficiency2"] = 0.9
        pd.testing.assert_series_equal(self._values(n), expected)

    def test_unknown_withdrawing_carrier_raises(self):
        """AC8: an unknown carrier withdrawing from urban central heat raises."""
        n = self._ac3_network()
        _add_dispatched(
            n,
            "Load",
            "A mystery",
            {"p": [1.0]},
            bus="A urban central heat",
            carrier="mystery heat",
        )
        with pytest.raises(ValueError, match="mystery heat"):
            Final_Energy_by_Carrier__District_Heat(n, config=self.CONFIG)

    @pytest.mark.parametrize(
        "efficiency, p1",
        [(2.5, [-5.0]), (-2.5, [-5.0])],
        ids=["positive efficiency", "negative withdrawal"],
    )
    def test_dac_supplying_heat_raises(self, efficiency, p1):
        """AC9: a DAC link that supplies heat to urban central heat raises."""
        n = self._ac3_network()
        n.links.loc["A DAC", "efficiency"] = efficiency
        n.links_t.p1["A DAC"] = p1
        with pytest.raises(ValueError, match="A DAC"):
            Final_Energy_by_Carrier__District_Heat(n, config=self.CONFIG)

    @pytest.mark.parametrize("config", [None, {}, {"sector": {"district_heating": {}}}])
    def test_missing_loss_raises_missing_input(self, config):
        """Section 8: missing district_heating_loss raises MissingInputError."""
        with pytest.raises(MissingInputError, match="district_heating_loss"):
            Final_Energy_by_Carrier__District_Heat(self._ac3_network(), config=config)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_district_heating(self, aggregate_per_year):
        """Edge case: no urban central heat bus gives 0.0 for every location."""
        n = _real_network()
        for loc in ("A", "B"):
            _add_bus(n, loc, "AC", "MWh_el", loc)
        result = Final_Energy_by_Carrier__District_Heat(
            n, aggregate_per_year=aggregate_per_year, config=self.CONFIG
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Coal
# ---------------------------------------------------------------------------


def _shares(**values: float) -> pd.DataFrame:
    """Non-energy shares table (C2.5) for ``carrier=value`` pairs of country ``AA``.

    Every carrier of ``{Natural Gas, Oil, Coal}`` is present (as after the
    initialisation checks); unspecified carriers get share ``0.0``.
    """
    carriers = {"Natural Gas": 0.0, "Oil": 0.0, "Coal": 0.0}
    carriers.update({k.replace("_", " "): v for k, v in values.items()})
    index = pd.MultiIndex.from_tuples(
        [("AA", c) for c in carriers], names=["country", "carrier"]
    )
    return pd.DataFrame({"non_energy_share": list(carriers.values())}, index=index)


class TestFinalEnergyByCarrierCoal:
    """Spec Final_Energy_by_Carrier__Coal.md AC1-AC6."""

    @staticmethod
    def _network(with_coal: bool = True) -> pypsa.Network:
        """Coal for industry Load of 10 MW at AA1 over 2 snapshots (weighting 1)."""
        n = _real_network()
        n.snapshot_weightings.loc[:, :] = 1.0
        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        _add_bus(n, "AA2", "AC", "MWh_el", "AA2")
        _add_bus(
            n,
            f"{COPPERPLATE_LOCATION} coal",
            "coal",
            "MWh_LHV",
            COPPERPLATE_LOCATION,
        )
        if with_coal:
            _add_bus(n, "AA1 coal for industry", "coal for industry", "MWh_LHV", "AA1")
            _add_bus(n, "AA2 coal for industry", "coal for industry", "MWh_LHV", "AA2")
            _add_dispatched(
                n,
                "Load",
                "AA1 coal for industry",
                {"p": [10.0, 10.0]},
                bus="AA1 coal for industry",
                carrier="coal for industry",
            )
            _add_dispatched(
                n,
                "Load",
                "AA2 coal for industry",
                {"p": [0.0, 0.0]},
                bus="AA2 coal for industry",
                carrier="coal for industry",
            )
        return n

    @staticmethod
    def _values(n: pypsa.Network, shares: pd.DataFrame, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Carrier__Coal(
            n, industry_non_energy_shares=shares, **kwargs
        )
        return result.droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format; AA2 (zero withdrawal) and copperplate kept with 0.0."""
        n = self._network()
        result = Final_Energy_by_Carrier__Coal(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        values = result.droplevel("unit")
        assert set(values.index) == {"AA1", "AA2", COPPERPLATE_LOCATION}
        assert (values.loc[["AA2", COPPERPLATE_LOCATION]] == 0.0).all(axis=None)

    def test_ac3_without_non_energy_use(self):
        """AC3: kappa = 0 and share 0 gives 20."""
        assert self._values(self._network(), _shares())["AA1"] == pytest.approx(20.0)

    def test_ac3a_non_energy_use_subtracted(self):
        """AC3a / AC5: share 0.25 gives NE = 5 and 15; values >= 0."""
        values = self._values(self._network(), _shares(Coal=0.25))
        assert values["AA1"] == pytest.approx(15.0)
        assert (values >= 0).all()

    @pytest.mark.parametrize(
        "non_energy_share, expected", [(0.0, 17.321), (0.25, 12.990)]
    )
    def test_ac3_coke_correction_injected(
        self, monkeypatch, non_energy_share, expected
    ):
        """AC3 / AC3a: an injected kappa = 0.5 applies the coke factor 1.366."""
        import pypsa_validation_processing.statistics_functions as sf

        monkeypatch.setattr(
            sf,
            "apply_coke_correction",
            lambda energy: apply_coke_correction(energy, kappa=0.5),
        )
        values = self._values(self._network(), _shares(Coal=non_energy_share))
        assert values["AA1"] == pytest.approx(expected, abs=1e-3)

    def test_ac3b_fallback_warns(self, caplog):
        """AC3b: the Eurostat fallback logs one WARNING about the coke correction."""
        with caplog.at_level(logging.WARNING):
            self._values(self._network(), _shares())
        coke = [r for r in caplog.records if "Coke correction" in r.getMessage()]
        assert len(coke) == 1

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._network()
        n.loads_t.p["AA1 coal for industry"] = [10.0, 4.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Carrier__Coal,
            n,
            industry_non_energy_shares=_shares(Coal=0.25),
        )

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_coal_for_industry(self, aggregate_per_year):
        """AC6 / C6.9: without the carrier, 0.0 for every location, never None."""
        n = self._network(with_coal=False)
        result = Final_Energy_by_Carrier__Coal(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Transportation
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorTransportation:
    """Test suite for Final_Energy_by_Sector__Transportation function."""

    def test_returns_series(self, mock_network: MockPyPSANetwork, energy_totals_df):
        """Test that the function returns a pandas Series."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_df
        )
        assert isinstance(result, pd.Series)

    def test_has_location_and_unit_multiindex(
        self, mock_network: MockPyPSANetwork, energy_totals_df
    ):
        """Test that result has MultiIndex with location and unit levels."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_df
        )
        assert isinstance(result.index, pd.MultiIndex)
        assert "location" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork, energy_totals_df):
        """Test that result is not empty."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_df
        )
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork, energy_totals_df):
        """Test that result values are numeric."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_df
        )
        assert result.dtype in [float, int] or pd.api.types.is_numeric_dtype(
            result.dtype
        )

    def test_contains_multiple_locations(
        self, mock_network: MockPyPSANetwork, energy_totals_df
    ):
        """Test that result contains multiple locational data."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network, energy_totals=energy_totals_df
        )
        locations = result.index.get_level_values("location").unique()
        assert len(locations) > 1
        assert all(r.startswith("AT") for r in locations)

    def test_multiple_networks(
        self, mock_network_collection: MockNetworkCollection, energy_totals_df
    ):
        """Test processing multiple networks from collection."""
        for network in mock_network_collection:
            result = Final_Energy_by_Sector__Transportation(
                network, energy_totals=energy_totals_df
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
        self, energy_totals_df, caplog
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
                network, energy_totals=energy_totals_df
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
        self, mock_network: MockPyPSANetwork, energy_totals_df
    ):
        """Transportation returns a DataFrame when aggregate_per_year=False."""
        result = Final_Energy_by_Sector__Transportation(
            mock_network,
            aggregate_per_year=False,
            energy_totals=energy_totals_df,
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
