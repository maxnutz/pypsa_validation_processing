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
import numpy as np
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
) -> pd.Series:
    """Extract transportation-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses, including charging losses) across a
    PyPSA Network.

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
    Includes all transportation-relevant carriers for component Load.
    Evaluation restricted to Load excludes V2G.
    For including charging losses for vehicle charging transport purpose only,
    a fraction of charging and V2G per country is calculated to multiply with losses
    calculated from input-output comparison of ``BEV charger`` links.

    """
    # sum over all transportation-relevant sectors - 2 different units involved.
    # count for transport sector Loads
    transport_carriers = [
        "land transport EV",
        "land transport fuel cell",
        "land transport oil",
        "kerosene for aviation",
        "shipping methanol",
        "shipping oil",
    ]
    # transport sector LOADS
    stat_transport = (
        n.statistics.energy_balance(
            carrier=transport_carriers,
            components="Load",
            groupby=["carrier", "unit", "country"],
            direction="withdrawal",
        )
        .groupby(["country", "unit"])
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
