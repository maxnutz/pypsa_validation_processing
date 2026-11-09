"""Statistics functions for PyPSA validation processing.

Each function in this module corresponds to one IAMC variable and extracts
the relevant value from a given PyPSA Network.  The functions are
looked up by name via the mapping defined in ``configs/mapping.default.yaml``.

For statistics-functions, the fixed input is n = pypsa.Network (one network / investment year)
and aggregate_per_year: bool = True to switch between yearly aggregation and full snapshot
time series.

If a variable-specific function needs additional settings, optional function parameters can be added.
Currently, these include ``config`` and ``energy totals``. The functions signature is identified
automatically.

Each function returns a :class:`pandas.Series` with MultiIndex, holding at
least the indexes ``location`` and ``unit`` (for aggregate_per_year = True)
or a :class:`pandas.DataFrame` with MultiIndex and snapshots as columns
(for aggregate_per_year = False).

**Region Level:**
Regions in the returned Series correspond to the network's bus regions
(e.g., "AT1", "AT2", "AT3" for pypsa-at). The postprocessing layer in
Network_Processor handles aggregation to country level or keeps regions
based on the ``aggregation_level`` configuration by the name of the entries of ``location``. All regions starting with the given country-entry are grouped together.
"""

from __future__ import annotations
import logging
import re
import pandas as pd
import numpy as np
import pypsa
from pypsa_validation_processing.utils import (
    statistics_kwargs_for_filtering as kwargs_filtering,
    statistics_kwargs as kwargs,
    statistics_grouping_index,
    UNITS_MAPPING,
    remap_unit_index,
)
from pypsa_validation_processing.utils import (
    get_energy_totals_domestic_share,
    create_location_index_from_copperplate,
    ensure_all_locations,
    MissingInputError,
    non_energy_use,
    apply_coke_correction,
    attribute_locations,
    fossil_oil_share,
    fossil_gas_share,
    decentral_heat_split,
)

logger = logging.getLogger(__name__)


def Final_Energy_by_Carrier__Electricity(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Carrier]|Electricity from a PyPSA Network.

    Sum of the electricity withdrawn from ``low voltage`` buses by the sector
    consumers (agriculture, residential and commercial incl. decentral heat
    pumps and resistive heaters, ``BEV charger``, ``industry electricity``),
    minus the ``V2G`` feed-in to ``low voltage`` (per snapshot, not clipped),
    plus the ``DAC`` withdrawal from ``AC`` buses. Distribution grid, storage
    chargers and district-heat suppliers (``urban central …``) are excluded.

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
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).
    """
    sector_carriers = [
        "agriculture electricity",
        "agriculture machinery electric",
        "industry electricity",
        "BEV charger",
    ]
    excluded = r"urban central|industry|agriculture|charger|distribution"
    stats = {"groupby_time": aggregate_per_year, "nice_names": False}
    groupby = ["carrier", "location", "unit"]
    bus_carriers = set(n.buses["carrier"])
    # pypsa raises ValueError for a bus carrier that is not in the network
    has_lv = "low voltage" in bus_carriers
    lv_carriers = (
        n.statistics.withdrawal(
            bus_carrier="low voltage", groupby="carrier", nice_names=False
        ).index.get_level_values("carrier")
        if has_lv
        else pd.Index([])
    )
    included = [
        c
        for c in lv_carriers.unique()
        if c in sector_carriers or not re.search(excluded, c)
    ]

    parts = []
    if included:
        parts.append(
            n.statistics.withdrawal(
                bus_carrier="low voltage", carrier=included, groupby=groupby, **stats
            )
        )
    if has_lv and "V2G" in set(n.links["carrier"]):
        v2g = n.statistics.supply(
            bus_carrier="low voltage", carrier="V2G", groupby=groupby, **stats
        )
        parts.append(-v2g)
    if "DAC" in set(n.links["carrier"]) and "AC" in bus_carriers:
        parts.append(
            n.statistics.withdrawal(
                bus_carrier="AC", carrier="DAC", groupby=groupby, **stats
            )
        )
    parts = [part for part in parts if not part.empty]
    result = (
        pd.concat(parts).fillna(0.0).groupby(level=statistics_grouping_index).sum()
        if parts
        else pd.Series(dtype=float)
    )
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(
        f"Final Energy [by Carrier]|Electricity finished. Shape: {result.shape}."
    )
    return result


def Net_Imports__Electricity(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract net imports of electricity from a PyPSA Network.

    For location ``l``: ``NI(l) = Σ (−p_port)`` over all ports of ``AC``
    Lines and ``DC`` Links at ``AC`` buses in ``l``, i.e. the energy fed
    into ``l`` minus the energy withdrawn from it. Imports over a lossy
    branch are counted at the receiving port, exports at the sending port.
    Positive = net import, negative = net export. Country values follow
    from summing locations (C8, class ``flow``); losses of branches within
    one country, or within one location, stay in that sum as negative net
    imports (spec ``Net_Imports__Electricity.md`` section 7).

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
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network; locations without branches get
        ``0.0`` (C6.13).
    """
    result = n.statistics.energy_balance(
        components=["Line", "Link"],
        carrier=["AC", "DC"],
        bus_carrier="AC",
        groupby_time=aggregate_per_year,
        **kwargs,
    )
    if not result.empty:
        result = result.groupby(level=statistics_grouping_index).sum()
    result = ensure_all_locations(
        result, n, unit="MWh", aggregate_per_year=aggregate_per_year
    )
    logger.debug(f"Net Imports|Electricity finished. Resulting shape: {result.shape}.")
    return result


def Final_Energy_by_Carrier__Coal(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    industry_non_energy_shares: pd.DataFrame | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Carrier]|Coal from a PyPSA Network.

    ``FE(l) = E(l) · (1 − κ) + E(l) · κ / 1.366`` with
    ``E(l) = L[coal for industry](l) − NE_coal(l)``: the ``coal for industry``
    Load minus its non-energy use (D5), with the coke correction (D6). Coal for
    power plants and CHPs is transformation, not final energy.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    industry_non_energy_shares : pd.DataFrame | None, optional
        Eurostat non-energy shares, index (``country``, ``carrier``), column
        ``non_energy_share`` (C2.5). Without industry production data in the
        network, ``κ = 0`` (Eurostat fallback, D6).

    Returns
    -------
    pd.Series | pd.DataFrame
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).
    """
    carrier = "coal for industry"
    if carrier not in set(n.loads["carrier"]):
        return ensure_all_locations(
            pd.Series(dtype=float), n, "MWh", aggregate_per_year
        )
    demand = n.statistics.withdrawal(
        carrier=carrier,
        components="Load",
        groupby_time=aggregate_per_year,
        **kwargs,
    ).fillna(0.0)
    energy = demand - non_energy_use(demand, industry_non_energy_shares, "Coal")
    result = apply_coke_correction(energy)
    if not result.empty:
        result = result.groupby(level=statistics_grouping_index).sum()
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(f"Final Energy [by Carrier]|Coal finished. Shape: {result.shape}.")
    return result


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
        groupby_time=aggregate_per_year,
        **kwargs,
    )

    # Final Energy|Residential and Commercial|Liquids - urban decentral oil boiler, rural oil boiler
    raw_rescom = n.statistics.withdrawal(
        bus_carrier="oil",
        carrier=["rural oil boiler", "urban decentral oil boiler"],
        groupby=kwargs_filtering["groupby"] + ["bus1"],
        groupby_time=aggregate_per_year,
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
        groupby_time=aggregate_per_year,
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
    logger.debug(
        f"Final Energy by Carrier|Oil finished. Resulting shape: {fossil_oil.shape}. "
    )
    return fossil_oil


def Net_Imports__Oil(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract net imports of oil from a PyPSA Network.

    ``NI(l) = f_oil · (Σ_c W[oil, c](l) + ΔE_store(l)) − S[oil, oil refining](l)``:
    the fossil part of the oil withdrawn by Links (location per D1) and of the
    net withdrawal of ``oil`` Stores, minus the fossil production of the
    location (D2). Positive = net import. The copperplate ``EU``, which holds
    the refining, is negative; the yearly sum over all locations is 0.

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
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).
    """
    if "oil" not in set(n.buses["carrier"]):
        return ensure_all_locations(
            pd.Series(dtype=float), n, "MWh", aggregate_per_year
        )
    f_oil = fossil_oil_share(n)
    stats = {"bus_carrier": "oil", "groupby_time": aggregate_per_year}
    withdrawal = n.statistics.withdrawal(
        components=["Link"],
        groupby=["name", "location", "unit"],
        nice_names=False,
        **stats,
    ).fillna(0.0)
    store = n.statistics.energy_balance(components=["Store"], **stats, **kwargs)
    refining = n.statistics.supply(carrier="oil refining", **stats, **kwargs)
    parts = [
        f_oil * attribute_locations(n, withdrawal),
        -f_oil * store,  # energy balance > 0 is supply, i.e. discharging
        -refining,
    ]
    parts = [
        part.groupby(level=statistics_grouping_index).sum()
        for part in parts
        if not part.empty
    ]
    result = (
        pd.concat(parts).fillna(0.0).groupby(level=statistics_grouping_index).sum()
        if parts
        else pd.Series(dtype=float)
    )
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(f"Net Imports|Oil finished. Shape: {result.shape}.")
    return result


def Final_Energy_by_Carrier__Natural_Gas(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    industry_non_energy_shares: pd.DataFrame | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Carrier]|Natural Gas from a PyPSA Network.

    ``FE(l) = f_gas · (W[gas, decentral gas boilers](l) + L[gas for
    industry](l) − NE_gas(l))``: the fossil share (D3) of the gas withdrawn by
    decentral boilers (location per D1) and of the energy part of the
    ``gas for industry`` Load (non-energy use per D5). Central boilers, CHPs,
    power plants and SMR are transformation, not final energy.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    industry_non_energy_shares : pd.DataFrame | None, optional
        Eurostat non-energy shares, index (``country``, ``carrier``), column
        ``non_energy_share`` (C2.5).

    Returns
    -------
    pd.Series | pd.DataFrame
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).
    """
    boiler_carriers = ["rural gas boiler", "urban decentral gas boiler"]
    parts = []
    if "gas" in set(n.buses["carrier"]) and set(boiler_carriers) & set(
        n.links["carrier"]
    ):
        boilers = n.statistics.withdrawal(
            bus_carrier="gas",
            carrier=boiler_carriers,
            components=["Link"],
            groupby=["name", "location", "unit"],
            groupby_time=aggregate_per_year,
            nice_names=False,
        ).fillna(0.0)
        parts.append(attribute_locations(n, boilers))
    if "gas for industry" in set(n.loads["carrier"]):
        demand = n.statistics.withdrawal(
            carrier="gas for industry",
            components="Load",
            groupby_time=aggregate_per_year,
            **kwargs,
        ).fillna(0.0)
        shares = industry_non_energy_shares
        parts.append(demand - non_energy_use(demand, shares, "Natural Gas"))
    parts = [
        part.groupby(level=statistics_grouping_index).sum()
        for part in parts
        if not part.empty
    ]
    result = (
        fossil_gas_share(n)
        * pd.concat(parts).groupby(level=statistics_grouping_index).sum()
        if parts
        else pd.Series(dtype=float)
    )
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(
        f"Final Energy [by Carrier]|Natural Gas finished. Shape: {result.shape}."
    )
    return result


def Final_Energy_by_Carrier__District_Heat(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    config: dict | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Carrier]|District Heat from a PyPSA Network.

    Heat delivered from district heating grids to consumers, without
    distribution losses: ``FE(l) = L[urban central heat](l) / (1 + λ)
    + L[low-temperature heat for industry](l) + W[DAC](l)``, all withdrawn
    from ``urban central heat`` buses at ``l``. Storage chargers and the heat
    vent withdraw heat but are not consumers; supplying links are not counted.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    config : dict | None, optional
        Network config; ``λ`` is
        ``config["sector"]["district_heating"]["district_heating_loss"]``.

    Returns
    -------
    pd.Series | pd.DataFrame
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).

    Raises
    ------
    MissingInputError
        If the district heating loss is missing in *config*.
    ValueError
        If a ``DAC`` Link supplies heat to an ``urban central heat`` bus, or a
        component with an unknown carrier withdraws from such a bus.
    """
    try:
        loss = float(config["sector"]["district_heating"]["district_heating_loss"])
    except (KeyError, TypeError) as exc:
        raise MissingInputError(
            "sector.district_heating.district_heating_loss"
        ) from exc
    bus_carrier = "urban central heat"
    factors = {
        ("Load", "urban central heat"): 1.0 / (1.0 + loss),
        ("Load", "low-temperature heat for industry"): 1.0,
        ("Link", "DAC"): 1.0,
        ("Link", "urban central water pits charger"): 0.0,
        ("Link", "urban central water tanks charger"): 0.0,
        ("Generator", "urban central heat vent"): 0.0,
    }
    if bus_carrier not in set(n.buses["carrier"]):
        return ensure_all_locations(
            pd.Series(dtype=float), n, "MWh", aggregate_per_year
        )

    heat_buses = n.buses.index[n.buses["carrier"] == bus_carrier]
    dac = n.links[n.links["carrier"] == "DAC"]
    for port in [c[3:] for c in dac.columns if re.fullmatch(r"bus\d+", c)]:
        at_heat = dac.index[dac[f"bus{port}"].isin(heat_buses)]
        if at_heat.empty:
            continue
        # efficiency > 0 at a non-input port means the link outputs heat there
        efficiency = {"0": None, "1": "efficiency"}.get(port, f"efficiency{port}")
        positive = (
            dac.loc[at_heat, efficiency].to_numpy() > 0
            if efficiency
            else np.zeros(len(at_heat), dtype=bool)
        )
        p = n.links_t[f"p{port}"].reindex(columns=at_heat, fill_value=0.0)
        supplying = at_heat[positive | (p < 0).any().to_numpy()]
        if not supplying.empty:
            raise ValueError(
                f"DAC Link(s) supply heat to '{bus_carrier}' buses: {list(supplying)}"
            )

    withdrawal = n.statistics.withdrawal(
        bus_carrier=bus_carrier,
        groupby=["carrier", "location", "unit"],
        groupby_time=aggregate_per_year,
        nice_names=False,
    )
    # groupby_time=False also returns NaN rows for pure suppliers
    withdrawal = withdrawal.fillna(0.0)
    keys = withdrawal.index.droplevel(["location", "unit"])
    withdrawing = withdrawal.ne(0)
    if isinstance(withdrawing, pd.DataFrame):
        withdrawing = withdrawing.any(axis=1)
    unknown = sorted(set(keys[withdrawing.to_numpy()]) - set(factors))
    if unknown:
        raise ValueError(
            f"Unknown components withdraw from '{bus_carrier}' buses: {unknown}"
        )
    factor = pd.Series(keys.map(factors), index=withdrawal.index, dtype=float)
    result = withdrawal.mul(factor, axis=0)
    if not result.empty:
        result = result.groupby(level=statistics_grouping_index).sum()
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(
        f"Final Energy [by Carrier]|District Heat finished. Shape: {result.shape}."
    )
    return result


def Final_Energy_by_Sector__Transportation(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
    energy_totals: pd.DataFrame | None = None,
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
    energy_totals : pd.DataFrame | None, optional
        Energy totals of the investment year, indexed by ``country``
        used to determine domestic shares for aviation and
        navigation liquid fuels via :func:`get_energy_totals_domestic_share`.
        Passed by ``Network_Processor``; the variable is skipped if no energy
        totals are available.

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
        logger.warning(
            "Network includes different efficiencies for BEV chargers. "
            "Using mean value for variable Final_Energy_by_Sector__Transportation"
        )

    elec = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier="BEV charger",
        components="Link",
        groupby_time=aggregate_per_year,
        **kwargs,
    ).mul(
        1 / eff
    )  # ( 1 + ((1/eff)-1))

    # get Final Energy [by Sector]|Transportation|Hydrogen
    h2 = n.statistics.withdrawal(
        carrier="land transport fuel cell",
        components="Load",
        groupby_time=aggregate_per_year,
        **kwargs,
    )

    # get Final Energy [by Sector]|Transportation|Liquids
    aviation_liquids = (
        n.statistics.withdrawal(
            carrier="kerosene for aviation",
            components="Load",
            groupby_time=aggregate_per_year,
            **kwargs,
        )
        * domestic_aviation_fraction
    )

    navigation_liquids = (
        n.statistics.withdrawal(
            carrier=["shipping oil", "shipping methanol"],
            components="Load",
            groupby_time=aggregate_per_year,
            **kwargs,
        )
        * domestic_navigation_fraction
    )

    land_transport_liquids = n.statistics.withdrawal(
        carrier="land transport oil",
        components="Load",
        groupby_time=aggregate_per_year,
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
    logger.debug(
        f"Final Energy by Sector|Transportation finished. Resulting shape: {total.shape}. "
    )
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
    logger.debug(
        f"Final Energy by Sector|Industry finished. Resulting shape: {res.shape}. "
    )
    return res


def Final_Energy_by_Sector__Agriculture(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Sector]|Agriculture from a PyPSA Network.

    ``FE(l) = L[agriculture electricity](l) + L[agriculture machinery
    electric](l) + L[agriculture machinery oil](l) + D8_agr(l)``. Losses of
    the machinery oil supply Links are not final energy.

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
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        (``MWh``) and every location of the network (C6.13).

    Raises
    ------
    ValueError
        If an ``agriculture heat`` Load sits on an ``urban central heat`` bus.

    Notes
    -----
    Agricultural heat is produced decentrally on the ``rural heat`` bus, so
    it is not reported as heat in final energy. Instead, the final energy is
    the input carriers of the decentral heat supply (e.g. biomass, electricity
    of heat pumps, CHP heat output), allocated to agriculture by its share of
    the ``rural heat`` demand (D8, ``decentral_heat_split``). The
    ``agriculture heat`` Load itself is therefore not counted.
    """
    heat_loads = n.loads[n.loads["carrier"] == "agriculture heat"]
    central = heat_loads.index[
        heat_loads["bus"].map(n.buses["carrier"]) == "urban central heat"
    ]
    if not central.empty:
        raise ValueError(
            "agriculture heat Load(s) on urban central heat buses are not "
            f"covered by the evaluation: {list(central)}"
        )
    load_carriers = [
        "agriculture electricity",
        "agriculture machinery electric",
        "agriculture machinery oil",
    ]
    split = decentral_heat_split(n, aggregate_per_year)
    parts = (
        [split.xs("agr", level="sector")]
        if "agr" in split.index.get_level_values("sector")
        else []
    )
    if set(load_carriers) & set(n.loads["carrier"]):
        loads = n.statistics.withdrawal(
            carrier=load_carriers,
            components="Load",
            groupby_time=aggregate_per_year,
            **kwargs,
        ).fillna(0.0)
        parts.append(remap_unit_index(loads))
    parts = [
        part.groupby(level=statistics_grouping_index).sum()
        for part in parts
        if not part.empty
    ]
    result = (
        pd.concat(parts).groupby(level=statistics_grouping_index).sum()
        if parts
        else pd.Series(dtype=float)
    )
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(
        f"Final Energy [by Sector]|Agriculture finished. Shape: {result.shape}."
    )
    return result


def Final_Energy_by_Sector__Residential_and_Commercial(
    n: pypsa.Network,
    aggregate_per_year: bool = True,
) -> pd.Series | pd.DataFrame:
    """Extract residential and commercial-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the sector residentials and
    commercials across the pypsa-network.

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
    excludes EV-charging, as covered by Sector Transportation. Concerning Carrier heat, the Function distinguishes between
    central heating systems (Final Energy is Heat) and decentral heating systems (Final Energy is Electricity, Gas, Liquids
    or Solids).
    """
    # Final Energy|Residential and Commercial|Electricity
    # include home batteries
    # include decentral heating technologies
    # exclude central heating technologies
    # exclude EV charging.
    low_voltage_elec = n.statistics.withdrawal(
        bus_carrier="low voltage",
        carrier=[
            "rural resistive heater",
            "urban decentral resistive heater",
            "home battery discharger",
            "home battery charger",
            "rural air heat pump",
            "rural ground heat pump",
            "urban decentral air heat pump",
        ],
        groupby_time=aggregate_per_year,
        **kwargs,
    )

    # Final Energy|Residential and Commercial|Heat
    # urban central heat as bus_carrier
    # decentral solar thermal
    # exclude urban central heat vent
    # exclude low-temperature-teat for industry
    # exclude decentral heating systems
    urban_central_heat = n.statistics.withdrawal(
        bus_carrier="urban central heat",
        carrier=[
            "urban central water pits charger",
            "urban central water tanks charger",
            "DAC",
            "urban central heat",
        ],
        groupby_time=aggregate_per_year,
        **kwargs,
    )

    # Final Energy|Residential and Commercial|Gases
    # urban decentral gas boiler, rural gas boiler
    rescom_gas = n.statistics.energy_balance(
        carrier=["urban decentral gas boiler", "rural gas boiler"],
        components="Link",
        at_port="bus0",  # count gas not heat
        groupby_time=aggregate_per_year,
        **kwargs,
    ).mul(
        -1
    )  # positive Load

    # Final Energy|Residential and Commercial|Liquids -> needs regionalization
    raw_rescom = n.statistics.energy_balance(
        bus_carrier="oil",
        carrier=["rural oil boiler", "urban decentral oil boiler"],
        groupby=kwargs_filtering["groupby"] + ["bus1"],
        at_port="bus0",  # count oil not heat
        groupby_time=aggregate_per_year,
    ).mul(
        -1
    )  # positive Load
    if raw_rescom.empty:
        rescom_liquids = raw_rescom
    else:
        raw_rescom = raw_rescom.drop("Store", errors="ignore")
        usage_location = [
            bus.split(" ")[0] for bus in list(raw_rescom.index.get_level_values("bus1"))
        ]
        rescom_liquids = (
            create_location_index_from_copperplate(raw_rescom, usage_location)
            .groupby(kwargs["groupby"])
            .sum()
        )

    # Final Energy|Residential and Commercial|Solids (Biomass)
    solids_usage = n.statistics.energy_balance(
        bus_carrier="solid biomass",
        carrier=["rural biomass boiler", "urban decentral biomass boiler"],
        components="Link",
        at_port="bus0",  # account for biomass not for heat
        groupby_time=aggregate_per_year,
        **kwargs,
    ).mul(
        -1
    )  # positive Load

    series_list = [
        low_voltage_elec,
        urban_central_heat,
        rescom_gas,
        rescom_liquids,
        solids_usage,
    ]
    series_list = [
        df.groupby(kwargs["groupby"]).sum() for df in series_list if not df.empty
    ]
    total = pd.concat(series_list)
    logger.debug(
        "Final Energy by Sector|Residential and Commercial finished. "
        f"Resulting shape: {total.shape}. "
    )
    return total
