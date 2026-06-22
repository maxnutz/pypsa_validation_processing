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
from pypsa_validation_processing.utils import (
    statistics_kwargs_for_filtering as kwargs_filtering,
    statistics_kwargs as kwargs,
    UNITS_MAPPING,
)
from pypsa_validation_processing.utils import (
    get_energy_totals_domestic_share,
    create_location_index_from_copperplate,
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
    forbidden_parts = [
        "urban central",
        "industry",
        "agriculture",
        "charger",
        "distribution",
    ]
    lv_carriers = lv.index.get_level_values("carrier").astype(str)
    forbidden_pattern = "|".join(re.escape(part) for part in forbidden_parts)
    forbidden_mask = lv_carriers.str.contains(forbidden_pattern, case=False, regex=True)
    rescom = lv[~forbidden_mask].groupby(kwargs["groupby"]).sum()

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


def Final_Energy_by_Carrier__Coal(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame | None:
    """Extracts Final Energy [by Carrier]|Coal from the PyPSA Network.

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
    pd.Series | pd.DataFrame | None
        Pandas Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex of ``location`` and
        ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    This function includes only the Final Energy consumption of coal. This excludes
    coal for electricity or CHP, but only focuses on the carrier ``coal for industry``
    as Final Energy of Coal. Return None, if this carrier is not present in the network.
    """
    try:
        industry = n.statistics.withdrawal(
            bus_carrier="coal for industry",
            carrier="coal for industry",
            components="Load",
            aggregate_time=aggregate_per_year,
            **kwargs,
        )
        return industry
    except ValueError:
        return None


def Final_Energy_by_Carrier__Oil(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract fossil final-energy oil demand from a PyPSA Network.

    Returns the final energy from oil carriers after removing an estimated
    renewable-oil share.

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
        Fossil oil final energy with MultiIndex including ``location`` and
        ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    Total oil final energy is built from:
    - agriculture machinery oil (Load),
    - residential/commercial oil boiler demand (rural + urban decentral),
    - land transport oil (Load).

    ``naphtha for industry`` is intentionally excluded because it is treated
    as non-energy use and therefore not part of Final Energy variables.

    Regionalization from the copperplate topology is performed by deriving a
    region code from demand- or production-bus names and applying
    :func:`create_location_index_from_copperplate` before regrouping to
    ``kwargs["groupby"]``.

    The renewable-oil fraction is computed per region as:

    ``renewable oil production in region / total oil demand in region``.

    Renewable production is based on supply from selected renewable-oil
    carriers, while total oil demand is based on withdrawals from oil-using
    carriers. If the fraction exceeds 1 (i.e., renewable production is larger
    than regional oil demand), it is clipped to 1, so the fossil share becomes
    zero in that region. Cross-regional export/import effects of renewable oil
    are not represented in this statistic.

    ``UNITS_MAPPING`` is applied inside this function to enable multiplication
    with demand-side units of the renewable-oil fraction.
    """

    # Final Energy|Agriculture|Liquids - agriculture machinery oil
    agri = n.statistics.withdrawal(
        carrier="agriculture machinery oil",
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # Final Energy|Residential and Commercial|Liquids - urban decentral oil boiler, rural oil boiler
    raw_rescom = n.statistics.withdrawal(
        bus_carrier="oil",
        carrier=["rural oil boiler", "urban decentral oil boiler"],
        groupby=kwargs_filtering["groupby"] + ["bus1"],
        aggregate_time=aggregate_per_year,
    )
    if raw_rescom.empty:
        rescom = raw_rescom
    else:
        raw_rescom = raw_rescom.drop("Store", errors="ignore")
        usage_location = [
            bus.split(" ")[0] for bus in list(raw_rescom.index.get_level_values("bus1"))
        ]
        rescom = (
            create_location_index_from_copperplate(raw_rescom, usage_location)
            .groupby(kwargs["groupby"])
            .sum()
        )

    # Final Energy|Transportation|Liquids
    transpo = n.statistics.withdrawal(
        carrier="land transport oil",
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    series_list = [
        agri,
        rescom,
        transpo,
    ]
    series_list = [series for series in series_list if not series.empty]

    total = pd.concat(series_list).groupby(kwargs["groupby"]).sum()

    # non-fossil parts from renewable-oil production per location
    # renewable oil production
    non_fossil_parts = n.statistics.supply(
        bus_carrier="oil",
        carrier=[
            "unsustainable bioliquids",
            "biomass to liquid",
            "biomass to liquid CC",
            "electrobiofuels",
            "Fischer-Tropsch",
        ],
        at_port="bus1",
        components="Link",
        groupby=kwargs_filtering["groupby"] + ["bus0"],
    )
    home_location = [
        bus.split(" ")[0]
        for bus in list(non_fossil_parts.index.get_level_values("bus0"))
    ]

    non_fossil_parts = create_location_index_from_copperplate(
        non_fossil_parts, home_location
    )
    non_fossil_parts = non_fossil_parts.groupby(kwargs["groupby"]).sum()

    # all oil use
    all_oil = n.statistics.withdrawal(
        bus_carrier="oil",
        carrier=[
            "land transport oil",
            "naphtha for industry",
            "shipping oil",
            "kerosene for aviation",
            "agriculture machinery oil",
            "urban central oil CHP",
            "oil",
            "rural oil boiler",
            "urban decentral oil boiler",
        ],
        components="Link",
        at_port="bus0",
        groupby=["bus1", "carrier", "location", "unit"],
    )

    home_location = [
        bus.split(" ")[0] for bus in list(all_oil.index.get_level_values("bus1"))
    ]

    all_oil = create_location_index_from_copperplate(all_oil, home_location)
    all_oil = all_oil.groupby(kwargs["groupby"]).sum()

    non_fossil_fraction = non_fossil_parts.div(all_oil)
    zero_oil = all_oil.eq(0).reindex(non_fossil_fraction.index, fill_value=False)
    non_fossil_fraction = non_fossil_fraction.mask(zero_oil, 1.0)

    non_fossil_fraction = non_fossil_fraction.clip(upper=1)  # TODO: Issue #53
    non_fossil_fraction = non_fossil_fraction.rename(index=UNITS_MAPPING, level="unit")
    non_fossil_fraction = non_fossil_fraction.groupby(
        kwargs["groupby"]
    ).mean()  # avoid double-indexing
    total = total.rename(index=UNITS_MAPPING)
    total = total.groupby(kwargs["groupby"]).sum()

    # cover edge-case with no oil demand
    if all_oil.empty:
        non_fossil_fraction = total * 0.0 + 1.0
    else:
        non_fossil_fraction = non_fossil_fraction.reindex_like(total).fillna(0.0)

    fossil_oil = total.mul(1 - non_fossil_fraction, axis=0)
    return fossil_oil


def Final_Energy_by_Carrier__Natural_Gas(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract natural-gas final energy from a PyPSA Network.

    Returns the total final energy demand supplied by natural gas across
    residential and commercial buildings and industry, while subtracting the
    estimated non-fossil share of gas consumption.

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
        (``aggregate_per_year=False``) with MultiIndex including
        ``location`` and ``unit``.
        Returns data at regional level as provided by the PyPSA network.
        Country-level aggregation is handled by
        Network_Processor._aggregate_to_country() if configured.

    Notes
    -----
    The function combines residential and commercial gas withdrawals with
    industry gas demand, then scales the total by the fossil fraction of gas.
    The fossil fraction is estimated from the ratio of non-fossil gas
    production to total gas usage, excluding pipeline flows and limiting the
    non-fossil share to at most 1.
    Industry gas demand is reduced by a fixed non-energy-use share for EU-27 based on
    Eurostat energy balance data.
    """
    # get fraction fossil-gas non-fossil-gas
    # non-fossil-gas-production per region
    non_fossil_gas_prod = n.statistics.supply(
        bus_carrier="gas",
        carrier=[
            "Sabatier",
            "biogas to gas",
            "biogas to gas CC",
            "BioSNG",
            "BioSNG CC",
        ],
        at_port="bus1",
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # all gas-usage per region
    all_gas = n.statistics.withdrawal(
        bus_carrier="gas",
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs_filtering,
    )
    all_gas.index.get_level_values("carrier").unique()
    forbidden_parts = ["pipeline"]
    forbidden_pattern = "|".join(re.escape(part) for part in forbidden_parts)

    total_gas_usage_carriers = all_gas.index.get_level_values("carrier").astype(str)
    forbidden_mask = total_gas_usage_carriers.str.contains(
        forbidden_pattern, case=False, regex=True
    )
    total_gas_usage = all_gas[~forbidden_mask]
    total_gas_usage = total_gas_usage.groupby(kwargs["groupby"]).sum()

    # fraction of usage and production values
    non_fossil_fraction = non_fossil_gas_prod / total_gas_usage
    non_fossil_fraction = non_fossil_fraction.replace([np.inf, -np.inf], np.nan)
    non_fossil_fraction = non_fossil_fraction.clip(upper=1)
    non_fossil_fraction = non_fossil_fraction.groupby(kwargs["groupby"]).mean()
    non_fossil_fraction = non_fossil_fraction.rename(index=UNITS_MAPPING)

    # Final Energy|Residential and Commercial|Natural Gas - urban decentral gas boiler
    rescom = n.statistics.withdrawal(
        bus_carrier="gas",
        carrier=["urban decentral gas boiler", "rural gas boiler"],
        components="Link",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # Final Energy|Industry|Natural Gas - gas for industry
    industry = n.statistics.withdrawal(
        bus_carrier="gas for industry",
        carrier=["gas for industry", "gas for industry CC"],
        components="Load",
        aggregate_time=aggregate_per_year,
        **kwargs,
    )

    # get fraction of non-energetic use in industry -> TODO: #61
    # data from Eurostat energy balance for 2024 | EU27 | in TWh
    # online available (used 2026-04-28): https://ec.europa.eu/eurostat/cache/visualisations/energy-balances/enbal.html?geo=EU27_2020&unit=KTOE&language=EN&year=&fuel=fuelMainFuel&siec=TOTAL&details=1&chartOptions=0&stacking=normal&chartBal=&chart=&full=0&chartBalText=&order=DESC&siecs=&dataset=nrg_bal_c&decimals=0&agregates=0&share=false&fuelList=fuelElectricity%2CfuelCombustible%2CfuelNonCombustible%2CfuelOtherPetroleum%2CfuelMainPetroleum%2CfuelOil%2CfuelOtherFossil%2CfuelFossil%2CfuelCoal%2CfuelMainFuel
    # Final consumption - energy use: 7 217 049
    # Final consumption - non-energy use (fuels not combusted): 458 572
    fc_energy = 7217049
    fc_noenergy = 458572
    energy_fraction_industry_gas = fc_energy / (fc_energy + fc_noenergy)
    industry = industry.mul(energy_fraction_industry_gas)

    series_list = [rescom, industry]
    series_list = [series for series in series_list if not series.empty]

    if not series_list:
        return pd.Series(
            dtype=float,
            index=pd.MultiIndex.from_tuples([], names=kwargs["groupby"]),
        )

    total = pd.concat(series_list)
    total = total.rename(index=UNITS_MAPPING).groupby(kwargs["groupby"]).sum()
    non_fossil_fraction = non_fossil_fraction.reindex_like(total).fillna(0)
    result = total.mul(1 - non_fossil_fraction, axis=0)
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
