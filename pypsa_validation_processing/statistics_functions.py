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
    statistics_kwargs as kwargs,
    statistics_grouping_index,
    remap_unit_index,
)
from pypsa_validation_processing.utils import (
    ensure_all_locations,
    MissingInputError,
    non_energy_use,
    apply_coke_correction,
    attribute_locations,
    fossil_oil_share,
    fossil_gas_share,
    decentral_heat_split,
    DECENTRAL_HEAT_BUS_CARRIERS,
    apply_domestic_share,
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

    Notes
    -----
    ``home battery charger`` (withdrawal) and ``home battery discharger``
    (supply) are both excluded. Measured on the networks in ``resources/``
    (``20261020_carbon_accounting_run``, ``AT_KN2040``, ``AT_KN2040_1H``,
    ``electricity_network_0p3``): the ``home battery`` stores are cyclic, so
    charger minus discharger equals the round-trip loss, charger
    ``· (1 − η²)`` with ``η = 0.98``. The largest loss is 3.05 TWh
    (``AT_KN2040_1H`` 2040, 0.06 % of the ``low voltage`` withdrawal);
    it is not counted.
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
    # pypsa raises ValueError for a bus carrier that is not in the network,
    # but returns an empty result for an absent carrier (filtered below)
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
    if has_lv:
        v2g = n.statistics.supply(
            bus_carrier="low voltage", carrier="V2G", groupby=groupby, **stats
        )
        parts.append(-v2g)
    if "AC" in bus_carriers:
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
    from summing locations (C8, class ``flow``).

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

    Notes
    -----
    Limitation: the losses of branches between two locations of the same
    country are not cross-border flows, but stay in the country sum as
    negative net imports. The country value is therefore its cross-border
    net imports minus its internal branch losses (accepted bias, spec
    ``Net_Imports__Electricity.md`` section 7). Branches with both ends in
    the same location do not exist by model design.
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
    energy_totals: pd.DataFrame | None = None,
    industry_non_energy_shares: pd.DataFrame | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Carrier]|Oil from a PyPSA Network.

    ``FE(l) = f_oil · (L[agriculture machinery oil](l) + W[oil, decentral oil
    boilers](l) + L[land transport oil](l) + d_aviation(c) · s_ker(l) ·
    L[kerosene for aviation](l) + d_navigation(c) · L[shipping oil](l)
    + L[naphtha for industry](l) − NE_naphtha(l))``: the fossil share (D2) of
    the oil consumed by the sectors. Boilers are located per D1, domestic
    shares per country (D4), non-energy use per D5. ``s_ker`` is the yearly
    oil-based share of the kerosene supply at ``l``. ``shipping methanol`` is
    not oil. Units are returned as pypsa reports them (D7).

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    energy_totals : pd.DataFrame | None, optional
        Energy totals of one year, indexed by ``country`` (C2.4), for the
        domestic shares of aviation and navigation (D4). Required if the
        network has a ``kerosene for aviation`` or ``shipping oil`` Load.
    industry_non_energy_shares : pd.DataFrame | None, optional
        Eurostat non-energy shares, index (``country``, ``carrier``), column
        ``non_energy_share`` (C2.5). Required if the network has a
        ``naphtha for industry`` Load.

    Returns
    -------
    pd.Series | pd.DataFrame
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).

    Raises
    ------
    ValueError
        If a carrier other than ``kerosene for aviation`` and
        ``methanol-to-kerosene`` supplies a ``kerosene for aviation`` bus;
        if *energy_totals* is ``None`` and the network has a
        ``kerosene for aviation`` or ``shipping oil`` Load; or if
        *industry_non_energy_shares* is ``None`` and the network has a
        ``naphtha for industry`` Load.
    """
    stats = {"groupby_time": aggregate_per_year, **kwargs}
    loads = set(n.loads["carrier"])
    boiler_carriers = ["rural oil boiler", "urban decentral oil boiler"]

    def load(carrier: str) -> pd.Series | pd.DataFrame:
        if carrier not in loads:
            return pd.Series(dtype=float)
        return n.statistics.withdrawal(
            carrier=carrier, components="Load", **stats
        ).fillna(0.0)

    def kerosene_oil_share() -> pd.Series:
        """Yearly oil-based share ``s_ker`` of the kerosene supply per location."""
        bus_carrier = "kerosene for aviation"
        if bus_carrier not in set(n.buses["carrier"]):
            return pd.Series(dtype=float)
        supply = n.statistics.supply(
            bus_carrier=bus_carrier,
            components=["Link", "Generator"],
            groupby=["carrier", "location"],
            nice_names=False,
        )
        by_carrier = supply.groupby("carrier").sum()
        allowed = {"kerosene for aviation", "methanol-to-kerosene"}
        unknown = sorted(c for c, v in by_carrier.items() if c not in allowed and v)
        if unknown:
            raise ValueError(
                f"Unknown carriers supply '{bus_carrier}' buses: {unknown}"
            )
        per_location = supply.groupby(["location", "carrier"]).sum()
        per_location = per_location.unstack("carrier", fill_value=0.0)
        total = per_location.sum(axis=1)
        oil = per_location.get(bus_carrier, pd.Series(0.0, index=total.index))
        return oil.div(total).where(total.gt(0), 0.0)

    parts = [load("agriculture machinery oil"), load("land transport oil")]
    if "oil" in set(n.buses["carrier"]) and set(boiler_carriers) & set(
        n.links["carrier"]
    ):
        boilers = n.statistics.withdrawal(
            bus_carrier="oil",
            carrier=boiler_carriers,
            components=["Link"],
            groupby=["name", "location", "unit"],
            groupby_time=aggregate_per_year,
            nice_names=False,
        ).fillna(0.0)
        parts.append(attribute_locations(n, boilers))
    kerosene = load("kerosene for aviation")
    if not kerosene.empty:
        s_ker = kerosene_oil_share()
        factor = kerosene.index.get_level_values("location").map(s_ker)
        kerosene = kerosene.mul(np.nan_to_num(factor.to_numpy(float)), axis=0)
        parts.append(apply_domestic_share(kerosene, energy_totals, "aviation"))
    shipping = load("shipping oil")
    if not shipping.empty:
        parts.append(apply_domestic_share(shipping, energy_totals, "navigation"))
    naphtha = load("naphtha for industry")
    if not naphtha.empty:
        shares = industry_non_energy_shares
        parts.append(naphtha - non_energy_use(naphtha, shares, "Oil"))
    parts = [
        part.groupby(level=statistics_grouping_index).sum()
        for part in parts
        if not part.empty
    ]
    result = (
        fossil_oil_share(n)
        * pd.concat(parts).groupby(level=statistics_grouping_index).sum()
        if parts
        else pd.Series(dtype=float)
    )
    result = ensure_all_locations(result, n, "MWh", aggregate_per_year)
    logger.debug(f"Final Energy [by Carrier]|Oil finished. Shape: {result.shape}.")
    return result


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

    Notes
    -----
    The result counts only oil the model consumes. Energy statistics
    (Eurostat ``IMP − EXP``, Statistik Austria) count all net imports of oil,
    including oil for non-energy use and refinery own use. PyPSA-AT models
    neither, except ``naphtha for industry``. So the result is lower than
    statistics by about non-energy use minus naphtha plus refinery own use.
    For AT 2024 (Eurostat), that is 65.6 − 13.7 + 23.1 ≈ 75 PJ, about 17 % of
    net imports. Take this into account in comparisons with statistics or
    other models.
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
    has_gas_bus = "gas" in set(n.buses["carrier"])
    # computed even without consumers so that unknown suppliers raise (AC8)
    gas_share = fossil_gas_share(n) if has_gas_bus else 0.0
    parts = []
    if has_gas_bus and set(boiler_carriers) & set(n.links["carrier"]):
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
        gas_share * pd.concat(parts).groupby(level=statistics_grouping_index).sum()
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
                f"DAC Link(s) supply heat to '{bus_carrier}' buses: {list(supplying)}. This evaluation assumes DAC only withdraws heat from such buses, not supply it."
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
    """Extract Final Energy [by Sector]|Transportation from a PyPSA Network.

    ``FE(l) = W[low voltage, BEV charger](l) − S[low voltage, V2G](l)
    + L[electricity for rail](l) + L[land transport fuel cell](l)
    + L[land transport oil](l) + d_aviation(c) · L[kerosene for aviation](l)
    + d_navigation(c) · (L[shipping oil](l) + L[shipping methanol](l))``.
    The ``BEV charger`` withdrawal already includes charging losses and is
    not divided by an efficiency; the ``V2G`` feed-in is subtracted per
    snapshot, without clipping. Units are returned as pypsa reports them
    (incl. ``land transport``, D7); ``Network_Processor`` normalises them.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.
    aggregate_per_year : bool, optional
        If ``True`` (default), aggregate over all snapshots and return a
        :class:`pandas.Series`. If ``False``, return a
        :class:`pandas.DataFrame` with snapshots as columns.
    energy_totals : pd.DataFrame | None, optional
        Energy totals of one year, indexed by ``country`` (C2.4), for the
        domestic shares of aviation and navigation (D4).

    Returns
    -------
    pd.Series | pd.DataFrame
        Series (``aggregate_per_year=True``) or DataFrame
        (``aggregate_per_year=False``) with MultiIndex ``location``, ``unit``
        and every location of the network (C6.13).
    """
    stats = {"groupby_time": aggregate_per_year, **kwargs}
    loads = set(n.loads["carrier"])
    links = set(n.links["carrier"])
    has_lv = "low voltage" in set(n.buses["carrier"])

    def load(carriers: list[str]) -> pd.Series | pd.DataFrame:
        present = [c for c in carriers if c in loads]
        if not present:
            return pd.Series(dtype=float)
        return n.statistics.withdrawal(
            carrier=present, components="Load", **stats
        ).fillna(0.0)

    parts = [
        load(["electricity for rail", "land transport fuel cell", "land transport oil"])
    ]
    if has_lv and "BEV charger" in links:
        parts.append(
            n.statistics.withdrawal(
                bus_carrier="low voltage", carrier="BEV charger", **stats
            ).fillna(0.0)
        )
    if has_lv and "V2G" in links:
        v2g = n.statistics.supply(bus_carrier="low voltage", carrier="V2G", **stats)
        parts.append(-v2g.fillna(0.0))
    for carriers, kind in [
        (["kerosene for aviation"], "aviation"),
        (["shipping oil", "shipping methanol"], "navigation"),
    ]:
        demand = load(carriers)
        if not demand.empty:
            parts.append(apply_domestic_share(demand, energy_totals, kind))
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
        f"Final Energy [by Sector]|Transportation finished. Shape: {result.shape}."
    )
    return result


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
    config: dict | None = None,
) -> pd.Series | pd.DataFrame:
    """Extract Final Energy [by Sector]|Residential and Commercial.

    ``FE(l) = Σ W[low voltage, c](l) + L[urban central heat](l) / (1 + λ)
    + D8_rc(l)``. The electricity term covers the ``low voltage`` consumers
    of the sector; it excludes industry, agriculture, transport (``rail``,
    ``road``, ``BEV charger``), storage chargers, the distribution grid,
    district-heat suppliers and every Link supplying a decentral heat bus,
    whose input enters only via the residential/commercial share of the
    decentral heat input (D8).

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
        (``MWh``) and every location of the network (C6.13).

    Raises
    ------
    MissingInputError
        If the district heating loss is missing in *config*.
    """
    try:
        loss = float(config["sector"]["district_heating"]["district_heating_loss"])
    except (KeyError, TypeError) as exc:
        raise MissingInputError(
            "sector.district_heating.district_heating_loss"
        ) from exc
    excluded = r"urban central|industry|agriculture|charger|distribution|rail|road"
    stats = {"groupby_time": aggregate_per_year, **kwargs}
    bus_carriers = n.buses["carrier"]
    port_buses = n.links.filter(regex=r"^bus\d+$")
    heat_inputs = set(
        n.links.loc[
            port_buses.apply(
                lambda col: col.map(bus_carriers).isin(DECENTRAL_HEAT_BUS_CARRIERS)
            ).any(axis=1),
            "carrier",
        ]
    )
    split = decentral_heat_split(n, aggregate_per_year)
    parts = (
        [split.xs("rc", level="sector")]
        if "rc" in split.index.get_level_values("sector")
        else []
    )
    if "low voltage" in set(bus_carriers):
        lv_carriers = n.statistics.withdrawal(
            bus_carrier="low voltage", groupby="carrier", nice_names=False
        ).index.get_level_values("carrier")
        included = [
            c
            for c in lv_carriers.unique()
            if not re.search(excluded, c) and c not in heat_inputs
        ]
        if included:
            parts.append(
                n.statistics.withdrawal(
                    bus_carrier="low voltage", carrier=included, **stats
                )
            )
    if "urban central heat" in set(n.loads["carrier"]):
        central = n.statistics.withdrawal(
            carrier="urban central heat", components="Load", **stats
        )
        parts.append(central / (1.0 + loss))
    parts = [
        remap_unit_index(part.fillna(0.0))
        .groupby(level=statistics_grouping_index)
        .sum()
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
        "Final Energy [by Sector]|Residential and Commercial finished. "
        f"Shape: {result.shape}."
    )
    return result
