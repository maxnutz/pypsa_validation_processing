import pandas as pd

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import eval_helpers as eh
import pytest


class DummyNetwork:
    def __init__(self, name):
        self.name = name


def test_load_networks_uses_network_collection(monkeypatch, tmp_path):
    called = {}

    class FakeNetworkCollection(dict):
        def __init__(self, *args, **kwargs):
            called["args"] = args
            called["kwargs"] = kwargs
            super().__init__({
                "scenario-1": DummyNetwork("n1"),
                "scenario-2": DummyNetwork("n2"),
            })

    # Ensure load_networks uses NetworkCollection when it succeeds
    monkeypatch.setattr(eh.pypsa, "NetworkCollection", FakeNetworkCollection, raising=True)

    networks = eh.load_networks(tmp_path)

    assert set(networks.keys()) == {"scenario-1", "scenario-2"}
    assert isinstance(networks["scenario-1"], DummyNetwork)
    assert isinstance(networks["scenario-2"], DummyNetwork)
    # Sanity check that NetworkCollection was constructed
    assert "args" in called


def test_load_networks_falls_back_to_single_network(monkeypatch, tmp_path):
    class Boom(Exception):
        pass

    # Simulate NetworkCollection failing
    def failing_network_collection(*args, **kwargs):
        raise Boom("NetworkCollection failed")

    created = {}

    # Fallback Network loader
    def fake_network(path):
        created["path"] = path
        return DummyNetwork("fallback")

    monkeypatch.setattr(eh.pypsa, "NetworkCollection", failing_network_collection, raising=True)
    monkeypatch.setattr(eh.pypsa, "Network", fake_network, raising=True)

    networks = eh.load_networks(tmp_path)

    # Expect a mapping with a single entry pointing to the fallback network
    assert isinstance(networks, dict)
    assert len(networks) == 1
    (key, net), = networks.items()
    assert isinstance(net, DummyNetwork)
    # Ensure the fallback Network was actually called with some path
    assert created["path"] is not None


class DummyStatistics:
    def __init__(self, prices_result, capacity_result):
        self._prices_result = prices_result
        self._capacity_result = capacity_result

    def prices(self, **kwargs):
        if isinstance(self._prices_result, Exception):
            raise self._prices_result
        return self._prices_result

    def installed_capacity(self, **kwargs):
        if isinstance(self._capacity_result, Exception):
            raise self._capacity_result
        return self._capacity_result


class DummyBusesT:
    def __init__(self, marginal_price: pd.DataFrame):
        self.marginal_price = marginal_price


class DummyNetwork:
    def __init__(
        self,
        buses: pd.DataFrame,
        marginal_price: pd.DataFrame,
        generators: pd.DataFrame | None = None,
        links: pd.DataFrame | None = None,
        prices_result=None,
        capacity_result=None,
    ):
        self.buses = buses
        self.buses_t = DummyBusesT(marginal_price)
        self.generators = generators if generators is not None else pd.DataFrame()
        self.links = links if links is not None else pd.DataFrame()
        self.statistics = DummyStatistics(prices_result, capacity_result)


def test_prices_by_bus_carrier_manual_fallback_filters_to_at():
    buses = pd.DataFrame(
        {"carrier": ["AC", "AC", "low voltage"]},
        index=["AT1 AC", "DE1 AC", "AT1 LV"],
    )
    marginal_price = pd.DataFrame(
        {
            "AT1 AC": [100.0, 120.0],
            "DE1 AC": [10.0, 15.0],
            "AT1 LV": [200.0, 220.0],
        }
    )
    n = DummyNetwork(
        buses=buses,
        marginal_price=marginal_price,
        prices_result=RuntimeError("statistics.prices failed"),
        capacity_result=pd.Series(dtype=float),
    )

    result = eh.prices_by_bus_carrier(
        n,
        bus_carriers=["AC", "low voltage"],
        country_prefix="AT",
    )

    expected = pd.Series({"AC": 110.0, "low voltage": 210.0})
    pd.testing.assert_series_equal(result, expected)


def test_installed_capacity_by_carrier_manual_fallback_uses_p_nom_opt_in_gw():
    buses = pd.DataFrame(
        {"carrier": ["AC", "AC", "urban central heat"]},
        index=["AT1 AC", "DE1 AC", "AT1 heat"],
    )
    marginal_price = pd.DataFrame(index=[0], columns=buses.index, data=0.0)
    generators = pd.DataFrame(
        {
            "carrier": ["solar", "solar", "onwind"],
            "bus": ["AT1 AC", "DE1 AC", "AT1 AC"],
            "p_nom_opt": [2000.0, 5000.0, 3000.0],
        },
        index=["g_at", "g_de", "w_at"],
    )

    n = DummyNetwork(
        buses=buses,
        marginal_price=marginal_price,
        generators=generators,
        prices_result=pd.Series(dtype=float),
        capacity_result=pd.Series(dtype=float),
    )

    result = eh.installed_capacity_by_carrier(
        n,
        components=["Generator"],
        carriers=["solar", "onwind"],
        bus_carriers=["AC"],
        country_prefix="AT",
    )

    expected = pd.Series({"solar": 2.0, "onwind": 3.0})
    pd.testing.assert_series_equal(result, expected)


def test_compare_installed_capacity_shapes_rows_and_columns():
    buses = pd.DataFrame(
        {"carrier": ["AC", "AC"]},
        index=["AT1 AC", "AT2 AC"],
    )
    marginal_price = pd.DataFrame(index=[0], columns=buses.index, data=0.0)

    n1 = DummyNetwork(
        buses=buses,
        marginal_price=marginal_price,
        generators=pd.DataFrame(
            {
                "carrier": ["solar"],
                "bus": ["AT1 AC"],
                "p_nom_opt": [1000.0],
            }
        ),
        prices_result=pd.Series(dtype=float),
        capacity_result=pd.Series(dtype=float),
    )
    n2 = DummyNetwork(
        buses=buses,
        marginal_price=marginal_price,
        generators=pd.DataFrame(
            {
                "carrier": ["onwind"],
                "bus": ["AT2 AC"],
                "p_nom_opt": [2000.0],
            }
        ),
        prices_result=pd.Series(dtype=float),
        capacity_result=pd.Series(dtype=float),
    )

    df = eh.compare_installed_capacity(
        networks={"s1": n1, "s2": n2},
        components=["Generator"],
        carriers=["solar", "onwind", "hydro"],
        bus_carriers=["AC"],
        country_prefix="AT",
    )

    assert list(df.columns) == ["s1", "s2"]
    assert list(df.index) == ["solar", "onwind"]
    assert df.loc["solar", "s1"] == 1.0
    assert pd.isna(df.loc["solar", "s2"])
    assert df.loc["onwind", "s2"] == 2.0
