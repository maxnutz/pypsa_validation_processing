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
    The actual extraction of transportation final energy from the network
    collection will be implemented by the user.  A typical call would be::

        network_collection.statistics.energy_balance(
            comps=["Load"], carrier="transport"
        )

    The current implementation returns a dummy value of ``0.0 MWh`` for the
    year 2020 so that the end-to-end workflow can be tested.
    """
    # sum over all transportation-relevant sectors - 2 different units involved.
    result = (
        n.statistics.energy_balance(
            carrier=[
                "land transport EV",
                "land transport fuel cell",
                "kerosene for aviation",
                "shipping methanol",
            ],
            components="Load",
            groupby=["carrier", "unit", "country"],
            direction="withdrawal",
        )
        .groupby(["country", "unit"])
        .sum()
    )
    return result
