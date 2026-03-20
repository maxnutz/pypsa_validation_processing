"""Statistics functions for PyPSA validation processing.

Each function in this module corresponds to one IAMC variable and extracts
the relevant value from a given PyPSA NetworkCollection.  The functions are
looked up by name via the mapping defined in ``configs/mapping.default.yaml``.

All functions share the same signature::

    def <function_name>(network_collection: pypsa.NetworkCollection) -> pd.DataFrame:
        ...

Each function returns a :class:`pandas.DataFrame` in long format with at
least the columns ``variable``, ``unit``, ``year``, and ``value``.
"""

from __future__ import annotations

import pandas as pd
import pypsa


def Final_Energy_by_Carrier__Electricity(
    network_collection: pypsa.NetworkCollection,
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
    # Dummy placeholder – to be replaced with the actual pypsa statistics call.
    # e.g.: network_collection.statistics.energy_balance(comps=["Load"], bus_carrier="AC")
    return pd.DataFrame(
        {
            "variable": ["Final Energy [by Carrier]|Electricity"],
            "unit": ["MWh"],
            "year": [2020],
            "value": [0.0],
        }
    )


def Final_Energy_by_Sector__Transportation(
    network_collection: pypsa.NetworkCollection,
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
    # Dummy placeholder – to be replaced with the actual pypsa statistics call.
    # e.g.: network_collection.statistics.energy_balance(comps=["Load"], carrier="transport")
    return pd.DataFrame(
        {
            "variable": ["Final Energy [by Sector]|Transportation"],
            "unit": ["MWh"],
            "year": [2020],
            "value": [0.0],
        }
    )
