"""Helper functions for scenario comparison evaluations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd
import plotly.express as px
import pypsa

PRICE_CATEGORIES: dict[str, list[str]] = {
    "Electricity": ["AC", "low voltage"],
    "Heat": [
        "urban central heat",
        "urban central water tanks",
        "urban central water pits",
        "rural heat",
        "rural water tanks",
        "urban decentral water tanks",
    ],
    "H2": ["H2"],
    "Fossils": ["coal", "oil", "gas", "biogas"],
    "Industry demand": [
        "solid biomass for industry",
        "gas for industry",
        "industry methanol",
        "naphtha for industry",
    ],
}

ELECTRICITY_GENERATOR_CARRIERS: list[str] = [
    "onwind",
    "solar",
    "solar-rooftop",
    "solar-hsat",
    "ror",
    "hydro",
    "solid biomass",
]

HEAT_GENERATOR_CARRIERS: list[str] = [
    "urban central heat vent",
    "urban central solar thermal",
    "rural heat vent",
    "rural solar thermal",
]

HEAT_LINK_CARRIERS: list[str] = [
    "H2 Electrolysis",
    "H2 Fuel Cell",
    "urban central air heat pump",
    "urban central resistive heater",
    "urban central gas boiler",
    "urban central gas CHP",
    "urban central gas CHP CC",
    "urban central solid biomass CHP",
    "urban central solid biomass CHP CC",
    "waste CHP",
    "waste CHP CC",
    "DAC",
    "rural air heat pump",
    "rural biomass boiler",
    "rural gas boiler",
    "rural ground heat pump",
    "rural resistive heater",
    "urban central coal CHP",
    "urban central H2 CHP",
    "urban central H2 retrofit CHP",
]

HEAT_BUS_CARRIERS: list[str] = [
    "urban central heat",
    "urban central water tanks",
    "urban central water pits",
    "rural heat",
    "rural water tanks",
    "urban decentral water tanks",
]

ELECTRICITY_BUS_CARRIERS: list[str] = ["AC", "low voltage"]


def load_networks(input_dict: Mapping[str, str]) -> dict[str, pypsa.Network]:
    """Load networks for all scenarios.

    Parameters
    ----------
    input_dict : Mapping[str, str]
        Mapping of scenario labels to network paths.

    Returns
    -------
    dict[str, pypsa.Network]
        Mapping of scenario labels to loaded PyPSA networks.
    """
    labels = list(input_dict.keys())
    paths = list(input_dict.values())

    try:
        collection = pypsa.NetworkCollection(paths, index=labels)
        return {
            label: network for label, network in zip(labels, collection, strict=True)
        }
    except Exception:
        return {label: pypsa.Network(path) for label, path in input_dict.items()}


def _extract_bus_level(index: pd.Index, buses: pd.Index) -> pd.Index:
    if isinstance(index, pd.MultiIndex):
        for level in range(index.nlevels):
            values = index.get_level_values(level)
            if values.isin(buses).any():
                return values
        return pd.Index([], dtype=str)
    return pd.Index(index)


def _series_from_statistics_output(result: pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(result, pd.Series):
        return result
    if result.empty:
        return pd.Series(dtype=float)
    if result.shape[1] == 1:
        return result.iloc[:, 0]
    return result.mean(axis=1)


def _manual_price_extraction(
    n: pypsa.Network,
    bus_carriers: Sequence[str],
    country_prefix: str,
) -> pd.Series:
    if not hasattr(n, "buses_t") or not hasattr(n.buses_t, "marginal_price"):
        return pd.Series(dtype=float)

    prices = n.buses_t.marginal_price
    if prices.empty:
        return pd.Series(dtype=float)

    valid_buses = n.buses.index[n.buses.index.str.startswith(country_prefix)]
    valid_buses = valid_buses.intersection(prices.columns)
    if valid_buses.empty:
        return pd.Series(dtype=float)

    bus_to_carrier = n.buses.loc[valid_buses, "carrier"]
    data: dict[str, float] = {}
    for carrier in bus_carriers:
        carrier_buses = bus_to_carrier.index[bus_to_carrier == carrier]
        if len(carrier_buses) == 0:
            continue
        value = prices.loc[:, carrier_buses].stack().mean()
        if pd.notna(value):
            data[carrier] = float(value)

    return pd.Series(data, dtype=float)


def prices_by_bus_carrier(
    n: pypsa.Network,
    bus_carriers: Sequence[str],
    country_prefix: str = "AT",
) -> pd.Series:
    """Calculate average marginal prices by bus carrier for one scenario.

    Parameters
    ----------
    n : pypsa.Network
        Scenario network.
    bus_carriers : Sequence[str]
        Bus carriers to include.
    country_prefix : str, default "AT"
        Prefix for bus filtering.

    Returns
    -------
    pd.Series
        Prices by bus carrier in EUR/MWh-equivalent unit.
    """
    try:
        result = n.statistics.prices(
            groupby=False,
            groupby_time=True,
            bus_carrier=list(bus_carriers),
            drop_zero=False,
        )
        series = _series_from_statistics_output(result)
        if series.empty:
            return _manual_price_extraction(n, bus_carriers, country_prefix)

        buses = _extract_bus_level(series.index, n.buses.index)
        if buses.empty:
            return _manual_price_extraction(n, bus_carriers, country_prefix)

        mask = buses.str.startswith(country_prefix)
        if not mask.any():
            return pd.Series(dtype=float)

        filtered = series.loc[mask]
        filtered_buses = buses[mask]
        bus_to_carrier = n.buses.loc[filtered_buses, "carrier"]

        grouped = filtered.groupby(bus_to_carrier.values).mean()
        grouped = grouped[grouped.index.isin(bus_carriers)]
        grouped = grouped.reindex([c for c in bus_carriers if c in grouped.index])
        return grouped.dropna()
    except Exception:
        print("WARNING: Price extraction failed, falling back to manual method.")
        return _manual_price_extraction(n, bus_carriers, country_prefix)


def _manual_capacity_extraction(
    n: pypsa.Network,
    components: Sequence[str],
    carriers: Sequence[str],
    bus_carriers: Sequence[str],
    country_prefix: str,
) -> pd.Series:
    component_tables = {
        "Generator": "generators",
        "Link": "links",
    }
    result: dict[str, float] = {}

    for component in components:
        table_name = component_tables.get(component)
        if table_name is None or not hasattr(n, table_name):
            continue

        df = getattr(n, table_name)
        if df.empty:
            continue

        working = df.copy()
        if "carrier" not in working:
            continue

        working = working[working["carrier"].isin(carriers)]
        if working.empty:
            continue

        bus_cols = [c for c in working.columns if c.startswith("bus")]
        if not bus_cols:
            continue

        def keep_row(row: pd.Series) -> bool:
            for col in bus_cols:
                bus = row[col]
                if not isinstance(bus, str) or bus not in n.buses.index:
                    continue
                if not bus.startswith(country_prefix):
                    continue
                if n.buses.at[bus, "carrier"] in bus_carriers:
                    return True
            return False

        working = working[working.apply(keep_row, axis=1)]
        if working.empty:
            continue

        capacity_col = "p_nom_opt" if "p_nom_opt" in working.columns else "p_nom"
        grouped = working.groupby("carrier")[capacity_col].sum() / 1000.0
        grouped = grouped[grouped != 0.0]

        for carrier, value in grouped.items():
            result[carrier] = result.get(carrier, 0.0) + float(value)

    series = pd.Series(result, dtype=float)
    series = series.reindex([c for c in carriers if c in series.index])
    return series.dropna()


def installed_capacity_by_carrier(
    n: pypsa.Network,
    components: Sequence[str],
    carriers: Sequence[str],
    bus_carriers: Sequence[str],
    country_prefix: str = "AT",
) -> pd.Series:
    """Calculate installed capacities by carrier for one scenario in GW.

    Parameters
    ----------
    n : pypsa.Network
        Scenario network.
    components : Sequence[str]
        Components to include (e.g. Generator, Link).
    carriers : Sequence[str]
        Carriers to include.
    bus_carriers : Sequence[str]
        Bus carriers used as filter.
    country_prefix : str, default "AT"
        Prefix for bus filtering.

    Returns
    -------
    pd.Series
        Installed capacities by carrier in GW.
    """
    try:
        frames: list[pd.Series] = []
        for component in components:
            result = n.statistics.installed_capacity(
                components=[component],
                groupby=["carrier", "bus"],
                at_port="all",
                carrier=list(carriers),
                bus_carrier=list(bus_carriers),
                drop_zero=False,
            )
            series = _series_from_statistics_output(result)
            if series.empty:
                continue

            if not isinstance(series.index, pd.MultiIndex) or series.index.nlevels < 2:
                continue

            carrier_level = series.index.get_level_values(-2)
            bus_level = series.index.get_level_values(-1)
            mask = bus_level.astype(str).str.startswith(country_prefix)
            if not mask.any():
                continue

            grouped = series.loc[mask].groupby(carrier_level[mask]).sum() / 1000.0
            grouped = grouped[grouped != 0.0]
            frames.append(grouped)

        if frames:
            combined = pd.concat(frames, axis=1).sum(axis=1)
            combined = combined.reindex([c for c in carriers if c in combined.index])
            combined = combined.dropna()
            if not combined.empty:
                return combined
    except Exception:
        print("WARNING: Capacity extraction failed.")
        pass

    return _manual_capacity_extraction(
        n=n,
        components=components,
        carriers=carriers,
        bus_carriers=bus_carriers,
        country_prefix=country_prefix,
    )


def compare_prices(
    networks: Mapping[str, pypsa.Network],
    bus_carriers: Sequence[str],
    country_prefix: str = "AT",
) -> pd.DataFrame:
    """Compare prices across scenarios.

    Parameters
    ----------
    networks : Mapping[str, pypsa.Network]
        Scenario label to network mapping.
    bus_carriers : Sequence[str]
        Bus carriers to include.
    country_prefix : str, default "AT"
        Prefix for bus filtering.

    Returns
    -------
    pd.DataFrame
        Rows are bus carriers and columns are scenarios.
    """
    out = {
        scenario: prices_by_bus_carrier(network, bus_carriers, country_prefix)
        for scenario, network in networks.items()
    }
    df = pd.DataFrame(out)
    if not df.empty:
        df = df.reindex([c for c in bus_carriers if c in df.index])
        df = df.dropna(how="all")
    return df


def compare_installed_capacity(
    networks: Mapping[str, pypsa.Network],
    components: Sequence[str],
    carriers: Sequence[str],
    bus_carriers: Sequence[str],
    country_prefix: str = "AT",
) -> pd.DataFrame:
    """Compare installed capacities across scenarios.

    Parameters
    ----------
    networks : Mapping[str, pypsa.Network]
        Scenario label to network mapping.
    components : Sequence[str]
        Components to include.
    carriers : Sequence[str]
        Carrier labels for rows.
    bus_carriers : Sequence[str]
        Bus carriers used as filter.
    country_prefix : str, default "AT"
        Prefix for bus filtering.

    Returns
    -------
    pd.DataFrame
        Rows are carriers and columns are scenarios.
    """
    out = {
        scenario: installed_capacity_by_carrier(
            network,
            components=components,
            carriers=carriers,
            bus_carriers=bus_carriers,
            country_prefix=country_prefix,
        )
        for scenario, network in networks.items()
    }
    df = pd.DataFrame(out)
    if not df.empty:
        df = df.reindex([c for c in carriers if c in df.index])
        df = df.dropna(how="all")
    return df


def plot_grouped_bars(df: pd.DataFrame, title: str, y_axis_title: str):
    """Create a grouped Plotly bar chart from a scenario comparison dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Rows as categories and columns as scenarios.
    title : str
        Plot title.
    y_axis_title : str
        Label for y-axis.

    Returns
    -------
    plotly.graph_objects.Figure
        Grouped bar chart.
    """
    if df.empty:
        return px.bar(title=title)

    tidy = df.reset_index(names="category").melt(
        id_vars="category",
        var_name="scenario",
        value_name="value",
    )
    fig = px.bar(
        tidy,
        x="category",
        y="value",
        color="scenario",
        barmode="group",
        title=title,
    )
    fig.update_layout(xaxis_title="Carrier", yaxis_title=y_axis_title)
    return fig
