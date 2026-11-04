"""Tests for pypsa_validation_processing.utils."""

import logging

import pandas as pd
import pypsa
import pytest

from pypsa_validation_processing.utils import (
    REGION_MAPPING,
    apply_domestic_share,
    attribute_locations,
    fossil_gas_share,
    fossil_oil_share,
    non_energy_use,
)

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


class TestFossilOilShare:
    @staticmethod
    def _oil_network(supply: dict[str, float]) -> pypsa.Network:
        """Return a network whose EU oil bus is supplied by Links of the given carriers."""
        n = _network(["AT11"])
        n.add("Bus", "EU oil", carrier="oil", location="EU", unit="MWh_LHV")
        n.add("Bus", "AT11 feed", carrier="feed", location="AT11")
        for carrier, p0 in supply.items():
            _add_link(
                n,
                f"AT11 {carrier}",
                [p0, p0],
                bus0="AT11 feed",
                bus1="EU oil",
                carrier=carrier,
            )
        return n

    def test_share_of_oil_refining(self):
        """D2: f_oil is the yearly oil refining supply over all C_oil supply."""
        n = self._oil_network({"oil refining": 3.0, "Fischer-Tropsch": 1.0})
        assert fossil_oil_share(n) == pytest.approx(0.75)

    def test_import_oil_is_non_fossil(self):
        """D2: import oil counts as non-fossil supply (OQ-23)."""
        n = self._oil_network({"oil refining": 1.0, "import oil": 1.0})
        assert fossil_oil_share(n) == pytest.approx(0.5)

    def test_store_is_excluded(self):
        """D2: supply of the oil Store does not enter f_oil."""
        n = self._oil_network({"oil refining": 1.0, "electrobiofuels": 1.0})
        n.add("Store", "EU oil Store", bus="EU oil", carrier="oil")
        n.stores_t.p["EU oil Store"] = [10.0, 10.0]
        assert fossil_oil_share(n) == pytest.approx(0.5)

    def test_no_supply_gives_zero(self):
        """D2: without oil supply f_oil is 0."""
        n = self._oil_network({"oil refining": 0.0})
        assert fossil_oil_share(n) == 0.0

    def test_unknown_carrier_with_supply_raises(self):
        """D2: an unknown carrier with non-zero yearly supply raises ValueError naming it."""
        n = self._oil_network({"oil refining": 1.0, "mystery oil": 1.0})
        with pytest.raises(ValueError, match="mystery oil"):
            fossil_oil_share(n)

    def test_unknown_carrier_without_supply_is_ignored(self):
        """D2: an unknown carrier with zero yearly supply is ignored."""
        n = self._oil_network({"oil refining": 1.0, "mystery oil": 0.0})
        assert fossil_oil_share(n) == pytest.approx(1.0)


class TestFossilGasShare:
    @staticmethod
    def _gas_network(
        generators: dict[str, float], links: dict[str, float]
    ) -> pypsa.Network:
        """Return a network with two gas buses supplied by the given Generators and Links."""
        n = _network(["AT11"])
        n.add("Bus", "AT11 gas", carrier="gas", location="AT11", unit="MWh_LHV")
        n.add("Bus", "DE1 gas", carrier="gas", location="DE1", unit="MWh_LHV")
        n.add("Bus", "AT11 feed", carrier="feed", location="AT11")
        for carrier, p in generators.items():
            n.add("Generator", f"AT11 {carrier}", bus="AT11 gas", carrier=carrier)
            n.generators_t.p[f"AT11 {carrier}"] = [p, p]
        for carrier, p0 in links.items():
            _add_link(
                n,
                f"AT11 {carrier}",
                [p0, p0],
                bus0="AT11 feed",
                bus1="AT11 gas",
                carrier=carrier,
            )
        return n

    def test_share_of_fossil_generators(self):
        """D3: f_gas is the fossil Generator supply over fossil and renewable supply."""
        n = self._gas_network(
            {"pipeline gas": 2.0, "lng gas": 1.0}, {"biogas to gas": 1.0}
        )
        assert fossil_gas_share(n) == pytest.approx(0.75)

    def test_import_gas_is_non_fossil(self):
        """D3: import gas counts as non-fossil supply (OQ-23)."""
        n = self._gas_network({"production gas": 1.0}, {"import gas": 3.0})
        assert fossil_gas_share(n) == pytest.approx(0.25)

    def test_transport_and_store_are_excluded(self):
        """D3: gas pipelines, other Links between gas buses and the gas Store are excluded."""
        n = self._gas_network({"pipeline gas": 1.0}, {"Sabatier": 1.0})
        for carrier in ["gas pipeline", "gas pipeline new", "gas compressor"]:
            _add_link(
                n,
                f"AT11 {carrier}",
                [5.0, 5.0],
                bus0="AT11 gas",
                bus1="DE1 gas",
                carrier=carrier,
            )
        n.add("Store", "AT11 gas Store", bus="AT11 gas", carrier="gas")
        n.stores_t.p["AT11 gas Store"] = [10.0, 10.0]
        assert fossil_gas_share(n) == pytest.approx(0.5)

    def test_no_supply_gives_zero(self):
        """D3: without gas supply f_gas is 0."""
        n = self._gas_network({"pipeline gas": 0.0}, {})
        assert fossil_gas_share(n) == 0.0

    def test_unknown_carrier_with_supply_raises(self):
        """D3: an unknown carrier with non-zero yearly supply raises ValueError naming it."""
        n = self._gas_network({"pipeline gas": 1.0, "shale gas": 1.0}, {})
        with pytest.raises(ValueError, match="shale gas"):
            fossil_gas_share(n)


class TestApplyDomesticShare:
    @staticmethod
    def _flows(values: dict[str, float]) -> pd.Series:
        """Return yearly flows indexed by location and unit."""
        return pd.Series(
            values.values(),
            index=pd.MultiIndex.from_tuples(
                [(loc, "MWh_LHV") for loc in values], names=["location", "unit"]
            ),
        )

    @pytest.fixture
    def totals(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "total domestic aviation": [30.0, 10.0, 0.0],
                "total international aviation": [70.0, 30.0, 0.0],
                "total domestic navigation": [20.0, 50.0, 0.0],
                "total international navigation": [80.0, 50.0, 0.0],
            },
            index=pd.Index(["AT", "DE", "LU"], name="country"),
        )

    def test_share_per_country(self, totals):
        """D4: each location is weighted with the share of its own country."""
        flows = self._flows({"AT11": 100.0, "AT12": 10.0, "DE1": 100.0})
        result = apply_domestic_share(flows, totals, "aviation")
        assert result.tolist() == pytest.approx([30.0, 3.0, 25.0])

    def test_navigation_columns(self, totals):
        """D4: kind navigation uses the navigation columns."""
        flows = self._flows({"DE1": 10.0})
        result = apply_domestic_share(flows, totals, "navigation")
        assert result.tolist() == pytest.approx([5.0])

    def test_zero_denominator_gives_zero(self, totals):
        """D4: a country with zero domestic and international demand gets d_k = 0."""
        flows = self._flows({"LU": 10.0})
        assert apply_domestic_share(flows, totals, "aviation").tolist() == [0.0]

    def test_missing_country_with_demand_raises(self, totals):
        """D4: a non-zero location whose country has no row raises ValueError naming it."""
        flows = self._flows({"AT11": 1.0, "CH": 1.0})
        with pytest.raises(ValueError, match="CH"):
            apply_domestic_share(flows, totals, "aviation")

    def test_zero_rows_need_no_lookup(self, totals):
        """D4: rows that are 0 (e.g. EU) stay 0 without a country row."""
        flows = self._flows({"AT11": 10.0, "EU": 0.0})
        result = apply_domestic_share(flows, totals, "aviation")
        assert result.tolist() == pytest.approx([3.0, 0.0])

    def test_time_series(self, totals):
        """D4: a time series is weighted per row in every snapshot column."""
        flows = pd.DataFrame(
            [[10.0, 20.0], [0.0, 0.0]],
            index=self._flows({"AT11": 0.0, "EU": 0.0}).index,
            columns=pd.date_range("2025-01-01", periods=2, freq="3h"),
        )
        result = apply_domestic_share(flows, totals, "aviation")
        assert isinstance(result, pd.DataFrame)
        assert result.to_numpy().ravel().tolist() == pytest.approx([3.0, 6.0, 0.0, 0.0])

    def test_missing_energy_totals_raises(self):
        """D4: energy_totals None raises ValueError."""
        with pytest.raises(ValueError, match="energy_totals"):
            apply_domestic_share(self._flows({"AT11": 1.0}), None, "aviation")

    def test_unknown_kind_raises(self, totals):
        """D4: a kind other than aviation or navigation raises ValueError."""
        with pytest.raises(ValueError, match="kind"):
            apply_domestic_share(self._flows({"AT11": 1.0}), totals, "rail")


class TestNonEnergyUse:
    @staticmethod
    def _demand(values: dict[str, float]) -> pd.Series:
        """Return yearly industry demand indexed by location and unit."""
        return pd.Series(
            values.values(),
            index=pd.MultiIndex.from_tuples(
                [(loc, "MWh_LHV") for loc in values], names=["location", "unit"]
            ),
        )

    @pytest.fixture
    def shares(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"non_energy_share": [0.1, 0.8, 0.2, 0.3, 0.6, 0.0]},
            index=pd.MultiIndex.from_tuples(
                [
                    ("AT", "Natural Gas"),
                    ("AT", "Oil"),
                    ("AT", "Coal"),
                    ("DE", "Natural Gas"),
                    ("DE", "Oil"),
                    ("DE", "Coal"),
                ],
                names=["country", "carrier"],
            ),
        )

    def test_share_of_country(self, shares):
        """D5: NE_x(l) is the share of the country of l times the demand at l."""
        demand = self._demand({"AT11": 100.0, "DE1": 100.0})
        result = non_energy_use(demand, shares, "Natural Gas")
        assert result.tolist() == pytest.approx([10.0, 30.0])

    def test_oil_and_coal_use_their_rows(self, shares):
        """D5: Oil and Coal use the shares of their own carrier."""
        demand = self._demand({"AT11": 10.0})
        assert non_energy_use(demand, shares, "Oil").tolist() == pytest.approx([8.0])
        assert non_energy_use(demand, shares, "Coal").tolist() == pytest.approx([2.0])

    def test_missing_country_uses_mean_with_warning(self, shares, caplog):
        """D5: a country without a row gets the mean of the carrier, with one WARNING."""
        demand = self._demand({"CH": 100.0, "CH1": 10.0})
        with caplog.at_level(logging.WARNING):
            result = non_energy_use(demand, shares, "Oil")
        assert result.tolist() == pytest.approx([70.0, 7.0])
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "CH" in warnings[0].getMessage() and "Oil" in warnings[0].getMessage()

    def test_copperplate_uses_mean_without_warning(self, shares, caplog):
        """D5: the copperplate EU gets the mean without a WARNING."""
        demand = self._demand({"AT11": 0.0, "EU": 10.0})
        with caplog.at_level(logging.WARNING):
            result = non_energy_use(demand, shares, "Natural Gas")
        assert result.tolist() == pytest.approx([0.0, 2.0])
        assert not caplog.records

    def test_h2_is_zero_with_warning(self, shares, caplog):
        """D5: NE_H2 is 0, with one WARNING per call."""
        demand = self._demand({"AT11": 10.0})
        with caplog.at_level(logging.WARNING):
            result = non_energy_use(demand, None, "H2")
        assert result.tolist() == [0.0]
        assert len(caplog.records) == 1 and "H2" in caplog.records[0].getMessage()

    def test_time_series_bounded_by_demand(self, shares):
        """D5: per snapshot 0 <= NE_x(l) <= demand(l)."""
        demand = pd.DataFrame(
            [[10.0, 0.0], [5.0, 20.0]],
            index=self._demand({"AT11": 0.0, "DE1": 0.0}).index,
            columns=pd.date_range("2025-01-01", periods=2, freq="3h"),
        )
        result = non_energy_use(demand, shares, "Oil")
        assert isinstance(result, pd.DataFrame)
        assert result.to_numpy().ravel().tolist() == pytest.approx(
            [8.0, 0.0, 3.0, 12.0]
        )
        assert ((result >= 0) & (result <= demand)).all().all()

    def test_share_outside_unit_interval_clipped_with_warning(self, caplog):
        """D5: a share outside [0, 1] is clipped, with one WARNING."""
        shares = pd.DataFrame(
            {"non_energy_share": [1.5, -0.2]},
            index=pd.MultiIndex.from_tuples(
                [("AT", "Oil"), ("DE", "Oil")], names=["country", "carrier"]
            ),
        )
        demand = self._demand({"AT11": 10.0, "DE1": 10.0})
        with caplog.at_level(logging.WARNING):
            result = non_energy_use(demand, shares, "Oil")
        assert result.tolist() == pytest.approx([10.0, 0.0])
        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "AT" in message and "DE" in message

    def test_missing_shares_raises(self):
        """D5: shares None for Natural Gas, Oil or Coal raises ValueError."""
        with pytest.raises(ValueError, match="industry_non_energy_shares"):
            non_energy_use(self._demand({"AT11": 1.0}), None, "Coal")

    def test_unknown_carrier_raises(self, shares):
        """D5: an unsupported carrier raises ValueError."""
        with pytest.raises(ValueError, match="carrier"):
            non_energy_use(self._demand({"AT11": 1.0}), shares, "Biomass")
