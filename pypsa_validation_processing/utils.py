"""Static information and general utility functions for pypsa_validation_processing."""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
import pypsa
from pathlib import Path

EU27_COUNTRY_CODES: dict[str, str] = {
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GB0": "United Kingdom Great Britain",
    "GB1": "United Kingdom Northern Ireland",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "XK": "Kosovo",
    "EU": "European Union",
}

COUNTRIES_SPECIAL_CASES: dict[str, str] = {
    "DE1": "Germany South-West",
    "DE2": "Germany South-East",
    "DE3": "Germany West",
    "DE4": "Germany East",
    "DE5": "Germany North",
    "DK0": "Denmark West",
    "DK1": "Denmark East",
    "ES0": "Spain Mainland",
    "ES1": "Spain Mallorca",
    "FR0": "France Mainland",
    "FR1": "France Corsica",
    "IT0": "Italy Mainland",
    "IT1": "Italy Sicily",
    "IT2": "Italy Sardinia",
}


NUTS_2_REGIONS: dict[str, str] = {
    "AT11": "Burgenland",
    "AT12": "Lower Austria",
    "AT13": "Vienna",
    "AT21": "Carinthia",
    "AT22": "Styria",
    "AT31": "Upper Austria",
    "AT32": "Salzburg",
    "AT33": "Tyrol",
    "AT333": "East Tyrol",
    "AT34": "Vorarlberg",
}

NUTS_3_REGIONS: dict[str, str] = {
    "AT111": "Mittelburgenland",
    "AT112": "Nordburgenland",
    "AT113": "Südburgenland",
    "AT121": "Mostviertel-Eisenwurzen",
    "AT122": "Niederösterreich-Süd",
    "AT123": "Sankt Pölten",
    "AT124": "Waldviertel",
    "AT125": "Weinviertel",
    "AT126": "Wiener Umland/Nordteil",
    "AT127": "Wiener Umland/Südteil",
    "AT130": "Wien",
    "AT211": "Klagenfurt-Villach",
    "AT212": "Oberkärnten",
    "AT213": "Unterkärnten",
    "AT221": "Graz",
    "AT222": "Liezen",
    "AT223": "Östliche Obersteiermark",
    "AT224": "Oststeiermark",
    "AT225": "West- und Südsteiermark",
    "AT226": "Westliche Obersteiermark",
    "AT311": "Innviertel",
    "AT312": "Linz-Wels",
    "AT313": "Mühlviertel",
    "AT314": "Steyr-Kirchdorf",
    "AT315": "Traunviertel",
    "AT321": "Lungau",
    "AT322": "Pinzgau-Pongau",
    "AT323": "Salzburg und Umgebung",
    "AT331": "Außerfern",
    "AT332": "Innsbruck",
    "AT333": "Osttirol",
    "AT334": "Tiroler Oberland",
    "AT335": "Tiroler Unterland",
    "AT341": "Bludenz-Bregenzer Wald",
    "AT342": "Rheintal-Bodenseegebiet",
    "ATXXX": "Not regionalised/Unknown NUTS 3",
    "ATZZZ": "Extra-Regio NUTS 3",
}
# NUTS 3 overwrites NUTS2, relevant because of language change of East Tyrol -> Osttirol
REGION_MAPPING = (
    EU27_COUNTRY_CODES | COUNTRIES_SPECIAL_CASES | NUTS_2_REGIONS | NUTS_3_REGIONS
)

UNITS_MAPPING = {
    "MWh_el": "MWh",
    "MWh_LHV": "MWh",
    "MWh_th": "MWh",
    "land transport": "MWh",
    "t_co2": "t",
    "": "",
    "MWh": "MWh",
}


def remap_unit_index(
    series: pd.Series | pd.DataFrame, unit_mapping: dict = UNITS_MAPPING
) -> pd.Series | pd.DataFrame:
    """Remaps unit index to standard value for statistics with need for
    direct comparison of input-output flows.

    Parameters
    ----------
    series : pd.Series | pd.DataFrame
        A series with a MultiIndex with a ``unit`` level.
    unit_mapping : dict, optional
        Dictionary with old unit values as keys and new unit values as values, by default UNITS_MAPPING

    Returns
    -------
    pd.Series | pd.DataFrame
        A series with a MultiIndex with a ``unit`` level remapped."""
    idx = series.index.to_frame(index=False)
    idx["unit"] = idx["unit"].replace(unit_mapping)
    out = series.copy()
    out.index = pd.MultiIndex.from_frame(idx, names=series.index.names)
    return out


## standards for statistics-functions
# standardize kwargs for pypsa-statistics statements
statistics_kwargs = {
    "groupby": ["location", "unit"],
    "nice_names": False,
}
statistics_kwargs_for_filtering = {
    "groupby": ["name", "bus", "carrier", "location", "unit"],
    "nice_names": False,
}
statistics_kwargs_for_imports = {
    "groupby": ["bus0", "bus1", "unit"],
    "nice_names": False,
}
# standardize MultiIndex
statistics_grouping_index = ["location", "unit"]


## UTILS FUNCTIONS


def get_energy_totals_domestic_share(
    energy_totals: Path,
    kind: str,
) -> pd.Series:
    """
    Return the domestic share of energy totals for a given kind.

    Parameters
    ----------
    energy_totals
        Path to the energy totals csv file.
    kind: {'aviation', 'navigation'}
        The kind of energy totals to calculate the factor for.

    Returns
    -------
    :
        The share of national aviation or navigation per country.
    """
    # TODO generalize energy totals for all countries
    energy_totals = pd.read_csv(energy_totals, index_col="country").loc["AT"]
    energy_totals = energy_totals[energy_totals.year == 2020]
    domestic = energy_totals[f"total domestic {kind}"]
    international = energy_totals[f"total international {kind}"]
    return (domestic / (domestic + international)).values[0]


def create_location_index_from_copperplate(
    raw_input: pd.Series | pd.DataFrame,
    usage_location_list: list,
    column_name: str = "location",
):
    """
    Replace the values of level ``column_name`` of an indexed object. Default
    column_name to be replaced is "location" for backward compatibility.

    This helper rebuilds the index of ``raw_input`` from its index frame and
    overwrites the ``column_name`` column with values from
    ``usage_location_list``. It is mainly used when location information from
    a copperplate-carrier result must be mapped back to explicit regional labels.

    Parameters
    ----------
    raw_input : pandas.Series or pandas.DataFrame
        Input object with a (Multi)Index that includes a ``location`` level.
        The function preserves data values and index level order/names.
    usage_location_list : list
        New location values to assign row-by-row. Must have the same length as
        ``raw_input``.
    column_name : str, optional
        Name of the index level to replace, by default "location".

    Returns
    -------
    pandas.Series or pandas.DataFrame
        A copy of ``raw_input`` with the same data and a rebuilt index where
        the ``column_name`` level has been replaced.

    Raises
    ------
    ValueError
        If ``usage_location_list`` length does not match the number of rows, or
        if the index cannot be reconstructed with the existing index names.
    ValueError
        If ``column_name`` is not found in the index levels of ``raw_input``.
    """
    idx_df = raw_input.index.to_frame(index=False)
    if column_name not in idx_df.columns:
        raise ValueError(
            f"Column name '{column_name}' not found in index levels: {idx_df.index.names}"
        )
    idx_df[column_name] = pd.Index(usage_location_list).to_numpy()
    new_index = pd.MultiIndex.from_frame(idx_df, names=raw_input.index.names)
    output = raw_input.copy()
    output.index = new_index
    return output


def trace_non_fossil_fraction(
    n: pypsa.Network,
    bus_carrier: str,
    pipeline_carriers: list[str],
    non_fossil_carriers: list[str],
    fossil_carriers: list[str],
) -> pd.DataFrame:
    """Trace the non-fossil content share of a piped bus_carrier pool.

    Uses the proportional-sharing flow-tracing principle: at every snapshot
    a bus's pool (local non-fossil and fossil supply, plus pipeline inflows
    weighted by the sending bus's own share) is assumed well-mixed, so all
    outflows from a bus carry the same non-fossil fraction. The resulting
    per-snapshot linear system is solved directly, which correctly handles
    cyclic/mesh pipeline topologies (e.g. a bus with two-way pipelines to
    several neighbours).

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    bus_carrier : str
        Bus carrier of the piped network, e.g. ``"gas"``.
    pipeline_carriers : list of str
        Link carriers that form the piped network's edges.
    non_fossil_carriers : list of str
        Link carriers whose supply into the network counts as non-fossil - To NOT include
        transmission pipelines but sector-coupling links!
    fossil_carriers : list of str
        Generator carriers whose supply into the network counts as fossil.

    Returns
    -------
    pd.DataFrame
        Non-fossil fraction indexed by ``bus``, with snapshots as columns.
        Buses with zero total inflow at a snapshot are ``NaN``.

    Notes
    -----
    Storage attached to the network (e.g. gas Stores) is not modelled as a
    source; a bus discharging from storage with no other inflow at a given
    snapshot is treated as having zero non-fossil content for that flow.
    """
    non_fossil_local = (
        n.statistics.supply(
            bus_carrier=bus_carrier,
            carrier=non_fossil_carriers,  # sector-coupling links
            components="Link",
            at_port="bus1",
            groupby=["bus", "unit"],
            groupby_time=False,
            nice_names=False,
        )
        .groupby("bus")
        .sum()
    )
    fossil_local = (
        n.statistics.supply(
            bus_carrier=bus_carrier,
            carrier=fossil_carriers,  # fossil generators
            components="Generator",
            groupby=["bus", "unit"],
            groupby_time=False,
            nice_names=False,
        )
        .groupby("bus")
        .sum()
    )
    flows = (
        n.statistics.transmission(
            bus_carrier=bus_carrier,
            carrier=pipeline_carriers,
            at_port="bus1",
            groupby=["bus0", "bus1", "unit"],
            groupby_time=False,
            nice_names=False,
        )
        .groupby(["bus0", "bus1"])
        .sum()
        .fillna(0.0)
    )

    buses = sorted(
        set(non_fossil_local.index)
        | set(fossil_local.index)
        | set(flows.index.get_level_values("bus0"))
        | set(flows.index.get_level_values("bus1"))
    )
    bus_pos = {bus: i for i, bus in enumerate(buses)}
    n_buses = len(buses)

    non_fossil_local = non_fossil_local.reindex(
        index=buses, columns=n.snapshots, fill_value=0.0
    ).to_numpy()
    fossil_local = fossil_local.reindex(
        index=buses, columns=n.snapshots, fill_value=0.0
    ).to_numpy()
    total_local = non_fossil_local + fossil_local

    bus0_idx = flows.index.get_level_values("bus0").map(bus_pos).to_numpy(dtype=np.intp)
    bus1_idx = flows.index.get_level_values("bus1").map(bus_pos).to_numpy(dtype=np.intp)
    flow_values = flows.reindex(columns=n.snapshots, fill_value=0.0).to_numpy()

    identity = np.eye(n_buses)
    result = pd.DataFrame(index=buses, columns=n.snapshots, dtype=float)
    for i, t in enumerate(n.snapshots):
        forward = np.clip(flow_values[:, i], 0, None)  # flows bus0 -> bus 1
        backward = np.clip(-flow_values[:, i], 0, None)  # reversed flows bus1 -> bus 0

        # total values at time t
        inflow = total_local[:, i].copy()  # prepare array holding total values
        np.add.at(inflow, bus1_idx, forward)  # add inflows
        np.add.at(inflow, bus0_idx, backward)  # add inflows from reversed

        # gas flow allocation - total values from neighbour flows
        allocation = np.zeros((n_buses, n_buses))
        allocation[bus1_idx, bus0_idx] += forward  # rows where to | column where from
        allocation[
            bus0_idx, bus1_idx
        ] += (
            backward  # rows where to | columns where from - sign flipped at "backwards"
        )

        # get shares of arrivals from total bus production
        valid = inflow > 0
        allocation_shares = np.zeros((n_buses, n_buses))
        allocation_shares[valid] = allocation[valid] / inflow[valid, None]  #

        # get share of local non-fossil production to total inflow at bus
        source = np.zeros(n_buses)
        source[valid] = non_fossil_local[valid, i] / inflow[valid]

        # assumtion: well-mixed pool assumption
        # x[i] = source[i] + sum(allocation_shares[i,j] for all j) * x[j]
        solved = np.linalg.solve(identity - allocation_shares, source)
        fraction = np.full(n_buses, np.nan)
        fraction[valid] = solved[valid]
        result[t] = fraction

    return result.clip(lower=0.0, upper=1.0)


def setup_logging(level: int | str = logging.WARNING) -> None:
    """Configure root logging once for the package entrypoint.

    Parameters
    ----------
    level : int or str, optional
        Logging level to configure, by default ``logging.WARNING``.
    """
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
