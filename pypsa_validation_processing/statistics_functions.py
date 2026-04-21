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
import pypsa
from pypsa_validation_processing.utils import statistics_kwargs as kwargs
from pypsa_validation_processing.utils import statistics_grouping_index


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
        bus_carrier="low voltage", aggregate_time=aggregate_per_year, **kwargs
    )
    forbitten_list = []
    for i in lv.index.get_level_values("carrier").unique():
        for regex in [
            "urban central",
            "industry",
            "agriculture",
            "charger",
            "distribution",
        ]:
            if regex in i:
                forbitten_list.append(i)
    rescom = lv[~lv.index.get_level_values("carrier").isin(forbitten_list)]

    # get Final Energy|Transportation|Electricity
    transpo = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier="BEV charger",
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
        **kwargs,
    )

    series_list = [agri, rescom, transpo, industry, dac]
    series_list = [series for series in series_list if not series.empty]

    if series_list and any(
        type(series) is not type(series_list[0]) for series in series_list
    ):
        raise TypeError(
            "Final Energy\|Electricity energy statistics must all have the same datatype."
        )

    result = reduce(lambda a, b: a.add(b, fill_value=0), series_list)
    return result


def Final_Energy_by_Sector__Transportation(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract transportation-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
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
    Includes all transportation-relevant carriers for component Load. Vehicle to Grid
    does not need to be evaluated, as evaluation is restricted to Load-Components only.
    """
    # sum over all transportation-relevant sectors - 2 different units involved.
    res = (
        n.statistics.energy_balance(
            carrier=[
                "land transport EV",
                "land transport fuel cell",
                "land transport oil",
                "kerosene for aviation",
                "shipping methanol",
                "shipping oil",
            ],
            components="Load",
            groupby=["carrier", "unit", "location"],
            direction="withdrawal",  # for positive values
            groupby_time=aggregate_per_year,
        )
        .groupby(["location", "unit"])
        .sum()
    )
    return res


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
