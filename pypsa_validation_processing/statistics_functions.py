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
    """Extract electricity final energy from a PyPSA Network.

    Returns the total electricity consumption (excluding transmission /
    distribution losses)

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
    Extracts all withdrawals from elec network. low_voltage is included in AC withdrawal.
    Remove discharger afterwards, as battery-connecting links have different carrier names.
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
    """Extract transportation-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses)

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
    Includes all carriers directly connected to loads in the transportation sector.
    TODO: Needs futher clarification for bidirectional EV usage!
    """
    # sum over all transportation-relevant sectors - 2 different units involved.
    result = (
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
            direction="withdrawal",  # for positive values
        )
        .groupby(["country", "unit"])
        .sum()
    )
    return result


def Final_Energy_by_Sector__Industry(
    n: pypsa.Network,
) -> pd.DataFrame:
    """Extract transportation-sector final energy from a PyPSA Network.

    Returns the total energy consumed by the transportation sector (excluding
    transmission / distribution losses)

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
    Includes all carriers directly connected to loads in the industry sector. Same Carrier
    names are also attached to some links, so components-grouping is needed!
    Values are exogenously set, so output values are round numbers!
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
    result = (
        n.statistics.energy_balance(
            carrier=carriers,
            groupby=["carrier", "unit", "country"],
            components="Load",
            direction="withdrawal",  # for positive values
        )
        .groupby(["country", "unit"])
        .sum()
    )
    return result
