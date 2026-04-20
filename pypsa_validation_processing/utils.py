"""Static information and general utility functions for pypsa_validation_processing."""

from __future__ import annotations

import re
import warnings
from functools import lru_cache

try:
    import eurostat
except Exception as error:  # pragma: no cover
    EUROSTAT_IMPORT_ERROR = error
    eurostat = None
else:
    EUROSTAT_IMPORT_ERROR = None

try:
    from requests import RequestException
except Exception:  # pragma: no cover
    RequestException = RuntimeError

EUROSTAT_MAPPING_ERRORS = (
    RuntimeError,
    TypeError,
    ValueError,
    KeyError,
    RequestException,
)


FALLBACK_COUNTRY_CODES: dict[str, str] = {
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


COUNTRIES_SPECIAL_CASES: dict[str, str] = {
    "GB0": "United Kingdom",
    "GB1": "United Kingdom-Northern Ireland",
    "DE1": "Germany South-West",
    "DE2": "Germany South-East",
    "DE3": "Germany West",
    "DE4": "Germany East",
    "DE5": "Germany North",
    "DK0": "Denmark West",
    "DK1": "Denmark East",
    "ES0": "Spain mainland",
    "ES1": "Spain-Mallorca",
    "FR0": "France mainland",
    "FR1": "France-Corsica",
    "IT0": "Italy mainland",
    "IT1": "Italy-Sicily",
    "IT2": "Italy-Sardinia",
}


FALLBACK_NUTS_2_REGIONS: dict[str, str] = {
    "AT11": "Burgenland",
    "AT12": "Lower Austria",
    "AT13": "Vienna",
    "AT21": "Carinthia",
    "AT22": "Styria",
    "AT31": "Upper Austria",
    "AT32": "Salzburg",
    "AT33": "Tyrol",
    # Keep historical model key for compatibility; fallback NUTS3 keeps the same key.
    "AT333": "East Tyrol",
    "AT34": "Vorarlberg",
}

FALLBACK_NUTS_3_REGIONS: dict[str, str] = {
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


def _warn_and_return_fallback(
    name: str, fallback: dict[str, str], error: Exception | None = None
) -> dict[str, str]:
    if error is not None:
        warnings.warn(
            f"Eurostat mapping fallback for {name}: {error}",
            RuntimeWarning,
            stacklevel=2,
        )
    return dict(sorted(fallback.items()))


def _get_eurostat_geo_dic(dataset: str) -> dict[str, str]:
    if eurostat is None:
        raise RuntimeError(
            "eurostat package is not available (install with: pixi add eurostat)"
        ) from EUROSTAT_IMPORT_ERROR
    geo_dic = eurostat.get_dic(dataset, par="geo", frmt="dict", lang="en")
    if not isinstance(geo_dic, dict):
        raise TypeError(f"Unexpected Eurostat payload for {dataset}: {type(geo_dic)!r}")
    return geo_dic


def _filter_geo_codes(
    geo_dic: dict[str, str], pattern: str, country_prefix: str | None = None
) -> dict[str, str]:
    return dict(
        sorted(
            {
                code: name
                for code, name in geo_dic.items()
                if isinstance(code, str)
                and isinstance(name, str)
                and re.match(pattern, code)
                and (country_prefix is None or code.startswith(country_prefix))
            }.items()
        )
    )


@lru_cache(maxsize=1)
def get_country_mapping() -> dict[str, str]:
    try:
        mapping = _filter_geo_codes(
            _get_eurostat_geo_dic("nama_10_gdp"), pattern=r"^[A-Z]{2}$"
        )
        if not mapping:
            return _warn_and_return_fallback("countries", FALLBACK_COUNTRY_CODES)
        return mapping
    except EUROSTAT_MAPPING_ERRORS as error:  # pragma: no cover - tests cover this path
        return _warn_and_return_fallback("countries", FALLBACK_COUNTRY_CODES, error)


@lru_cache(maxsize=4)
def get_nuts_mapping(level: int, country_prefix: str | None = None) -> dict[str, str]:
    if level not in (2, 3):
        raise ValueError("NUTS mapping level must be 2 or 3")

    dataset = "nama_10r_2gdp" if level == 2 else "nama_10r_3gdp"
    pattern = r"^[A-Z]{2}[A-Z0-9]{2}$" if level == 2 else r"^[A-Z]{2}[A-Z0-9]{3}$"
    fallback = FALLBACK_NUTS_2_REGIONS if level == 2 else FALLBACK_NUTS_3_REGIONS

    try:
        mapping = _filter_geo_codes(
            _get_eurostat_geo_dic(dataset), pattern=pattern, country_prefix=country_prefix
        )
        if not mapping:
            return _warn_and_return_fallback(f"nuts{level}", fallback)
        return mapping
    except EUROSTAT_MAPPING_ERRORS as error:  # pragma: no cover - tests cover this path
        return _warn_and_return_fallback(f"nuts{level}", fallback, error)


def create_region_mapping() -> dict[str, str]:
    return (
        get_country_mapping()
        | get_nuts_mapping(level=2)
        | get_nuts_mapping(level=3)
        | COUNTRIES_SPECIAL_CASES
    )


EU27_COUNTRY_CODES = get_country_mapping()
NUTS_2_REGIONS = get_nuts_mapping(level=2)
NUTS_3_REGIONS = get_nuts_mapping(level=3)
REGION_MAPPING = create_region_mapping()

UNITS_MAPPING = {
    "MWh_el": "MWh",
    "MWh_LHV": "MWh",
    "MWh_th": "MWh",
    "t_co2": "t",
    "": "",
}
