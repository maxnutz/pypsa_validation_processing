"""Tests for pypsa_validation_processing.utils."""

import math

import pandas as pd
import pytest

from pypsa_validation_processing.utils import REGION_MAPPING, trace_non_fossil_fraction


class TestRegionsCodes:
    def test_is_dict(self):
        assert isinstance(REGION_MAPPING, dict)

    def test_has_all_27_member_states(self):
        # All 27 EU member state ISO codes must be present
        expected_codes = {
            "AT",
            "BE",
            "BG",
            "CY",
            "CZ",
            "DE",
            "DK",
            "EE",
            "ES",
            "FI",
            "FR",
            "GR",
            "HR",
            "HU",
            "IE",
            "IT",
            "LT",
            "LU",
            "LV",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SE",
            "SI",
            "SK",
        }
        assert expected_codes.issubset(REGION_MAPPING.keys())

    def test_sample_mappings(self):
        assert REGION_MAPPING["AT"] == "Austria"
        assert REGION_MAPPING["DE"] == "Germany"
        assert REGION_MAPPING["FR"] == "France"

    def test_values_are_strings(self):
        for key, value in REGION_MAPPING.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(
                value, str
            ), f"Value {value!r} for key {key!r} is not a string"


def _broadcast(values: dict, snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """Build a (key x snapshot) frame from scalar or per-snapshot values."""
    rows = {
        key: val if isinstance(val, list) else [val] * len(snapshots)
        for key, val in values.items()
    }
    return pd.DataFrame(rows, index=snapshots).T


class _FakeStatistics:
    """Minimal n.statistics stand-in for trace_non_fossil_fraction tests."""

    def __init__(
        self,
        non_fossil_supply: pd.DataFrame,
        fossil_supply: pd.DataFrame,
        flows: pd.DataFrame,
    ):
        self._non_fossil_supply = non_fossil_supply
        self._fossil_supply = fossil_supply
        self._flows = flows

    def supply(self, *, components, **_):
        source = (
            self._non_fossil_supply if components == "Link" else self._fossil_supply
        )
        result = source.copy()
        result.index = pd.MultiIndex.from_arrays(
            [result.index, ["MWh"] * len(result)], names=["bus", "unit"]
        )
        return result

    def transmission(self, **_):
        result = self._flows.copy()
        result.index = pd.MultiIndex.from_arrays(
            [
                result.index.get_level_values(0),
                result.index.get_level_values(1),
                ["MWh"] * len(result),
            ],
            names=["bus0", "bus1", "unit"],
        )
        return result


class _FakeNetwork:
    def __init__(self, non_fossil_supply, fossil_supply, flows, snapshots):
        self.statistics = _FakeStatistics(non_fossil_supply, fossil_supply, flows)
        self.snapshots = snapshots


def _network(non_fossil: dict, fossil: dict, flows: dict, periods: int = 1):
    snapshots = pd.date_range("2019-01-01", periods=periods, freq="h")
    non_fossil_df = _broadcast(non_fossil, snapshots)
    fossil_df = _broadcast(fossil, snapshots)
    flows_df = _broadcast(flows, snapshots)
    flows_df.index = pd.MultiIndex.from_tuples(flows_df.index, names=["bus0", "bus1"])
    return _FakeNetwork(non_fossil_df, fossil_df, flows_df, snapshots)


class TestTraceNonFossilFraction:
    """Test suite for trace_non_fossil_fraction (proportional flow tracing)."""

    def _trace(self, network):
        return trace_non_fossil_fraction(
            network,
            bus_carrier="gas",
            pipeline_carriers=["gas pipeline"],
            non_fossil_carriers=["biogas to gas"],
            fossil_carriers=["pipeline gas"],
        )

    def test_single_bus_mixed_local_supply(self):
        """No pipelines: fraction is just the local non-fossil share."""
        network = _network(non_fossil={"A gas": 30.0}, fossil={"A gas": 70.0}, flows={})
        result = self._trace(network)
        assert result.loc["A gas"].iloc[0] == pytest.approx(0.3)

    def test_non_fossil_content_propagates_through_zero_local_supply_bus(self):
        """A bus with no local production still inherits the non-fossil
        content carried in via the pipeline network - this two-hop case is
        exactly what a naive local-supply-only ratio would miss."""
        network = _network(
            non_fossil={"A gas": 100.0, "B gas": 0.0, "C gas": 0.0},
            fossil={"A gas": 0.0, "B gas": 0.0, "C gas": 0.0},
            flows={("A gas", "B gas"): 50.0, ("B gas", "C gas"): 50.0},
        )
        result = self._trace(network)
        assert result.loc["B gas"].iloc[0] == pytest.approx(1.0)
        assert result.loc["C gas"].iloc[0] == pytest.approx(1.0)

    def test_reversed_flow_sign_convention(self):
        """A negative bus0->bus1 transmission value means gas physically
        flows bus1->bus0 (matches at_port='bus1' sign convention)."""
        network = _network(
            non_fossil={"A gas": 0.0, "B gas": 100.0},
            fossil={"A gas": 0.0, "B gas": 0.0},
            flows={("A gas", "B gas"): -50.0},
        )
        result = self._trace(network)
        assert result.loc["A gas"].iloc[0] == pytest.approx(1.0)

    def test_zero_inflow_bus_is_nan(self):
        """A bus with neither local supply nor pipeline inflow is undefined."""
        network = _network(
            non_fossil={"A gas": 0.0, "B gas": 0.0},
            fossil={"A gas": 0.0, "B gas": 0.0},
            flows={("A gas", "B gas"): 0.0},
        )
        result = self._trace(network)
        assert math.isnan(result.loc["A gas"].iloc[0])
        assert math.isnan(result.loc["B gas"].iloc[0])

    def test_cyclic_mesh_is_solved_consistently(self):
        """Three buses with a two-way pipeline mesh (A<->B<->C<->A) should
        still converge to a consistent, bounded solution."""
        network = _network(
            non_fossil={"A gas": 60.0, "B gas": 0.0, "C gas": 0.0},
            fossil={"A gas": 40.0, "B gas": 0.0, "C gas": 0.0},
            flows={
                ("A gas", "B gas"): 20.0,
                ("B gas", "C gas"): 20.0,
                ("C gas", "A gas"): 5.0,
            },
        )
        result = self._trace(network)
        fractions = result.iloc[:, 0]
        assert ((fractions >= 0) & (fractions <= 1)).all()
        # A produces the only source; everything downstream must inherit
        # exactly A's own mix once the mesh reaches steady state.
        assert fractions.loc["B gas"] == pytest.approx(fractions.loc["A gas"])
        assert fractions.loc["C gas"] == pytest.approx(fractions.loc["A gas"])
