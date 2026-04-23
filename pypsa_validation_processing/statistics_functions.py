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
import re
from functools import reduce
from pathlib import Path
import pandas as pd
import numpy as np
import pypsa
from pypsa_validation_processing.utils import statistics_kwargs as kwargs
from pypsa_validation_processing.utils import (
    statistics_kwargs_for_filtering as kwargs_filtering,
)
from pypsa_validation_processing.utils import (
    statistics_grouping_index,
    get_energy_totals_domestic_share,
)


def Final_Energy_by_Carrier__Electricity(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract electricity-carrier final energy from a PyPSA Network.

    Returns the total final energy demand supplied by electricity across
    agriculture, residential and commercial, transportation, and industry
    and DAC.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
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
    Combines electricity withdrawals from the following contributions:
    agriculture electricity loads, residential/commercial low-voltage loads
    (excluding dedicated industry/agriculture/charger/distribution categories,
    BEV charging) industry electricity loads, and DAC electricity demand
    change in home battery is of magnitude 1e-9 compared to electricity demand.
    Concerning heat: rural air heat pump, rural ground heat pump, rural resisive
    heater and urban decentral heatings are included. Central heatings using
    electricity as fuel are NOT included.
    """
    # get Final Energy|Agriculture|Electricity
    agri = n.statistics.withdrawal(
        carrier=["agriculture electricity", "agriculture machinery electric"],
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # get Final Energy|Residential and Commercial|Electricity
    lv = n.statistics.withdrawal(
        bus_carrier="low voltage", aggregate_time=aggregate_per_year, **kwargs_filtering
    )
    forbitten_parts = [
        "urban central",
        "industry",
        "agriculture",
        "charger",
        "distribution",
    ]
    lv_carriers = lv.index.get_level_values("carrier").astype(str)
    forbitten_pattern = "|".join(re.escape(part) for part in forbitten_parts)
    forbitten_mask = lv_carriers.str.contains(forbitten_pattern, case=False, regex=True)
    rescom = lv[~forbitten_mask].groupby(kwargs["groupby"]).sum()

    # get Final Energy|Transportation|Electricity
    transpo = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier="BEV charger",
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # get Final Energy|Industry|Electricity
    industry = n.statistics.withdrawal(
        carrier="industry electricity",
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # get electricity load from DAC
    dac = n.statistics.withdrawal(
        bus_carrier="AC",
        carrier="DAC",
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    series_list = [agri, rescom, transpo, industry, dac]
    series_list = [series for series in series_list if not series.empty]

    result = pd.concat(series_list)
    return result


def Final_Energy_by_Sector__Transportation(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    energy_totals: Path | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract transportation-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the Transportation sector
    (excluding transmission / distribution losses) across the pypsa-network.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    energy_totals : pathlib.Path | None, optional
        Path to an energy totals file used to determine domestic shares for
        aviation and navigation liquid fuels. If ``None``, default domestic
        shares from :func:`get_energy_totals_domestic_share` are used.

    Returns
    -------
    pd.Series | pd.DataFrame
        Pandas Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex including ``location``
        and ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    Sums transportation final energy from electricity, hydrogen, and liquid
    fuels:
    - Electricity demand from BEV charging loads.
    - Additional EV charging losses computed from BEV charger link flows and
      adjusted for V2G participation.
    - Hydrogen demand from fuel-cell land transport.
    - Liquid fuels for aviation and navigation scaled by domestic fractions,
      plus land-transport oil.

    Raises
    ------
    ValueError
        If BEV charging flow sign conventions are violated.
    TypeError
        If intermediate statistics return mixed result types.
    """

    domestic_aviation_fraction = get_energy_totals_domestic_share(
        energy_totals, "aviation"
    )
    domestic_navigation_fraction = get_energy_totals_domestic_share(
        energy_totals, "navigation"
    )

    # get Final Energy [by Sector]|Transportation|Electricity
    # get elec load losses from BEV-charger links
    bev_charger_efficiencies = n.links.loc[
        n.links.carrier == "BEV charger", "efficiency"
    ].dropna()
    if bev_charger_efficiencies.nunique() == 1:
        eff = bev_charger_efficiencies.iloc[0]
    else:
        eff = bev_charger_efficiencies.mean()
        print(
            "WARNING: Network includes different efficiencies for BEV chargers. Using mean value for variable Final_Energy_by_Sector__Transportation"
        )

    elec = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier="BEV charger",
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs,
    ).mul(
        1 / eff
    )  # ( 1 + ((1/eff)-1))

    # get Final Energy [by Sector]|Transportation|Hydrogen
    h2 = n.statistics.withdrawal(
        carrier="land transport fuel cell",
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # get Final Energy [by Sector]|Transportation|Liquids
    aviation_liquids = (
        n.statistics.withdrawal(
            carrier="kerosene for aviation",
            components="Load",
            aggregate_time=aggregate_per_year,
            **kwargs,
        )
        * domestic_aviation_fraction
    )

    navigation_liquids = (
        n.statistics.withdrawal(
            carrier=["shipping oil", "shipping methanol"],
            components="Load",
            aggregate_time=aggregate_per_year,
            **kwargs,
        )
        * domestic_navigation_fraction
    )

    land_transport_liquids = n.statistics.withdrawal(
        carrier="land transport oil",
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    series_list = [
        elec,
        h2,
        aviation_liquids,
        navigation_liquids,
        land_transport_liquids,
    ]
    series_list = [series for series in series_list if not series.empty]

    total = pd.concat(series_list)
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
    if any(carrier in n.carriers.index for carrier in cc_carriers):
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
        eff_loss = abs(cc_in - cc_out)
        eff_loss = eff_loss.groupby(["location", "unit"]).sum()
        res = res.add(eff_loss, fill_value=0)

    return res
