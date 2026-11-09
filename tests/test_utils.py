"""Tests for pypsa_validation_processing.utils."""

import logging

import pandas as pd
import pypsa
import pytest

from pypsa_validation_processing.utils import (
    REGION_MAPPING,
    UNITS_MAPPING,
    apply_coke_correction,
    apply_domestic_share,
    attribute_locations,
    decentral_heat_split,
    ensure_all_locations,
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


class TestApplyCokeCorrection:
    def test_fallback_is_identity_with_warning(self, caplog):
        """D6: without kappa the Eurostat fallback kappa = 0 applies, with one WARNING."""
        coal = pd.Series([10.0, 0.0], index=pd.Index(["AT11", "EU"], name="location"))
        with caplog.at_level(logging.WARNING):
            result = apply_coke_correction(coal)
        assert result.tolist() == [10.0, 0.0]
        assert len(caplog.records) == 1 and "D6" in caplog.records[0].getMessage()

    def test_kappa_converts_coke_part(self):
        """D6: the coke part kappa is divided by 1.366."""
        coal = pd.Series([13.66], index=pd.Index(["AT11"], name="location"))
        result = apply_coke_correction(coal, kappa=0.5)
        assert result.tolist() == pytest.approx([6.83 + 5.0])

    def test_kappa_out_of_range_raises(self):
        """D6: kappa outside [0, 1] raises ValueError."""
        coal = pd.Series([1.0], index=pd.Index(["AT11"], name="location"))
        with pytest.raises(ValueError, match="kappa"):
            apply_coke_correction(coal, kappa=1.5)


class TestLandTransportUnit:
    def test_land_transport_maps_to_mwh(self):
        """D7: the bus unit label land transport is a permanent UNITS_MAPPING key for MWh."""
        assert UNITS_MAPPING["land transport"] == "MWh"


class TestDecentralHeatSplit:
    @staticmethod
    def _link(n: pypsa.Network, name: str, p: dict[int, float], **attrs) -> None:
        """Add a Link with constant dispatch p[i] (MW, positive = withdrawal) at port i."""
        n.add("Link", name, **attrs)
        for port, value in p.items():
            n.links_t[f"p{port}"][name] = [value, value]

    @staticmethod
    def _load(n: pypsa.Network, name: str, bus: str, p: float) -> None:
        """Add a Load with constant withdrawal p (MW)."""
        n.add("Load", name, bus=bus, carrier=name.split(" ", 1)[1])
        n.loads_t.p[name] = [p, p]

    @pytest.fixture
    def network(self) -> pypsa.Network:
        n = _network(["AT11", "DE1"])
        n.buses["unit"] = "MWh_th"
        n.add(
            "Bus",
            "AT11 urban decentral heat",
            carrier="urban decentral heat",
            location="AT11",
            unit="MWh_th",
        )
        n.add("Bus", "AT11 water tanks", carrier="rural water tanks", location="AT11")
        for bus, carrier, location, unit in [
            ("AT11 gas", "gas", "AT11", "MWh_LHV"),
            ("DE1 gas", "gas", "DE1", "MWh_LHV"),
            ("EU oil", "oil", "EU", "MWh_LHV"),
            ("AT11 low voltage", "low voltage", "AT11", "MWh_el"),
            ("AT11", "AC", "AT11", "MWh_el"),
            ("AT11 biogas", "biogas", "AT11", "MWh_LHV"),
            ("co2 atmosphere", "co2", "EU", "t_co2"),
        ]:
            n.add("Bus", bus, carrier=carrier, location=location, unit=unit)
        heat = "AT11 rural heat"
        self._link(
            n,
            "AT11 rural gas boiler",
            {0: 3.0, 1: -2.7, 2: -0.6},
            bus0="AT11 gas",
            bus1=heat,
            bus2="co2 atmosphere",
            carrier="rural gas boiler",
        )
        self._link(
            n,
            "AT11 rural oil boiler",
            {0: 1.5, 1: -1.4},
            bus0="EU oil",
            bus1=heat,
            carrier="rural oil boiler",
        )
        self._link(
            n,
            "AT11 rural air heat pump",
            {0: -3.0, 1: 1.0},
            bus0=heat,
            bus1="AT11 low voltage",
            carrier="rural air heat pump",
        )
        self._link(
            n,
            "AT11 biogas CHP",
            {0: 2.0, 1: -0.8, 2: -0.9},
            bus0="AT11 biogas",
            bus1="AT11",
            bus2=heat,
            carrier="biogas CHP",
        )
        self._link(
            n,
            "AT11 rural water tanks charger",
            {0: 0.5, 1: -0.5},
            bus0=heat,
            bus1="AT11 water tanks",
            carrier="rural water tanks charger",
        )
        self._link(
            n,
            "AT11 rural water tanks discharger",
            {0: 0.5, 1: -0.5},
            bus0="AT11 water tanks",
            bus1=heat,
            carrier="rural water tanks discharger",
        )
        self._link(
            n,
            "DE1 rural gas boiler",
            {0: 1.0, 1: -0.9},
            bus0="DE1 gas",
            bus1="DE1 rural heat",
            carrier="rural gas boiler",
        )
        self._link(
            n,
            "AT11 urban decentral resistive heater",
            {0: 4.0, 1: -4.0},
            bus0="AT11 low voltage",
            bus1="AT11 urban decentral heat",
            carrier="urban decentral resistive heater",
        )
        self._link(
            n,
            "AT11 DAC",
            {0: 1.0, 1: 0.0},
            bus0="AT11 urban decentral heat",
            bus1="co2 atmosphere",
            carrier="DAC",
        )
        for name, p in [
            ("AT11 rural solar thermal", 0.6),
            ("AT11 rural heat vent", -0.3),
        ]:
            n.add("Generator", name, bus=heat, carrier=name.split(" ", 1)[1])
            n.generators_t.p[name] = [p, p]
        self._load(n, "AT11 rural heat", heat, 2.0)
        self._load(n, "AT11 agriculture heat", heat, 1.0)
        self._load(n, "AT11 urban decentral heat", "AT11 urban decentral heat", 2.0)
        self._load(
            n,
            "AT11 low-temperature heat for industry",
            "AT11 urban decentral heat",
            1.0,
        )
        return n

    def test_rural_input_split_by_demand(self, network):
        """D8: rural heat input (incl. D1, solar, CHP heat) is split 2:1 between rc and agr."""
        result = decentral_heat_split(network)
        rural = result.xs("AT11", level="location").drop(
            "urban decentral heat", level="carrier", errors="ignore"
        )
        rc = rural.xs("rc", level="sector").droplevel("unit")
        assert rc.drop("low voltage").to_dict() == pytest.approx(
            {"gas": 12.0, "oil": 6.0, "rural heat": 6.0}
        )
        assert rural.xs("agr", level="sector").sum() == pytest.approx(42.0 / 3)

    def test_excluded_flows(self, network):
        """D8: CO2 output, CHP fuel and electricity, storage and heat vent are not input."""
        result = decentral_heat_split(network)
        carriers = set(result.index.get_level_values("carrier"))
        assert carriers == {"gas", "oil", "low voltage", "rural heat"}

    def test_urban_decentral_other_demand(self, network):
        """D8: DAC is other demand; the input is split rc 1/2, ind 1/4, other 1/4."""
        result = decentral_heat_split(network).xs("AT11", level="location")
        lv = result.xs("low voltage", level="carrier").droplevel("unit")
        # urban: 24 MWh resistive heater; rural: 6 MWh heat pump split 2:1
        assert lv.to_dict() == pytest.approx(
            {"rc": 12.0 + 4.0, "agr": 2.0, "ind": 6.0, "other": 6.0}
        )

    def test_consistency_per_location(self, network):
        """D8: the sector values sum to the total input at a location with demand."""
        result = decentral_heat_split(network).xs("AT11", level="location")
        assert result.sum() == pytest.approx(18.0 + 9.0 + 6.0 + 9.0 + 24.0)

    def test_location_without_demand_gets_zero(self, network):
        """D8: a location without heat demand has shares 0."""
        result = decentral_heat_split(network).xs("DE1", level="location")
        assert result.abs().sum() == 0.0

    def test_units_are_normalised(self, network):
        """D8: all units are normalised to MWh (C6.5)."""
        result = decentral_heat_split(network)
        assert set(result.index.get_level_values("unit")) == {"MWh"}

    def test_time_series_matches_year(self, network):
        """D8: snapshot values weighted over the year equal the yearly values."""
        yearly = decentral_heat_split(network)
        series = decentral_heat_split(network, aggregate_per_year=False)
        assert isinstance(series, pd.DataFrame)
        assert list(series.columns) == list(network.snapshots)
        weighted = series.mul(network.snapshot_weightings.generators, axis=1)
        pd.testing.assert_series_equal(weighted.sum(axis=1), yearly, check_names=False)

    def test_generator_only_supply(self):
        """D8: a heat bus supplied only by solar thermal gives the solar heat as input."""
        n = _network(["AT11"])
        n.buses["unit"] = "MWh_th"
        n.add(
            "Generator",
            "AT11 rural solar thermal",
            bus="AT11 rural heat",
            carrier="rural solar thermal",
        )
        n.generators_t.p["AT11 rural solar thermal"] = [1.0, 1.0]
        self._load(n, "AT11 rural heat", "AT11 rural heat", 1.0)
        result = decentral_heat_split(n)
        assert result.xs("rc", level="sector").sum() == pytest.approx(6.0)

    def test_heat_bus_without_supply(self):
        """D8: a decentral heat bus without supplying Link or Generator gives an empty result."""
        n = _network(["AT11"])
        n.buses["unit"] = "MWh_th"
        self._load(n, "AT11 rural heat", "AT11 rural heat", 1.0)
        assert decentral_heat_split(n).empty
        assert decentral_heat_split(n, aggregate_per_year=False).empty

    def test_generator_and_link_with_same_name(self):
        """D8: a Generator is input even if a converter Link has the same name."""
        n = _network(["AT11"])
        n.buses["unit"] = "MWh_th"
        n.add("Bus", "AT11 gas", carrier="gas", location="AT11", unit="MWh_LHV")
        name = "AT11 rural heat supply"
        self._link(
            n,
            name,
            {0: 1.0, 1: -1.0},
            bus0="AT11 gas",
            bus1="AT11 rural heat",
            carrier="rural gas boiler",
        )
        n.add("Generator", name, bus="AT11 rural heat", carrier="rural solar thermal")
        n.generators_t.p[name] = [1.0, 1.0]
        self._load(n, "AT11 rural heat", "AT11 rural heat", 2.0)
        result = decentral_heat_split(n).xs("rc", level="sector")
        assert result.droplevel(["location", "unit"]).to_dict() == pytest.approx(
            {"gas": 6.0, "rural heat": 6.0}
        )

    def test_storage_unit_is_no_demand(self):
        """D8.2: a StorageUnit charging from a heat bus is no (other) demand."""
        n = _network(["AT11"])
        n.buses["unit"] = "MWh_th"
        n.add(
            "Generator",
            "AT11 rural solar thermal",
            bus="AT11 rural heat",
            carrier="rural solar thermal",
        )
        n.generators_t.p["AT11 rural solar thermal"] = [2.0, 2.0]
        n.add("StorageUnit", "AT11 rural heat storage", bus="AT11 rural heat")
        n.storage_units_t.p["AT11 rural heat storage"] = [-1.0, -1.0]
        n.storage_units_t.p_store["AT11 rural heat storage"] = [1.0, 1.0]
        n.storage_units_t.p_dispatch["AT11 rural heat storage"] = [0.0, 0.0]
        self._load(n, "AT11 rural heat", "AT11 rural heat", 1.0)
        result = decentral_heat_split(n)
        assert result.xs("rc", level="sector").sum() == pytest.approx(12.0)
        assert result.xs("other", level="sector").sum() == pytest.approx(0.0)

    def test_network_without_decentral_heat(self):
        """D8: a network without decentral heat buses gives an empty result."""
        n = pypsa.Network()
        n.set_snapshots(pd.date_range("2025-01-01", periods=2, freq="3h"))
        assert decentral_heat_split(n).empty
        assert decentral_heat_split(n, aggregate_per_year=False).empty


class TestEnsureAllLocations:
    """Tests for ensure_all_locations (C6.13)."""

    @staticmethod
    def _index(locations: list[str], unit: str = "MWh_el") -> pd.MultiIndex:
        """Return a (location, unit) MultiIndex with one *unit* for all rows."""
        return pd.MultiIndex.from_arrays(
            [locations, [unit] * len(locations)], names=["location", "unit"]
        )

    def test_adds_missing_locations_series(self):
        """Series: missing locations get 0.0; buses without location are ignored."""
        n = _network(["AT1", "AT2", "EU"])
        n.add("Bus", "no location", carrier="AC")
        result = pd.Series([5.0], index=self._index(["AT1"]))

        out = ensure_all_locations(result, n, unit="MWh", aggregate_per_year=True)

        assert isinstance(out, pd.Series)
        assert out[("AT1", "MWh_el")] == 5.0
        assert out[("AT2", "MWh")] == 0.0
        assert out[("EU", "MWh")] == 0.0
        assert len(out) == 3

    def test_adds_missing_locations_dataframe(self):
        """DataFrame: missing locations get 0.0 in every snapshot column."""
        n = _network(["AT1", "AT2"])
        result = pd.DataFrame(
            [[1.0, 2.0]], index=self._index(["AT1"]), columns=n.snapshots
        )

        out = ensure_all_locations(result, n, unit="MWh", aggregate_per_year=False)

        assert isinstance(out, pd.DataFrame)
        assert list(out.columns) == list(n.snapshots)
        assert (out.loc[("AT2", "MWh")] == 0.0).all()

    @pytest.mark.parametrize("aggregate_per_year", [True, False])
    def test_empty_result_gives_every_location(self, aggregate_per_year):
        """An empty result becomes all-zero rows for every location, in both modes."""
        n = _network(["AT1", "AT2"])

        out = ensure_all_locations(
            pd.Series(dtype=float), n, unit="MWh", aggregate_per_year=aggregate_per_year
        )

        expected_type = pd.Series if aggregate_per_year else pd.DataFrame
        assert isinstance(out, expected_type)
        assert set(out.index) == {("AT1", "MWh"), ("AT2", "MWh")}
        assert (out == 0.0).all(axis=None)

    def test_complete_result_is_unchanged(self):
        """A result already covering all locations is returned unchanged."""
        n = _network(["AT1"])
        result = pd.Series([0.0], index=self._index(["AT1"]))

        out = ensure_all_locations(result, n, unit="MWh", aggregate_per_year=True)

        pd.testing.assert_series_equal(out, result)

    def test_missing_index_level_raises(self):
        """A result without a ``unit`` level raises a ValueError (C6.1)."""
        n = _network(["AT1"])
        index = pd.MultiIndex.from_tuples(
            [("Link", "AT1")], names=["component", "location"]
        )

        with pytest.raises(ValueError, match="Index levels"):
            ensure_all_locations(
                pd.Series([1.0], index=index), n, unit="MWh", aggregate_per_year=True
            )

    def test_extra_index_levels_are_kept(self):
        """Extra levels are allowed (C6.3); added rows get NaN there."""
        n = _network(["AT1", "AT2"])
        index = pd.MultiIndex.from_tuples(
            [("Link", "AT1", "MWh_el")], names=["component", "location", "unit"]
        )

        out = ensure_all_locations(
            pd.Series([1.0], index=index), n, unit="MWh", aggregate_per_year=True
        )

        assert list(out.index.names) == ["component", "location", "unit"]
        added = out.xs("AT2", level="location")
        assert len(added) == 1 and (added == 0.0).all()
        assert added.index.get_level_values("component").isna().all()

    def test_quantity_level_adds_value_and_weight(self):
        """Intensive results get a ``value`` and a ``weight`` row (C6.12, C6.13)."""
        n = _network(["AT1", "AT2"])
        index = pd.MultiIndex.from_tuples(
            [("AT1", "EUR/MWh", "value"), ("AT1", "MWh_el", "weight")],
            names=["location", "unit", "quantity"],
        )

        out = ensure_all_locations(
            pd.Series([50.0, 2.0], index=index),
            n,
            unit="EUR/MWh",
            aggregate_per_year=True,
        )

        added = out.xs("AT2", level="location")
        assert set(added.index.get_level_values("quantity")) == {"value", "weight"}
        assert (added == 0.0).all()
