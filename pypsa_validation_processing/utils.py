"""Static information and general utility functions for pypsa_validation_processing."""

import logging
import pandas as pd

EU27_COUNTRY_CODES: dict[str, str] = {
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GB0": "United Kingdom Great Britain",
    "GB1": "United Kingdom Northern Ireland",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "XK": "Kosovo",
    "EU": "European Union",
}

# the 27 member states of the European Union, aggregated for ``country: EU`` (C1.6, C8.8)
EU_MEMBER_STATES: tuple[str, ...] = (
    "AT",
    "BE",
    "BG",
    "CY",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
)

# copperplate pseudo-location of pypsa-eur networks, never part of the output (C8.7)
COPPERPLATE_LOCATION = "EU"

COUNTRIES_SPECIAL_CASES: dict[str, str] = {
    "DE1": "Germany South-West",
    "DE2": "Germany South-East",
    "DE3": "Germany West",
    "DE4": "Germany East",
    "DE5": "Germany North",
    "DK0": "Denmark West",
    "DK1": "Denmark East",
    "ES0": "Spain Mainland",
    "ES1": "Spain Mallorca",
    "FR0": "France Mainland",
    "FR1": "France Corsica",
    "IT0": "Italy Mainland",
    "IT1": "Italy Sicily",
    "IT2": "Italy Sardinia",
}


NUTS_2_REGIONS: dict[str, str] = {
    "AT11": "Burgenland",
    "AT12": "Lower Austria",
    "AT13": "Vienna",
    "AT21": "Carinthia",
    "AT22": "Styria",
    "AT31": "Upper Austria",
    "AT32": "Salzburg",
    "AT33": "Tyrol",
    "AT333": "East Tyrol",
    "AT34": "Vorarlberg",
}

NUTS_3_REGIONS: dict[str, str] = {
    "AT111": "Mittelburgenland",
    "AT112": "Nordburgenland",
    "AT113": "Südburgenland",
    "AT121": "Mostviertel-Eisenwurzen",
    "AT122": "Niederösterreich-Süd",
    "AT123": "Sankt Pölten",
    "AT124": "Waldviertel",
    "AT125": "Weinviertel",
    "AT126": "Wiener Umland/Nordteil",
    "AT127": "Wiener Umland/Südteil",
    "AT130": "Wien",
    "AT211": "Klagenfurt-Villach",
    "AT212": "Oberkärnten",
    "AT213": "Unterkärnten",
    "AT221": "Graz",
    "AT222": "Liezen",
    "AT223": "Östliche Obersteiermark",
    "AT224": "Oststeiermark",
    "AT225": "West- und Südsteiermark",
    "AT226": "Westliche Obersteiermark",
    "AT311": "Innviertel",
    "AT312": "Linz-Wels",
    "AT313": "Mühlviertel",
    "AT314": "Steyr-Kirchdorf",
    "AT315": "Traunviertel",
    "AT321": "Lungau",
    "AT322": "Pinzgau-Pongau",
    "AT323": "Salzburg und Umgebung",
    "AT331": "Außerfern",
    "AT332": "Innsbruck",
    "AT333": "Osttirol",
    "AT334": "Tiroler Oberland",
    "AT335": "Tiroler Unterland",
    "AT341": "Bludenz-Bregenzer Wald",
    "AT342": "Rheintal-Bodenseegebiet",
    "ATXXX": "Not regionalised/Unknown NUTS 3",
    "ATZZZ": "Extra-Regio NUTS 3",
}
# NUTS 3 overwrites NUTS2, relevant because of language change of East Tyrol -> Osttirol
REGION_MAPPING = (
    EU27_COUNTRY_CODES | COUNTRIES_SPECIAL_CASES | NUTS_2_REGIONS | NUTS_3_REGIONS
)

UNITS_MAPPING = {
    "MWh_el": "MWh",
    "MWh_LHV": "MWh",
    "MWh_th": "MWh",
    "land transport": "MWh",
    "t_co2": "t",
    "": "",
    "MWh": "MWh",
}


def remap_unit_index(
    series: pd.Series | pd.DataFrame, unit_mapping: dict = UNITS_MAPPING
) -> pd.Series | pd.DataFrame:
    """Remaps unit index to standard value for statistics with need for
    direct comparison of input-output flows.

    Parameters
    ----------
    series : pd.Series | pd.DataFrame
        A series with a MultiIndex with a ``unit`` level.
    unit_mapping : dict, optional
        Dictionary with old unit values as keys and new unit values as values, by default UNITS_MAPPING

    Returns
    -------
    pd.Series | pd.DataFrame
        A series with a MultiIndex with a ``unit`` level remapped."""
    idx = series.index.to_frame(index=False)
    idx["unit"] = idx["unit"].replace(unit_mapping)
    out = series.copy()
    out.index = pd.MultiIndex.from_frame(idx, names=series.index.names)
    return out


## standards for statistics-functions
# standardize kwargs for pypsa-statistics statements
statistics_kwargs = {
    "groupby": ["location", "unit"],
    "nice_names": False,
}
statistics_kwargs_for_filtering = {
    "groupby": ["name", "bus", "carrier", "location", "unit"],
    "nice_names": False,
}
statistics_kwargs_for_imports = {
    "groupby": ["bus0", "bus1", "unit"],
    "nice_names": False,
}
# standardize MultiIndex
statistics_grouping_index = ["location", "unit"]


## UTILS FUNCTIONS


class MissingInputError(Exception):
    """Raised by a statistics function when a required input key is missing.

    The message names the missing key (e.g. a dotted config path such as
    ``sector.district_heating.district_heating_loss``). ``Network_Processor``
    catches it and skips the variable for that network.
    """


def get_energy_totals_domestic_share(
    energy_totals: pd.DataFrame | None,
    kind: str,
) -> float:
    """
    Return the domestic share of energy totals for a given kind.

    Parameters
    ----------
    energy_totals
        Energy totals of one year, indexed by ``country``.
    kind: {'aviation', 'navigation'}
        The kind of energy totals to calculate the factor for.

    Returns
    -------
    :
        The share of national aviation or navigation per country.
    """
    # TODO generalize energy totals for all countries
    if energy_totals is None:
        raise ValueError("energy_totals is required to compute domestic shares.")
    energy_totals = energy_totals.loc["AT"]
    domestic = energy_totals[f"total domestic {kind}"]
    international = energy_totals[f"total international {kind}"]
    return domestic / (domestic + international)


def create_location_index_from_copperplate(
    raw_input: pd.Series | pd.DataFrame,
    usage_location_list: list,
    column_name: str = "location",
):
    """
    Replace the values of level ``column_name`` of an indexed object. Default
    column_name to be replaced is "location" for backward compatibility.

    This helper rebuilds the index of ``raw_input`` from its index frame and
    overwrites the ``column_name`` column with values from
    ``usage_location_list``. It is mainly used when location information from
    a copperplate-carrier result must be mapped back to explicit regional labels.

    Parameters
    ----------
    raw_input : pandas.Series or pandas.DataFrame
        Input object with a (Multi)Index that includes a ``location`` level.
        The function preserves data values and index level order/names.
    usage_location_list : list
        New location values to assign row-by-row. Must have the same length as
        ``raw_input``.
    column_name : str, optional
        Name of the index level to replace, by default "location".

    Returns
    -------
    pandas.Series or pandas.DataFrame
        A copy of ``raw_input`` with the same data and a rebuilt index where
        the ``column_name`` level has been replaced.

    Raises
    ------
    ValueError
        If ``usage_location_list`` length does not match the number of rows, or
        if the index cannot be reconstructed with the existing index names.
    ValueError
        If ``column_name`` is not found in the index levels of ``raw_input``.
    """
    idx_df = raw_input.index.to_frame(index=False)
    if column_name not in idx_df.columns:
        raise ValueError(
            f"Column name '{column_name}' not found in index levels: {idx_df.index.names}"
        )
    idx_df[column_name] = pd.Index(usage_location_list).to_numpy()
    new_index = pd.MultiIndex.from_frame(idx_df, names=raw_input.index.names)
    output = raw_input.copy()
    output.index = new_index
    return output


def setup_logging(level: int | str = logging.WARNING) -> None:
    """Configure root logging once for the package entrypoint.

    Parameters
    ----------
    level : int or str, optional
        Logging level to configure, by default ``logging.WARNING``.
    """
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
