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
        assert list(result.columns) == list(n.snapshots)
        assert all(pd.api.types.is_numeric_dtype(d) for d in result.dtypes)


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
    """Spec Final_Energy_by_Carrier__Oil.md AC1-AC9."""

    # d_aviation(AA) = 0.5, d_navigation(AA) = 0.2; BB: d_aviation = 0.25
    ENERGY_TOTALS = pd.DataFrame(
        {
            "total domestic aviation": [50.0, 25.0],
            "total international aviation": [50.0, 75.0],
            "total domestic navigation": [20.0, 20.0],
            "total international navigation": [80.0, 80.0],
        },
        index=pd.Index(["AA", "BB"], name="country"),
    )

    @staticmethod
    def _network(
        methanol_kerosene: bool = False, n_snapshots: int = 1
    ) -> pypsa.Network:
        """AC3 mock: f_oil = 0.75; loads at AA1; AA2 empty."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots

        def dispatch(component, name, values, **attrs):
            series = {k: [v * o for o in ones] for k, v in values.items()}
            _add_dispatched(n, component, name, series, **attrs)

        _add_bus(n, "EU oil", "oil", "MWh_th", "EU")
        _add_bus(n, "EU oil primary", "oil primary", "MWh_th", "EU")
        _add_bus(n, "EU methanol", "methanol", "MWh_LHV", "EU")
        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        _add_bus(n, "AA2", "AC", "MWh_el", "AA2")
        dispatch(
            "Link",
            "EU oil refining",
            {"p0": 75.0, "p1": -75.0},
            bus0="EU oil primary",
            bus1="EU oil",
            carrier="oil refining",
        )
        dispatch(
            "Link",
            "AA1 Fischer-Tropsch",
            {"p0": 30.0, "p1": -25.0},
            bus0="AA1",
            bus1="EU oil",
            carrier="Fischer-Tropsch",
        )
        for carrier, unit, p in [
            ("land transport oil", "land transport", 40.0),
            ("kerosene for aviation", "MWh_LHV", 20.0),
            ("agriculture machinery oil", "MWh_LHV", 4.0),
        ]:
            _add_bus(n, f"AA1 {carrier}", carrier, unit, "AA1")
            dispatch(
                "Load",
                f"AA1 {carrier}",
                {"p": p},
                bus=f"AA1 {carrier}",
                carrier=carrier,
            )
        ker = "AA1 kerosene for aviation"
        oil_ker = 15.0 if methanol_kerosene else 20.0
        dispatch(
            "Link",
            "AA1 kerosene supply",
            {"p0": oil_ker, "p1": -oil_ker},
            bus0="EU oil",
            bus1=ker,
            carrier="kerosene for aviation",
        )
        if methanol_kerosene:
            dispatch(
                "Link",
                "AA1 methanol-to-kerosene",
                {"p0": 5.0, "p1": -5.0},
                bus0="EU methanol",
                bus1=ker,
                carrier="methanol-to-kerosene",
            )
        return n

    def _normalised(
        self, n: pypsa.Network, shares: pd.DataFrame | None = None, **kwargs: object
    ) -> pd.Series:
        result = Final_Energy_by_Carrier__Oil(
            n,
            energy_totals=self.ENERGY_TOTALS,
            industry_non_energy_shares=_shares() if shares is None else shares,
            **kwargs,
        )
        return remap_unit_index(result).groupby("location").sum()

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC5 / AC6: C6 format incl. `land transport`; AA2 and EU are 0.0."""
        n = self._network()
        result = Final_Energy_by_Carrier__Oil(
            n,
            aggregate_per_year=aggregate_per_year,
            energy_totals=self.ENERGY_TOTALS,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert "land transport" in set(result.index.get_level_values("unit"))
        for loc in ("AA2", "EU"):
            assert (result.xs(loc, level="location") == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3: 0.75 · (40 + 0.5·20 + 4) = 40.5."""
        values = self._normalised(self._network())
        assert values["AA1"] == pytest.approx(40.5)
        assert (values >= 0).all()

    def test_ac3b_oil_based_kerosene_share(self):
        """AC3b: s_ker = 0.75 gives 0.75 · (40 + 0.5·0.75·20 + 4) = 38.625."""
        assert self._normalised(self._network(methanol_kerosene=True))[
            "AA1"
        ] == pytest.approx(38.625)

    def test_unknown_kerosene_supplier_raises(self):
        """Section 7: an unknown carrier supplying kerosene raises ValueError."""
        n = self._network()
        _add_dispatched(
            n,
            "Link",
            "AA1 mystery kerosene",
            {"p0": [1.0], "p1": [-1.0]},
            bus0="AA1",
            bus1="AA1 kerosene for aviation",
            carrier="mystery kerosene",
        )
        with pytest.raises(ValueError, match="mystery kerosene"):
            self._normalised(n)

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._network(n_snapshots=2)
        n.loads_t.p["AA1 land transport oil"] = [40.0, 10.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Carrier__Oil,
            n,
            energy_totals=self.ENERGY_TOTALS,
            industry_non_energy_shares=_shares(),
        )

    def test_ac7_domestic_share_per_country(self):
        """AC7: kerosene at BB1 uses d_aviation(BB) = 0.25, AA1 uses 0.5."""
        n = self._network()
        _add_bus(
            n, "BB1 kerosene for aviation", "kerosene for aviation", "MWh_LHV", "BB1"
        )
        _add_dispatched(
            n,
            "Load",
            "BB1 kerosene for aviation",
            {"p": [20.0]},
            bus="BB1 kerosene for aviation",
            carrier="kerosene for aviation",
        )
        _add_dispatched(
            n,
            "Link",
            "BB1 kerosene supply",
            {"p0": [20.0], "p1": [-20.0]},
            bus0="EU oil",
            bus1="BB1 kerosene for aviation",
            carrier="kerosene for aviation",
        )
        values = self._normalised(n)
        assert values["BB1"] == pytest.approx(0.75 * 0.25 * 20.0)
        assert values["AA1"] == pytest.approx(40.5)

    def test_ac9_naphtha_non_energy_use(self):
        """AC9: naphtha 10 with S = 0.8 gives 0.75 · (40 + 10 + 4 + 10 − 8) = 42."""
        n = self._network()
        _add_bus(
            n, "AA1 naphtha for industry", "naphtha for industry", "MWh_LHV", "AA1"
        )
        _add_dispatched(
            n,
            "Load",
            "AA1 naphtha for industry",
            {"p": [10.0]},
            bus="AA1 naphtha for industry",
            carrier="naphtha for industry",
        )
        assert self._normalised(n, _shares(Oil=0.8))["AA1"] == pytest.approx(42.0)

    def test_decentral_boiler_located_per_d1(self):
        """Section 6: a rural oil boiler from EU oil counts at its heat bus location."""
        n = self._network()
        _add_bus(n, "AA2 rural heat", "rural heat", "MWh_th", "AA2")
        _add_dispatched(
            n,
            "Link",
            "AA2 rural oil boiler",
            {"p0": [8.0], "p1": [-7.2]},
            bus0="EU oil",
            bus1="AA2 rural heat",
            carrier="rural oil boiler",
        )
        values = self._normalised(n)
        assert values["AA2"] == pytest.approx(0.75 * 8.0)
        assert values["EU"] == 0.0

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_oil(self, aggregate_per_year):
        """AC6: a network without oil carriers gives 0.0 everywhere."""
        n = _real_network()
        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        result = Final_Energy_by_Carrier__Oil(
            n,
            aggregate_per_year=aggregate_per_year,
            energy_totals=self.ENERGY_TOTALS,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Natural_Gas
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierNaturalGas:
    """Spec Final_Energy_by_Carrier__Natural_Gas.md AC1-AC10."""

    @staticmethod
    def _network(
        renewable: str = "biogas to gas", n_snapshots: int = 1
    ) -> pypsa.Network:
        """AC3 mock: production gas 60, renewable 40 (f_gas = 0.6) at AA1."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots
        for loc in ("AA1", "AA2"):
            _add_bus(n, f"{loc} gas", "gas", "MWh_LHV", loc)
        _add_bus(n, "AA1 biogas", "biogas", "MWh_LHV", "AA1")
        _add_bus(n, "AA1 rural heat", "rural heat", "MWh_th", "AA1")
        _add_bus(n, "AA1 gas for industry", "gas for industry", "MWh_LHV", "AA1")
        _add_bus(n, "EU co2 atmosphere", "co2", "t_co2", "EU")
        _add_dispatched(
            n,
            "Generator",
            "AA1 production gas",
            {"p": [60.0 * v for v in ones]},
            bus="AA1 gas",
            carrier="production gas",
        )
        bus0 = "EU co2 atmosphere" if renewable == "import gas" else "AA1 biogas"
        _add_dispatched(
            n,
            "Link",
            f"AA1 {renewable}",
            {"p0": [40.0 * v for v in ones], "p1": [-40.0 * v for v in ones]},
            bus0=bus0,
            bus1="AA1 gas",
            carrier=renewable,
        )
        _add_dispatched(
            n,
            "Link",
            "AA1 rural gas boiler",
            {"p0": [10.0 * v for v in ones], "p1": [-9.0 * v for v in ones]},
            bus0="AA1 gas",
            bus1="AA1 rural heat",
            carrier="rural gas boiler",
        )
        _add_dispatched(
            n,
            "Load",
            "AA1 gas for industry",
            {"p": [20.0 * v for v in ones]},
            bus="AA1 gas for industry",
            carrier="gas for industry",
        )
        return n

    @staticmethod
    def _values(n: pypsa.Network, shares: pd.DataFrame, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Carrier__Natural_Gas(
            n, industry_non_energy_shares=shares, **kwargs
        )
        return result.droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format; AA2 and EU present with 0.0."""
        n = self._network()
        result = Final_Energy_by_Carrier__Natural_Gas(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        values = result.droplevel("unit")
        assert set(values.index) == {"AA1", "AA2", "EU"}
        assert (values.loc[["AA2", "EU"]] == 0.0).all(axis=None)

    def test_ac3_value(self):
        """Test Natural Gas as fossil share of gas mix (AC3)
        Fossil share = 0.6, gas demand (10 heating + 20 industry) = 30.
        0.6 · (10 + 20) = 18.
        """
        assert self._values(self._network(), _shares())["AA1"] == pytest.approx(18.0)

    def test_ac4_flow_consistency_time_varying_supply(self):
        """AC4: C6-AC3 with weighting 3 and time-varying gas supply (SC-23)."""
        n = self._network(n_snapshots=2)
        n.generators_t.p["AA1 production gas"] = [90.0, 10.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Carrier__Natural_Gas,
            n,
            industry_non_energy_shares=_shares(Natural_Gas=0.25),
        )

    def test_ac5_non_negative_with_local_renewable_surplus(self):
        """AC5: renewable supply above local demand at AA2 still gives >= 0 (#97).

        The AA2 surplus enters the system-wide share: f_gas = 60 / 200 = 0.3,
        AA1 = 0.3 · (10 + 20) = 9.
        """
        n = self._network()
        _add_bus(n, "AA2 biogas", "biogas", "MWh_LHV", "AA2")
        _add_dispatched(
            n,
            "Link",
            "AA2 biogas to gas",
            {"p0": [100.0], "p1": [-100.0]},
            bus0="AA2 biogas",
            bus1="AA2 gas",
            carrier="biogas to gas",
        )
        values = self._values(n, _shares())
        assert (values >= 0).all()
        assert values["AA1"] == pytest.approx(9.0)
        assert values["AA2"] == 0.0

    def test_ac7_transport_and_store_ignored(self):
        """AC7: gas pipeline flows and the gas Store do not change f_gas."""
        n = self._network()
        _add_dispatched(
            n,
            "Link",
            "AA1-AA2 pipeline",
            {"p0": [50.0], "p1": [-50.0]},
            bus0="AA1 gas",
            bus1="AA2 gas",
            carrier="gas pipeline",
        )
        _add_dispatched(
            n, "Store", "AA2 gas Store", {"p": [30.0]}, bus="AA2 gas", carrier="gas"
        )
        assert self._values(n, _shares())["AA1"] == pytest.approx(18.0)

    def test_ac8_unknown_supplier_raises(self):
        """AC8: an unknown carrier with non-zero supply to a gas bus raises."""
        n = self._network()
        _add_dispatched(
            n,
            "Generator",
            "AA1 mystery gas",
            {"p": [5.0]},
            bus="AA1 gas",
            carrier="mystery gas",
        )
        with pytest.raises(ValueError, match="mystery gas"):
            self._values(n, _shares())

    def test_ac8_unknown_supplier_raises_without_consumers(self):
        """AC8: the unknown-supplier check also runs when no gas is consumed."""
        n = _real_network(1)
        _add_bus(n, "AA1 gas", "gas", "MWh_LHV", "AA1")
        _add_dispatched(
            n,
            "Generator",
            "AA1 mystery gas",
            {"p": [5.0]},
            bus="AA1 gas",
            carrier="mystery gas",
        )
        with pytest.raises(ValueError, match="mystery gas"):
            self._values(n, _shares())

    def test_ac8_import_gas_is_renewable(self):
        """AC8: an import gas Link instead of biogas gives the same result."""
        assert self._values(self._network("import gas"), _shares())[
            "AA1"
        ] == pytest.approx(18.0)

    def test_ac9_non_energy_use(self):
        """AC9: S = 0.25 gives NE = 5 and 0.6 · (10 + 20 − 5) = 15."""
        assert self._values(self._network(), _shares(Natural_Gas=0.25))[
            "AA1"
        ] == pytest.approx(15.0)

    def test_ac9_missing_country_uses_mean(self, caplog):
        """AC9: country CC without a row uses the mean of AA and BB with a WARNING."""
        n = self._network()
        _add_bus(n, "CC1 gas for industry", "gas for industry", "MWh_LHV", "CC1")
        _add_dispatched(
            n,
            "Load",
            "CC1 gas for industry",
            {"p": [20.0]},
            bus="CC1 gas for industry",
            carrier="gas for industry",
        )
        shares = pd.concat(
            [
                _shares(Natural_Gas=0.25),
                _shares(Natural_Gas=0.75).rename(index={"AA": "BB"}),
            ]
        )
        with caplog.at_level(logging.WARNING):
            values = self._values(n, shares)
        assert values["CC1"] == pytest.approx(0.6 * (20.0 - 10.0))
        assert any(
            "CC" in r.getMessage() and "Natural Gas" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.parametrize("share, expected", [(1.0, 6.0), (0.0, 18.0)])
    def test_ac10_share_bounds(self, share, expected):
        """AC10: S = 1 gives industry term 0 (not negative); S = 0 gives 18."""
        assert self._values(self._network(), _shares(Natural_Gas=share))[
            "AA1"
        ] == pytest.approx(expected)

    def test_no_fossil_supply(self):
        """Edge case: f_gas = 0 gives 0.0 for all locations."""
        n = self._network()
        n.generators_t.p["AA1 production gas"] = [0.0]
        assert (self._values(n, _shares()) == 0.0).all()

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_gas_consumers(self, aggregate_per_year):
        """AC6 / SC-25: no boilers and no gas for industry gives 0.0, never zero rows."""
        n = _real_network()
        _add_bus(n, "AA1 gas", "gas", "MWh_LHV", "AA1")
        result = Final_Energy_by_Carrier__Natural_Gas(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


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
    """Spec Final_Energy_by_Sector__Transportation.md AC1-AC8."""

    # d_aviation(AA) = 0.5, d_navigation(AA) = 0.2
    ENERGY_TOTALS = pd.DataFrame(
        {
            "total domestic aviation": [50.0],
            "total international aviation": [50.0],
            "total domestic navigation": [20.0],
            "total international navigation": [80.0],
        },
        index=pd.Index(["AA"], name="country"),
    )

    @staticmethod
    def _base_network(n_snapshots: int = 1) -> pypsa.Network:
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        _add_bus(n, "AA1 low voltage", "low voltage", "MWh_el", "AA1")
        _add_bus(n, "AA1 EV battery", "EV battery", "MWh_el", "AA1")
        _add_bus(n, "AA2", "AC", "MWh_el", "AA2")
        return n

    def _network(self, rail_road: bool = False, v2g: bool = False) -> pypsa.Network:
        """AC3 mock at AA1; AA2 has no transport."""
        n = self._base_network()
        lv = "AA1 low voltage"
        _add_dispatched(
            n,
            "Link",
            "AA1 BEV charger",
            {"p0": [10.0], "p1": [-9.0]},
            bus0=lv,
            bus1="AA1 EV battery",
            carrier="BEV charger",
            efficiency=0.9,
        )
        for carrier, unit, p in [
            ("land transport fuel cell", "MWh_LHV", 5.0),
            ("land transport oil", "land transport", 40.0),
            ("kerosene for aviation", "MWh_LHV", 20.0),
            ("shipping oil", "MWh_LHV", 10.0),
            ("shipping methanol", "MWh_LHV", 5.0),
        ]:
            bus_carrier = "H2" if carrier == "land transport fuel cell" else carrier
            _add_bus(n, f"AA1 {bus_carrier}", bus_carrier, unit, "AA1")
            _add_dispatched(
                n,
                "Load",
                f"AA1 {carrier}",
                {"p": [p]},
                bus=f"AA1 {bus_carrier}",
                carrier=carrier,
            )
        _add_dispatched(
            n,
            "Load",
            "AA1 land transport EV",
            {"p": [8.0]},
            bus="AA1 EV battery",
            carrier="land transport EV",
        )
        if rail_road:
            _add_dispatched(
                n,
                "Load",
                "AA1 electricity for rail",
                {"p": [2.0]},
                bus=lv,
                carrier="electricity for rail",
            )
            _add_dispatched(
                n,
                "Load",
                "AA1 electricity for road",
                {"p": [4.0]},
                bus=lv,
                carrier="electricity for road",
            )
        if v2g:
            _add_dispatched(
                n,
                "Link",
                "AA1 V2G",
                {"p0": [3.0], "p1": [-3.0]},
                bus0="AA1 EV battery",
                bus1=lv,
                carrier="V2G",
            )
        return n

    def _normalised(self, n: pypsa.Network, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Sector__Transportation(
            n, energy_totals=self.ENERGY_TOTALS, **kwargs
        )
        return remap_unit_index(result).groupby("location").sum()

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC5 / AC6: C6 format incl. unit `land transport`; AA2 is 0.0."""
        n = self._network()
        result = Final_Energy_by_Sector__Transportation(
            n, aggregate_per_year=aggregate_per_year, energy_totals=self.ENERGY_TOTALS
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert "land transport" in set(result.index.get_level_values("unit"))
        aa2 = result.xs("AA2", level="location")
        assert (aa2 == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3: 10 + 5 + 40 + 0.5·20 + 0.2·(10 + 5) = 68; no charger efficiency."""
        values = self._normalised(self._network())
        assert values["AA1"] == pytest.approx(68.0)
        assert (values >= 0).all()

    def test_ac3_rail_counted_road_not(self):
        """AC3: electricity for rail 2 counts, electricity for road 4 does not: 70."""
        assert self._normalised(self._network(rail_road=True))["AA1"] == pytest.approx(
            70.0
        )

    def test_ac3_v2g_subtracted(self):
        """AC3: a V2G feed-in of 3 gives 67."""
        assert self._normalised(self._network(rail_road=True, v2g=True))[
            "AA1"
        ] == pytest.approx(67.0)

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._base_network(n_snapshots=2)
        lv = "AA1 low voltage"
        _add_dispatched(
            n,
            "Link",
            "AA1 BEV charger",
            {"p0": [4.0, 1.0], "p1": [-3.6, -0.9]},
            bus0=lv,
            bus1="AA1 EV battery",
            carrier="BEV charger",
        )
        _add_dispatched(
            n,
            "Link",
            "AA1 V2G",
            {"p0": [0.0, 3.0], "p1": [0.0, -3.0]},
            bus0="AA1 EV battery",
            bus1=lv,
            carrier="V2G",
        )
        _add_bus(
            n, "AA1 kerosene for aviation", "kerosene for aviation", "MWh_LHV", "AA1"
        )
        _add_dispatched(
            n,
            "Load",
            "AA1 kerosene for aviation",
            {"p": [20.0, 10.0]},
            bus="AA1 kerosene for aviation",
            carrier="kerosene for aviation",
        )
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Sector__Transportation, n, energy_totals=self.ENERGY_TOTALS
        )

    def test_ac8_v2g_not_clipped(self):
        """AC8: BEV 4 / 0 and V2G 0 / 3 give snapshot values 4 / −3, yearly 1."""
        n = self._base_network(n_snapshots=2)
        lv = "AA1 low voltage"
        _add_dispatched(
            n,
            "Link",
            "AA1 BEV charger",
            {"p0": [4.0, 0.0], "p1": [-3.6, 0.0]},
            bus0=lv,
            bus1="AA1 EV battery",
            carrier="BEV charger",
        )
        _add_dispatched(
            n,
            "Link",
            "AA1 V2G",
            {"p0": [0.0, 3.0], "p1": [0.0, -3.0]},
            bus0="AA1 EV battery",
            bus1=lv,
            carrier="V2G",
        )
        series = Final_Energy_by_Sector__Transportation(
            n, aggregate_per_year=False, energy_totals=self.ENERGY_TOTALS
        )
        assert series.droplevel("unit").loc["AA1"].tolist() == pytest.approx(
            [4.0, -3.0]
        )
        assert self._normalised(n)["AA1"] == pytest.approx(1.0)

    def test_missing_country_in_energy_totals_raises(self):
        """D4: non-zero aviation demand in a country without energy totals raises MissingInputError."""
        n = self._network()
        _add_bus(
            n, "BB1 kerosene for aviation", "kerosene for aviation", "MWh_LHV", "BB1"
        )
        _add_dispatched(
            n,
            "Load",
            "BB1 kerosene for aviation",
            {"p": [1.0]},
            bus="BB1 kerosene for aviation",
            carrier="kerosene for aviation",
        )
        with pytest.raises(MissingInputError, match="BB"):
            Final_Energy_by_Sector__Transportation(n, energy_totals=self.ENERGY_TOTALS)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_transport(self, aggregate_per_year):
        """AC6: a network without transport carriers gives 0.0 everywhere."""
        n = _real_network()
        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        result = Final_Energy_by_Sector__Transportation(
            n, aggregate_per_year=aggregate_per_year, energy_totals=self.ENERGY_TOTALS
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Agriculture
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorAgriculture:
    """Spec Final_Energy_by_Sector__Agriculture.md AC1-AC6."""

    @staticmethod
    def _network(chp: bool = False, n_snapshots: int = 1) -> pypsa.Network:
        """AC3 mock at A (sigma_rural,agr = 0.25, I_rural = 12); B is empty."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots

        def dispatch(component, name, values, **attrs):
            series = {k: [v * o for o in ones] for k, v in values.items()}
            _add_dispatched(n, component, name, series, **attrs)

        for bus, carrier, unit in [
            ("A", "AC", "MWh_el"),
            ("A low voltage", "low voltage", "MWh_el"),
            ("A rural heat", "rural heat", "MWh_th"),
            ("A solid biomass", "solid biomass", "MWh_LHV"),
            ("A biogas", "biogas", "MWh_LHV"),
            ("A oil", "oil", "MWh_LHV"),
            ("A agriculture machinery oil", "agriculture machinery oil", "MWh_LHV"),
            ("B", "AC", "MWh_el"),
        ]:
            _add_bus(n, bus, carrier, unit, bus.split()[0])
        lv, heat = "A low voltage", "A rural heat"
        dispatch(
            "Load",
            "A agriculture electricity",
            {"p": 2.0},
            bus=lv,
            carrier="agriculture electricity",
        )
        dispatch(
            "Load",
            "A agriculture machinery electric",
            {"p": 1.0},
            bus=lv,
            carrier="agriculture machinery electric",
        )
        dispatch(
            "Load",
            "A agriculture machinery oil",
            {"p": 4.0},
            bus="A agriculture machinery oil",
            carrier="agriculture machinery oil",
        )
        dispatch(
            "Load",
            "A agriculture heat",
            {"p": 3.0},
            bus=heat,
            carrier="agriculture heat",
        )
        dispatch(
            "Load",
            "A rural heat",
            {"p": 13.0 if chp else 9.0},
            bus=heat,
            carrier="rural heat",
        )
        dispatch(
            "Link",
            "A rural biomass boiler",
            {"p0": 8.0, "p1": -7.2},
            bus0="A solid biomass",
            bus1=heat,
            carrier="rural biomass boiler",
        )
        # heat pumps in PyPSA-AT: bus0 = heat bus, bus1 = low voltage
        dispatch(
            "Link",
            "A rural ground heat pump",
            {"p0": -4.8, "p1": 4.0},
            bus0=heat,
            bus1=lv,
            carrier="rural ground heat pump",
        )
        dispatch(
            "Link",
            "A agriculture machinery oil CC",
            {"p0": 5.0, "p1": -4.0},
            bus0="A oil",
            bus1="A agriculture machinery oil",
            carrier="agriculture machinery oil CC",
        )
        if chp:
            dispatch(
                "Link",
                "A biogas CHP",
                {"p0": 10.0, "p1": -2.0, "p2": -4.0},
                bus0="A biogas",
                bus1="A",
                bus2=heat,
                carrier="biogas CHP",
            )
        return n

    @staticmethod
    def _values(n: pypsa.Network, **kwargs: object) -> pd.Series:
        return Final_Energy_by_Sector__Agriculture(n, **kwargs).droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 (C6 output format) and AC6 (every location present).

        Result has the C6 format with unit MWh; location B holds no
        agriculture loads and gets 0.0.
        """
        n = self._network()
        result = Final_Energy_by_Sector__Agriculture(
            n, aggregate_per_year=aggregate_per_year
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert set(result.index.get_level_values("unit")) == {"MWh"}
        values = result.droplevel("unit")
        assert set(values.index) == {"A", "B"}
        assert (values.loc[["B"]] == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3 (reference value) and AC5 (values >= 0).

        Loads agriculture electricity 2, machinery electric 1, machinery
        oil 4; decentral heat input I_rural = 12 with agriculture share
        sigma_rural,agr = 0.25: 2 + 1 + 4 + 0.25 · 12 = 10. Losses of the
        machinery oil CC link (5 in, 4 out) are not counted.
        """
        values = self._values(self._network())
        assert values["A"] == pytest.approx(10.0)
        assert (values >= 0).all()

    def test_ac3b_chp_heat(self):
        """AC3b (CHP heat output counts as decentral heat input).

        As AC3 plus a biogas CHP with heat output 4 to rural heat: I_rural =
        12 + 4 = 16, sigma_rural,agr = 3/16, result 2 + 1 + 4 + 3 = 10.
        """
        assert self._values(self._network(chp=True))["A"] == pytest.approx(10.0)

    def test_flow_consistency(self):
        """AC4 (C6-AC3, class flow): yearly value = weighted sum of snapshots.

        Checked on a two-snapshot network with snapshot weighting 3.
        """
        n = self._network(chp=True, n_snapshots=2)
        n.loads_t.p["A agriculture electricity"] = [2.0, 6.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(Final_Energy_by_Sector__Agriculture, n)

    def test_agriculture_heat_on_central_heat_raises(self):
        """Edge case: an agriculture heat Load on urban central heat raises."""
        n = self._network()
        _add_bus(n, "A urban central heat", "urban central heat", "MWh_th", "A")
        _add_dispatched(
            n,
            "Load",
            "A central agriculture heat",
            {"p": [1.0]},
            bus="A urban central heat",
            carrier="agriculture heat",
        )
        with pytest.raises(ValueError, match="A central agriculture heat"):
            Final_Energy_by_Sector__Agriculture(n)

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_agriculture(self, aggregate_per_year):
        """AC6 (C6-AC6, every location present): without agriculture loads.

        A network without any agriculture load gives 0.0 at every location.
        """
        n = _real_network()
        _add_bus(n, "A", "AC", "MWh_el", "A")
        result = Final_Energy_by_Sector__Agriculture(
            n, aggregate_per_year=aggregate_per_year
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Residential_and_Commercial
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorResidentialAndCommercial:
    """Spec Final_Energy_by_Sector__Residential_and_Commercial.md AC1-AC7."""

    CONFIG = {"sector": {"district_heating": {"district_heating_loss": 0.15}}}

    @staticmethod
    def _network(n_snapshots: int = 1) -> pypsa.Network:
        """AC3 mock at A (I_rural = 11, sigma_rural,rc = 0.75); B is empty."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots

        def dispatch(component, name, values, **attrs):
            series = {k: [v * o for o in ones] for k, v in values.items()}
            _add_dispatched(n, component, name, series, **attrs)

        for bus, carrier, unit, loc in [
            ("A", "AC", "MWh_el", "A"),
            ("B", "AC", "MWh_el", "B"),
            ("A low voltage", "low voltage", "MWh_el", "A"),
            ("A rural heat", "rural heat", "MWh_th", "A"),
            ("A urban central heat", "urban central heat", "MWh_th", "A"),
            ("A gas", "gas", "MWh_LHV", "A"),
            ("EU oil", "oil", "MWh_LHV", "EU"),
            ("A solid biomass", "solid biomass", "MWh_LHV", "A"),
            ("A EV battery", "EV battery", "MWh_el", "A"),
            ("A home battery", "home battery", "MWh_el", "A"),
        ]:
            _add_bus(n, bus, carrier, unit, loc)
        lv, heat = "A low voltage", "A rural heat"
        dispatch("Load", "A electricity", {"p": 10.0}, bus=lv, carrier="electricity")
        dispatch(
            "Load",
            "A urban central heat",
            {"p": 23.0},
            bus="A urban central heat",
            carrier="urban central heat",
        )
        dispatch("Load", "A rural heat", {"p": 6.0}, bus=heat, carrier="rural heat")
        dispatch(
            "Load",
            "A agriculture heat",
            {"p": 2.0},
            bus=heat,
            carrier="agriculture heat",
        )
        dispatch(
            "Link",
            "A home battery charger",
            {"p0": 1.0, "p1": -1.0},
            bus0=lv,
            bus1="A home battery",
            carrier="home battery charger",
        )
        dispatch(
            "Link",
            "A BEV charger",
            {"p0": 3.0, "p1": -3.0},
            bus0=lv,
            bus1="A EV battery",
            carrier="BEV charger",
        )
        # heat pumps in PyPSA-AT: bus0 = heat bus, bus1 = low voltage
        dispatch(
            "Link",
            "A rural air heat pump",
            {"p0": -6.0, "p1": 2.0},
            bus0=heat,
            bus1=lv,
            carrier="rural air heat pump",
        )
        dispatch(
            "Link",
            "A rural gas boiler",
            {"p0": 4.0, "p1": -3.6},
            bus0="A gas",
            bus1=heat,
            carrier="rural gas boiler",
        )
        dispatch(
            "Link",
            "A rural oil boiler",
            {"p0": 2.0, "p1": -1.8},
            bus0="EU oil",
            bus1=heat,
            carrier="rural oil boiler",
        )
        dispatch(
            "Link",
            "A rural biomass boiler",
            {"p0": 1.0, "p1": -0.9},
            bus0="A solid biomass",
            bus1=heat,
            carrier="rural biomass boiler",
        )
        dispatch(
            "Generator",
            "A rural solar thermal",
            {"p": 2.0},
            bus=heat,
            carrier="rural solar thermal",
        )
        return n

    def _values(self, n: pypsa.Network, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            n, config=self.CONFIG, **kwargs
        )
        return result.droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format, unit MWh; B and EU present with 0.0."""
        n = self._network()
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            n, aggregate_per_year=aggregate_per_year, config=self.CONFIG
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert set(result.index.get_level_values("unit")) == {"MWh"}
        values = result.droplevel("unit")
        assert set(values.index) == {"A", "B", "EU"}
        assert (values.loc[["B", "EU"]] == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3 / AC5: 10 + 23/1.15 + 0.75 · 11 = 38.25; heat pump only via D8."""
        values = self._values(self._network())
        assert values["A"] == pytest.approx(38.25)
        assert (values >= 0).all()

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._network(n_snapshots=2)
        n.loads_t.p["A electricity"] = [10.0, 4.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Sector__Residential_and_Commercial, n, config=self.CONFIG
        )

    def test_ac7_d8_consistency_with_agriculture(self):
        """AC7: decentral parts of R&C and Agriculture add up to I_rural = 11."""
        n = self._network()
        rc_decentral = self._values(n)["A"] - 10.0 - 23.0 / 1.15
        agriculture = Final_Energy_by_Sector__Agriculture(n).droplevel("unit")["A"]
        assert rc_decentral + agriculture == pytest.approx(11.0)

    @pytest.mark.parametrize("config", [None, {}, {"sector": {"district_heating": {}}}])
    def test_missing_loss_raises_missing_input(self, config):
        """Section 8: missing district_heating_loss raises MissingInputError."""
        with pytest.raises(MissingInputError, match="district_heating_loss"):
            Final_Energy_by_Sector__Residential_and_Commercial(
                self._network(), config=config
            )

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_carriers(self, aggregate_per_year):
        """AC6: a network without any of the carriers gives 0.0 everywhere."""
        n = _real_network()
        _add_bus(n, "A", "AC", "MWh_el", "A")
        result = Final_Energy_by_Sector__Residential_and_Commercial(
            n, aggregate_per_year=aggregate_per_year, config=self.CONFIG
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Industry
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorIndustry:
    """Spec Final_Energy_by_Sector__Industry.md AC1-AC8."""

    @staticmethod
    def _network(n_snapshots: int = 1) -> pypsa.Network:
        """AC3 mock at AA1 (sum 38) and AC8 decentral heat at AA2."""
        n = _real_network(n_snapshots)
        n.snapshot_weightings.loc[:, :] = 1.0
        ones = [1.0] * n_snapshots

        def dispatch(component, name, values, **attrs):
            series = {k: [v * o for o in ones] for k, v in values.items()}
            _add_dispatched(n, component, name, series, **attrs)

        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        _add_bus(n, "AA3", "AC", "MWh_el", "AA3")
        _add_bus(n, "AA1 low voltage", "low voltage", "MWh_el", "AA1")
        _add_bus(n, "AA1 urban central heat", "urban central heat", "MWh_th", "AA1")
        _add_bus(n, "AA1 gas", "gas", "MWh_LHV", "AA1")
        dispatch(
            "Load",
            "AA1 industry electricity",
            {"p": 10.0},
            bus="AA1 low voltage",
            carrier="industry electricity",
        )
        dispatch(
            "Load",
            "AA1 low-temperature heat for industry",
            {"p": 5.0},
            bus="AA1 urban central heat",
            carrier="low-temperature heat for industry",
        )
        for carrier, bus_carrier, p in [
            ("gas for industry", "gas for industry", 8.0),
            ("H2 for industry", "H2", 2.0),
            ("naphtha for industry", "naphtha for industry", 6.0),
            ("solid biomass for industry", "solid biomass for industry", 3.0),
            ("coal for industry", "coal for industry", 4.0),
            ("industry methanol", "industry methanol", 7.0),
        ]:
            _add_bus(n, f"AA1 {bus_carrier}", bus_carrier, "MWh_LHV", "AA1")
            dispatch(
                "Load",
                f"AA1 {carrier}",
                {"p": p},
                bus=f"AA1 {bus_carrier}",
                carrier=carrier,
            )
        dispatch(
            "Link",
            "AA1 gas for industry CC",
            {"p0": 10.0, "p1": -9.0},
            bus0="AA1 gas",
            bus1="AA1 gas for industry",
            carrier="gas for industry CC",
        )
        # AC8 at AA2: no urban central heat bus; sigma_urban decentral,ind = 0.25
        _add_bus(n, "AA2 urban decentral heat", "urban decentral heat", "MWh_th", "AA2")
        _add_bus(n, "AA2 gas", "gas", "MWh_LHV", "AA2")
        dispatch(
            "Load",
            "AA2 low-temperature heat for industry",
            {"p": 1.0},
            bus="AA2 urban decentral heat",
            carrier="low-temperature heat for industry",
        )
        dispatch(
            "Load",
            "AA2 urban decentral heat",
            {"p": 3.0},
            bus="AA2 urban decentral heat",
            carrier="urban decentral heat",
        )
        dispatch(
            "Link",
            "AA2 urban decentral gas boiler",
            {"p0": 6.0, "p1": -4.0},
            bus0="AA2 gas",
            bus1="AA2 urban decentral heat",
            carrier="urban decentral gas boiler",
        )
        return n

    @staticmethod
    def _values(n: pypsa.Network, shares: pd.DataFrame, **kwargs: object) -> pd.Series:
        result = Final_Energy_by_Sector__Industry(
            n, industry_non_energy_shares=shares, **kwargs
        )
        return result.droplevel("unit")

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_format_and_every_location(self, aggregate_per_year):
        """AC1 / AC2 / AC6: C6 format, unit MWh; AA3 without industry is 0.0."""
        n = self._network()
        result = Final_Energy_by_Sector__Industry(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert set(result.index.get_level_values("unit")) == {"MWh"}
        values = result.droplevel("unit")
        assert set(values.index) == {"AA1", "AA2", "AA3"}
        assert (values.loc[["AA3"]] == 0.0).all(axis=None)

    def test_ac3_value(self):
        """AC3 / AC5: 10 + 5 + 8 + 2 + 6 + 3 + 4 = 38; methanol and CC losses excluded."""
        values = self._values(self._network(), _shares())
        assert values["AA1"] == pytest.approx(38.0)
        assert (values >= 0).all()

    def test_ac7_non_energy_use(self, caplog):
        """AC7: NE_gas 2, NE_naphtha 3 → 33; with NE_coal 1 → 32; H2 and coke WARNINGs."""
        n = self._network()
        assert self._values(n, _shares(Natural_Gas=0.25, Oil=0.5))[
            "AA1"
        ] == pytest.approx(33.0)
        with caplog.at_level(logging.WARNING):
            values = self._values(n, _shares(Natural_Gas=0.25, Oil=0.5, Coal=0.25))
        assert values["AA1"] == pytest.approx(32.0)
        messages = [r.getMessage() for r in caplog.records]
        assert any("H2 non-energy use is skipped" in m for m in messages)
        assert any("Coke correction is skipped" in m for m in messages)

    def test_ac8_decentral_heat_share(self):
        """AC8: the decentral contribution at AA2 is 0.25 · 6 = 1.5, not the heat 1."""
        assert self._values(self._network(), _shares())["AA2"] == pytest.approx(1.5)

    def test_flow_consistency(self):
        """AC4: C6-AC3 on a network with snapshot weighting 3."""
        n = self._network(n_snapshots=2)
        n.loads_t.p["AA1 industry electricity"] = [10.0, 2.0]
        n.snapshot_weightings.loc[:, :] = WEIGHT
        _check_flow_consistency(
            Final_Energy_by_Sector__Industry,
            n,
            industry_non_energy_shares=_shares(Natural_Gas=0.25),
        )

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_no_industry(self, aggregate_per_year):
        """AC6: a network without industry carriers gives 0.0 everywhere."""
        n = _real_network()
        _add_bus(n, "AA1", "AC", "MWh_el", "AA1")
        result = Final_Energy_by_Sector__Industry(
            n,
            aggregate_per_year=aggregate_per_year,
            industry_non_energy_shares=_shares(),
        )
        _check_c6_format(result, n, aggregate_per_year)
        assert (result == 0.0).all(axis=None)


# ---------------------------------------------------------------------------
# Tests for aggregate_per_year=False (timeseries output)
# ---------------------------------------------------------------------------


class TestAggregatePerYearFalse:
    """Tests verifying that all statistics functions return a DataFrame with
    snapshot columns when called with ``aggregate_per_year=False``."""

    _FUNCTIONS = [
        Final_Energy_by_Carrier__Electricity,
        Final_Energy_by_Carrier__Coal,
    ]

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
