"""Tests for pypsa_validation_processing.utils."""

import pandas as pd
import pypsa
import pytest

from pypsa_validation_processing.utils import REGION_MAPPING, attribute_locations

GROUPBY = ["name", "carrier", "location", "unit"]


def _network(locations: list[str]) -> pypsa.Network:
    """Return an empty network with two 3-hour snapshots and one bus per location."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=2, freq="3h"))
    n.snapshot_weightings.loc[:, :] = 3.0
    for location in locations:
        n.add("Bus", f"{location} rural heat", carrier="rural heat", location=location)
    return n


def _add_link(n: pypsa.Network, name: str, p0: list[float], **attrs: object) -> None:
    """Add a lossless Link with the dispatch *p0* (MW) at ``bus0``."""
    n.add("Link", name, efficiency=1.0, **attrs)
    n.links_t.p0[name] = p0
    n.links_t.p1[name] = [-v for v in p0]


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


class TestAttributeLocations:
    @pytest.fixture
    def network(self) -> pypsa.Network:
        n = _network(["AT11", "DE1"])
        n.add("Bus", "EU oil", carrier="oil", location="EU", unit="MWh_LHV")
        n.add("Bus", "EU oil 2", carrier="oil", location="EU", unit="MWh_LHV")
        n.add("Bus", "AT11 gas", carrier="gas", location="AT11", unit="MWh_LHV")
        n.add("Load", "EU oil load", bus="EU oil", carrier="oil load")
        n.loads_t.p["EU oil load"] = [1.0, 1.0]
        _add_link(
            n,
            "AT11 rural oil boiler",
            [1.0, 2.0],
            bus0="EU oil",
            bus1="AT11 rural heat",
            carrier="rural oil boiler",
        )
        _add_link(
            n,
            "DE1 rural oil boiler",
            [4.0, 0.0],
            bus0="EU oil",
            bus1="DE1 rural heat",
            carrier="rural oil boiler",
        )
        _add_link(
            n,
            "AT11 rural gas boiler",
            [5.0, 5.0],
            bus0="AT11 gas",
            bus1="AT11 rural heat",
            carrier="rural gas boiler",
        )
        _add_link(
            n,
            "EU oil transfer",
            [2.0, 2.0],
            bus0="EU oil",
            bus1="EU oil 2",
            carrier="oil transfer",
        )
        return n

    def test_copperplate_link_moves_to_bus1(self, network):
        """D1.3: a Link withdrawal from EU oil is attributed to the location of bus1."""
        flows = network.statistics.withdrawal(
            carrier="rural oil boiler", groupby=GROUPBY, nice_names=False
        )
        result = attribute_locations(network, flows)
        locations = result.groupby("location").sum()
        assert locations.to_dict() == {"AT11": 9.0, "DE1": 12.0}

    def test_regional_link_keeps_location(self, network):
        """D1.2: a Link flow at a regional bus keeps the location of that bus."""
        flows = network.statistics.withdrawal(
            carrier="rural gas boiler", groupby=GROUPBY, nice_names=False
        )
        result = attribute_locations(network, flows)
        assert result.index.get_level_values("location").tolist() == ["AT11"]

    def test_copperplate_bus1_stays_eu(self, network):
        """D1.4: a Link between two copperplate buses stays at EU."""
        flows = network.statistics.withdrawal(
            carrier="oil transfer", groupby=GROUPBY, nice_names=False
        )
        result = attribute_locations(network, flows)
        assert result.index.get_level_values("location").tolist() == ["EU"]

    def test_load_on_copperplate_stays_eu(self, network):
        """D1.1: a Load keeps the location of its bus, also on a copperplate bus."""
        flows = network.statistics.withdrawal(
            carrier="oil load", groupby=GROUPBY, nice_names=False
        )
        result = attribute_locations(network, flows)
        assert result.index.get_level_values("location").tolist() == ["EU"]

    def test_time_series_keeps_columns(self, network):
        """D1: a time series result keeps its snapshot columns and values."""
        flows = network.statistics.withdrawal(
            carrier="rural oil boiler",
            groupby=GROUPBY,
            groupby_time=False,
            nice_names=False,
        )
        result = attribute_locations(network, flows)
        assert isinstance(result, pd.DataFrame)
        assert result.columns.equals(flows.columns)
        assert result.groupby("location").sum().loc["DE1"].tolist() == [4.0, 0.0]

    def test_missing_level_raises(self, network):
        """D1: flows without a name level raise ValueError naming the level."""
        flows = network.statistics.withdrawal(
            carrier="rural oil boiler", groupby=["location"], nice_names=False
        )
        with pytest.raises(ValueError, match="name"):
            attribute_locations(network, flows)
