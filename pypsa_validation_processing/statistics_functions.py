"""Statistics functions for PyPSA validation processing.

Each function in this module corresponds to one IAMC variable and extracts
the relevant value from a given PyPSA Network.  The functions are
looked up by name via the mapping defined in ``configs/mapping.default.yaml``.

All functions share the same signature::

    def <function_name>(network: pypsa.Network) -> pd.Series:
        ...

Each function returns a :class:`pandas.Series` with MultiIndex, holding at
least the indexes ``location`` and ``unit``.

**Region Level:**
Regions in the returned Series correspond to the network's bus regions
(e.g., "AT1", "AT2", "AT3" for pypsa-at). The postprocessing layer in
Network_Processor handles aggregation to country level or keeps regions
based on the ``aggregation_level`` configuration by the name of the entries of ``location``. All regions starting with the given country-entry are grouped together.
"""

from __future__ import annotations
from functools import reduce
import pandas as pd
import numpy as np
import pypsa
from pypsa_validation_processing.utils import statistics_kwargs as kwargs
from pypsa_validation_processing.utils import statistics_grouping_index


def Final_Energy_by_Carrier__Electricity(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract electricity final energy from a PyPSA Network.

    Returns the total electricity consumption (excluding transmission /
    distribution losses)

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`.  If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.

    Returns
    -------
    pd.Series | pd.DataFrame
        Pandas Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex of ``location`` and
        ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    Extracts all withdrawals from elec network. low_voltage is included in AC withdrawal.
    Remove discharger afterwards, as battery-connecting links have different carrier names.
    """
    # withdrawal from electricity including low_voltage
    res = abs(
        n.statistics.energy_balance(
            bus_carrier="AC",
            groupby=["carrier", "location", "unit"],
            groupby_time=aggregate_per_year,
        )
    )
    # as battery is Store, discharger-link needs to be evaluated separately.
    res_storage = n.statistics.energy_balance(
        bus_carrier="AC",
        groupby=["carrier", "location", "unit"],
        carrier=["battery discharger"],
        groupby_time=aggregate_per_year,
    )
    return (
        pd.concat([res, res_storage.mul(-1)], axis=0)
        .groupby(["location", "unit"])
        .sum()
    )


def Final_Energy_by_Sector__Transportation(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """ """

    # TOOD: get domestic to international fractions for avation and navigation
    domestic_aviation_fraction = 0.2
    domestic_navigation_fraction = 0.3

    # get Final Energy [by Sector]|Transportation|Electricity
    elec = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier="BEV charger",
        aggregate_time=True,
        **kwargs,
    )
    # include losses from EV charging
    charging_out = (
        n.statistics.energy_balance(
            carrier="BEV charger", components="Link", at_port=["bus1"], **kwargs
        )
        .groupby(statistics_grouping_index)
        .sum()
    )
    charging_out.replace(0, np.nan, inplace=True)
    charging_in = (
        n.statistics.energy_balance(
            carrier="BEV charger", components="Link", at_port=["bus0"], **kwargs
        )
        .groupby(statistics_grouping_index)
        .sum()
    )
    v2g_in = n.statistics.energy_balance(
        carrier="V2G", components="Link", at_port=["bus0"], **kwargs
    )
    if v2g_in.empty:
        ev_share = pd.Series(1.0, index=charging_out.index)
    else:
        v2g_in = v2g_in.groupby(statistics_grouping_index).sum()
        ev_share = charging_out.add(v2g_in, fill_value=0).div(charging_out)

    if (charging_in > 0).any() or (charging_out < 0).any():
        raise ValueError("Charging in must be positive, charging out must be negative.")

    total_link_losses = charging_out.add(charging_in, fill_value=0)
    EV_charging_losses = total_link_losses.abs().mul(ev_share, fill_value=1.0)

    # get Final Energy [by Sector]|Transportation|Hydroghen
    h2 = n.statistics.withdrawal(
        carrier="land transport fuel cell",
        components="Load",
        aggregate_time=True,
        **kwargs,
    )

    # get Final Energy [by Sector]|Transportation|Liquids
    aviation_liquids = (
        n.statistics.withdrawal(
            carrier="kerosene for aviation",
            components="Load",
            aggregate_time=True,
            **kwargs,
        )
        * domestic_aviation_fraction
    )

    navigation_liquids = (
        n.statistics.withdrawal(
            carrier=["shipping oil", "shipping methanol"],
            components="Load",
            aggregate_time=True,
            **kwargs,
        )
        * domestic_navigation_fraction
    )

    land_transport_liquids = n.statistics.withdrawal(
        carrier="land transport oil", components="Load", aggregate_time=True, **kwargs
    )

    series_list = [
        elec,
        h2,
        aviation_liquids,
        navigation_liquids,
        land_transport_liquids,
        EV_charging_losses,
    ]
    total = reduce(lambda a, b: a.add(b, fill_value=0), series_list)
    total.groupby(statistics_grouping_index).sum()
    return total

def Final_Energy_by_Sector__Industry(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract Industry-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the Industry sector (excluding
    transmission / distribution losses)

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`.  If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.

    Returns
    -------
    pd.Series | pd.DataFrame
        Pandas Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex of ``location`` and
        ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    Includes all carriers directly connected to loads in the industry sector. Same Carrier
    names are also attached to some links, so components-grouping is needed!
    efficiency losses directly supplying industry loads for gas, biomass and coal carbon capture
    are included extra.
    """
    carriers = [
        "coal for industry",
        "industry electricity",
        "gas for industry",
        "H2 for industry",
        "solid biomass for industry",
        "industry methanol",
        "naphtha for industry",
        "low-temperature heat for industry",
    ]
    cc_carriers = [
        "coal for industry CC",
        "gas for industry CC",
        "solid biomass for industry CC",
    ]

    load_statistics = (
        n.statistics.energy_balance(
            carrier=carriers,
            groupby=["carrier", "unit", "location"],
            components="Load",
            direction="withdrawal",  # for positive values
            groupby_time=aggregate_per_year,
        )
        .groupby(["location", "unit"])
        .sum()
    )
    # calculate efficiency losses for links with eff < 1
    cc_in = n.statistics.energy_balance(
        carrier=cc_carriers,
        groupby=["carrier", "location", "unit"],
        components="Link",
        at_port=["bus0"],
        groupby_time=aggregate_per_year,
    )
    cc_out = n.statistics.energy_balance(
        carrier=cc_carriers,
        groupby=["carrier", "location", "unit"],
        components="Link",
        at_port=["bus1"],
        groupby_time=aggregate_per_year,
    )
    eff_loss = abs(cc_in) - abs(cc_out)
    eff_loss = eff_loss.groupby(["location", "unit"]).sum()
    res = load_statistics.add(eff_loss, fill_value=0)
    return res


def Final_Energy_by_Sector__Agriculture(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract agriculture-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses) across the pypsa-network.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`.  If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.

    Returns
    -------
    pd.Series | pd.DataFrame
        Pandas Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex of ``location`` and
        ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    Includes carriers ['agriculture electricity','agriculture heat','agriculture machinery electric',
    'agriculture machinery oil'] executed on Load-Components. Agriculture machinery oil is also carrier
    of Links and Buses, as Demand is assumed fixed. _Time series of Agriculture demand are assumed
    to be constant in PyPSA-EUR._
    Theoretically, machinery oil is a single bus with load and links for energy flow. This bus could be
    sourced by a bus representing oil usage with carbon capture in agriculture. Therefore the "efficiency
    loss" of this link must be added.
    """
    carriers = [
        "agriculture electricity",
        "agriculture heat",
        "agriculture machinery electric",
        "agriculture machinery oil",
    ]
    cc_carriers = ["agriculture machinery oil CC"]
    res = (
        n.statistics.energy_balance(
            carrier=carriers,
            groupby=["carrier", "unit", "location"],
            components="Load",
            direction="withdrawal",  # for positive values
            groupby_time=aggregate_per_year,
        )
        .groupby(["location", "unit"])
        .sum()
    )

    # losses while charging-for-transport
    charging_out = n.statistics.energy_balance(
        carrier="BEV charger",
        components="Link",
        groupby=["country", "unit"],
        at_port=["bus1"],
    )
    charging_out.replace(0, np.nan, inplace=True)
    charging_in = n.statistics.energy_balance(
        carrier="BEV charger",
        components="Link",
        groupby=["country", "unit"],
        at_port=["bus0"],
    )
    v2g_in = n.statistics.energy_balance(
        carrier="V2G", components="Link", groupby=["country", "unit"], at_port=["bus0"]
    )
    if not (no_v2g := v2g_in.empty):
        EV_charging_percentage = (charging_out + v2g_in) / charging_out
    total_link_losses = charging_out + charging_in
    EV_charging_losses = (
        abs(total_link_losses)
        if no_v2g
        else abs(total_link_losses * EV_charging_percentage)
    )

    return stat_transport.add(EV_charging_losses, fill_value=0)
