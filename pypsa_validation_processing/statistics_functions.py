"""Statistics functions for PyPSA validation processing.

Each function in this module corresponds to one IAMC variable and extracts
the relevant value from a given PyPSA Network.  The functions are
looked up by name via the mapping defined in ``configs/mapping.default.yaml``.

All functions share the same signature::

    def <function_name>(network_collection: pypsa.Network) -> pd.Series:
        ...

Each function returns a :class:`pandas.Series`  with Multiindex, holding at
least the indexes ``variable`` and ``unit``.
"""

from __future__ import annotations

import pandas as pd
import pypsa


def Final_Energy_by_Carrier__Electricity(
    n: pypsa.Network,
) -> pd.DataFrame:
    """Extract electricity final energy from a PyPSA NetworkCollection.

    Returns the total electricity consumption (excluding transmission /
    distribution losses) across all networks in *network_collection*.

    Parameters
    ----------
    network_collection : pypsa.NetworkCollection
        Collection of PyPSA networks to process.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns ``variable``, ``unit``, ``year``,
        and ``value``.  The ``variable`` column contains
        ``"Final Energy [by Carrier]|Electricity"`` for every row.

    Notes
    -----
    The actual extraction of electricity final energy from the network
    collection will be implemented by the user.  A typical call would be::

        network_collection.statistics.energy_balance(
            comps=["Load"], bus_carrier="AC"
        )

    The current implementation returns a dummy value of ``0.0 MWh`` for the
    year 2020 so that the end-to-end workflow can be tested.
    """
    # withdrawal from electricity including low_voltage
    res = n.statistics.energy_balance(
        bus_carrier="AC", groupby=["carrier", "country", "unit"], direction="withdrawal"
    )
    # as battery is Store, discharger-link needs to be evaluated separately.
    res_storage = n.statistics.energy_balance(
        bus_carrier="AC",
        groupby=["carrier", "country", "unit"],
        carrier=["battery discharger"],
    )
    return pd.concat([res, res_storage], axis=0).groupby(["country", "unit"]).sum()


def Final_Energy_by_Sector__Transportation(
    n: pypsa.Network,
) -> pd.DataFrame:
    """Extract transportation-sector final energy from a PyPSA NetworkCollection.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses) across all networks in
    *network_collection*.

    Parameters
    ----------
    network_collection : pypsa.NetworkCollection
        Collection of PyPSA networks to process.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns ``variable``, ``unit``, ``year``,
        and ``value``.  The ``variable`` column contains
        ``"Final Energy [by Sector]|Transportation"`` for every row.

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
            groupby=["carrier", "unit", "country"],
            direction="withdrawal",
        )
        .groupby(["country", "unit"])
        .sum()
    )
    return res


def Final_Energy_by_Sector__Agriculture(n: pypsa.Network) -> pd.Series:
    """Extract agriculture-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses) across the pypsa-network.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network to process.

    Returns
    -------
    pd.Series
        Pandas Series with Multiindex of ``country`` and ``unit``

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
            groupby=["carrier", "unit", "country"],
            components="Load",
            direction="withdrawal",  # for positive values
        )
        .groupby(["country", "unit"])
        .sum()
    )
    if any(carrier in n.carriers.index for carrier in cc_carriers):
        cc_in = n.statistics.energy_balance(
            carrier=cc_carriers,
            groupby=["carrier", "country", "unit"],
            components="Link",
            at_port=["bus0"],
        )
        cc_out = n.statistics.energy_balance(
            carrier=cc_carriers,
            groupby=["carrier", "country", "unit"],
            components="Link",
            at_port=["bus1"],
        )
        eff_loss = abs(cc_in - cc_out)
        eff_loss = eff_loss.groupby(["country", "unit"]).sum()
        res = res.add(eff_loss, fill_value=0)

    return res
