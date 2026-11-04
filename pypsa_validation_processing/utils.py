"""Static information and general utility functions for pypsa_validation_processing."""

import logging

import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

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

# all assigned ISO 3166-1 alpha-2 codes, accepted as ``country`` (C1.6)
ISO_3166_ALPHA2_CODES: frozenset[str] = frozenset("""
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI
    BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN
    CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK
    FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM
    HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN
    KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK
    ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP
    NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW
    SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF
    TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI
    VN VU WF WS YE YT ZA ZM ZW
    """.split())

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
    # bus unit label of `land transport oil` (pypsa-eur `add_ice_cars`), fuel
    # energy (LHV); a permanent key, functions may return it raw (D7, C9.1)
    "land transport": "MWh",
    "t_co2": "t",
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


# D2: carriers that supply oil buses; only ``oil refining`` is fossil (OQ-23)
OIL_FOSSIL_CARRIERS: tuple[str, ...] = ("oil refining",)
OIL_NON_FOSSIL_CARRIERS: tuple[str, ...] = (
    "Fischer-Tropsch",
    "biomass to liquid",
    "biomass to liquid CC",
    "electrobiofuels",
    "unsustainable bioliquids",
    "import oil",
)

# D3: Generators that supply fossil gas, Links that supply non-fossil gas (OQ-23)
GAS_FOSSIL_CARRIERS: tuple[str, ...] = ("lng gas", "pipeline gas", "production gas")
GAS_NON_FOSSIL_CARRIERS: tuple[str, ...] = (
    "Sabatier",
    "biogas to gas",
    "biogas to gas CC",
    "BioSNG",
    "BioSNG CC",
    "import gas",
)
# D3: gas transport, excluded together with every other Link between gas buses
GAS_TRANSPORT_CARRIERS: tuple[str, ...] = ("gas pipeline", "gas pipeline new")

# D6: MWh of coal per MWh of coke
MWH_COAL_PER_MWH_COKE = 1.366

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


def attribute_locations(
    n: pypsa.Network, flows: pd.Series | pd.DataFrame
) -> pd.Series | pd.DataFrame:
    """Attribute flows on copperplate buses to a location (D1).

    ``pypsa.statistics`` already attributes a flow to the location of the bus
    at the evaluated port (D1.1, D1.2). This helper applies the copperplate
    exception: a Link flow at location ``EU`` is moved to the location of the
    Link's ``bus1`` (D1.3). If ``bus1`` is a copperplate bus as well, the flow
    stays at ``EU`` (D1.4). Flows of other components are not changed.

    Parameters
    ----------
    n : pypsa.Network
        Network the flows were evaluated on.
    flows : pd.Series | pd.DataFrame
        Result of a ``pypsa.statistics`` call whose index contains the levels
        ``component``, ``name`` and ``location``. ``pypsa.statistics`` drops
        the ``component`` level if ``components`` is a single string, so pass
        a list (e.g. ``components=["Link"]``).

    Returns
    -------
    pd.Series | pd.DataFrame
        Copy of *flows* with the ``location`` level replaced. Rows are not
        regrouped, so two rows may now share all index values.

    Raises
    ------
    ValueError
        If the index of *flows* lacks one of the required levels.
    """
    missing = [
        level
        for level in ("component", "name", "location")
        if level not in flows.index.names
    ]
    if missing:
        raise ValueError(
            f"flows lack the index levels {missing} (D1). Group by 'name' and "
            "'location', and pass 'components' as a list: pypsa drops the "
            "'component' level for a single component given as a string."
        )
    index = flows.index.to_frame(index=False)
    on_copperplate = (index["component"] == "Link") & (
        index["location"] == COPPERPLATE_LOCATION
    )
    bus1 = n.links["bus1"].reindex(index.loc[on_copperplate, "name"])
    receiving = n.buses["location"].reindex(bus1).to_numpy()
    locations = index["location"].to_numpy(dtype=object, copy=True)
    locations[on_copperplate.to_numpy()] = receiving
    return create_location_index_from_copperplate(flows, list(locations))


def _fossil_share(
    supply: pd.Series,
    fossil: tuple[str, ...],
    non_fossil: tuple[str, ...],
    bus_carrier: str,
) -> float:
    """Return the fossil share of the yearly *supply* per carrier (D2, D3).

    Internal helper of the ``fossil_<carrier>_share`` functions (e.g.
    :func:`fossil_oil_share`); do not call it directly. It only works for bus
    carriers whose supplying carriers are classified as fossil / non-fossil
    in the spec, passed in as *fossil* and *non_fossil*. Other bus carriers
    (e.g. ``urban central heat``) have no such classification.

    Parameters
    ----------
    supply : pd.Series
        Yearly supply to buses of *bus_carrier*, indexed by ``carrier``.
    fossil : tuple[str, ...]
        Fossil supplying carriers.
    non_fossil : tuple[str, ...]
        Non-fossil supplying carriers.
    bus_carrier : str
        Bus carrier, used in the error message.

    Returns
    -------
    float
        ``fossil supply / (fossil + non-fossil supply)``, ``0.0`` if the
        denominator is 0.

    Raises
    ------
    ValueError
        If a carrier outside *fossil* and *non_fossil* has non-zero supply.
    """
    supply = supply.groupby("carrier").sum()
    unknown = supply[~supply.index.isin(fossil + non_fossil) & supply.ne(0)]
    if not unknown.empty:
        raise ValueError(
            f"Unknown carriers {sorted(unknown.index)} supply '{bus_carrier}' "
            "buses; the spec does not classify them as fossil or non-fossil "
            "(D2, D3)."
        )
    total = supply[supply.index.isin(fossil + non_fossil)].sum()
    if total == 0:
        return 0.0
    return float(supply[supply.index.isin(fossil)].sum() / total)


def fossil_oil_share(n: pypsa.Network) -> float:
    """Return the system-wide fossil share of oil ``f_oil`` (D2).

    Yearly supply to all ``oil`` buses, summed over all locations; Stores are
    excluded. The same value applies to every location and every snapshot.

    Parameters
    ----------
    n : pypsa.Network
        Network to evaluate.

    Returns
    -------
    float
        ``f_oil`` in ``[0, 1]``; ``0.0`` if no oil is supplied.

    Raises
    ------
    ValueError
        If a component other than a Store with a carrier outside
        ``OIL_FOSSIL_CARRIERS`` and ``OIL_NON_FOSSIL_CARRIERS`` supplies oil.
    """
    supply = n.statistics.supply(
        bus_carrier="oil", groupby=["carrier"], nice_names=False
    )
    supply = supply.drop("Store", level="component", errors="ignore")
    return _fossil_share(supply, OIL_FOSSIL_CARRIERS, OIL_NON_FOSSIL_CARRIERS, "oil")


def fossil_gas_share(n: pypsa.Network) -> float:
    """Return the system-wide fossil share of gas ``f_gas`` (D3).

    Yearly supply to all ``gas`` buses, summed over all locations. Stores and
    gas transport (``GAS_TRANSPORT_CARRIERS`` and every Link whose ``bus0``
    and ``bus1`` are both ``gas`` buses) are excluded. The same value applies
    to every location and every snapshot.

    Parameters
    ----------
    n : pypsa.Network
        Network to evaluate.

    Returns
    -------
    float
        ``f_gas`` in ``[0, 1]``; ``0.0`` if no gas is supplied.

    Raises
    ------
    ValueError
        If a non-excluded component with a carrier outside
        ``GAS_FOSSIL_CARRIERS`` and ``GAS_NON_FOSSIL_CARRIERS`` supplies gas.
    """
    supply = n.statistics.supply(
        bus_carrier="gas", groupby=["carrier"], nice_names=False
    )
    supply = supply.drop("Store", level="component", errors="ignore")
    bus_carrier = n.buses["carrier"]
    between_gas_buses = (bus_carrier.reindex(n.links["bus0"]).to_numpy() == "gas") & (
        bus_carrier.reindex(n.links["bus1"]).to_numpy() == "gas"
    )
    transport = set(GAS_TRANSPORT_CARRIERS) | set(
        n.links.loc[between_gas_buses, "carrier"]
    )
    supply = supply[~supply.index.get_level_values("carrier").isin(transport)]
    return _fossil_share(supply, GAS_FOSSIL_CARRIERS, GAS_NON_FOSSIL_CARRIERS, "gas")


def apply_domestic_share(
    energy_stats: pd.Series | pd.DataFrame,
    energy_totals: pd.DataFrame | None,
    kind: str,
) -> pd.Series | pd.DataFrame:
    """Multiply flows by the domestic share ``d_k(c)`` of their country (D4).

    ``d_k(c) = total domestic k / (total domestic k + total international k)``
    with ``c`` = the first two characters of the location. The share is looked
    up only for rows with a non-zero value (in any snapshot); rows that are 0
    everywhere stay 0 without a lookup, e.g. the pseudo-location ``EU``.

    Parameters
    ----------
    energy_stats : pd.Series | pd.DataFrame
        Energy statistics with a ``location`` index level; a DataFrame has snapshots as
        columns.
    energy_totals : pd.DataFrame | None
        Energy totals of one year, indexed by ``country`` (C2.4).
    kind : str
        ``"aviation"`` or ``"navigation"``.

    Returns
    -------
    pd.Series | pd.DataFrame
        *energy_stats* multiplied row-wise by ``d_k``; a denominator of 0 gives 0.

    Raises
    ------
    ValueError
        If *energy_totals* is ``None``, *kind* is not supported, or a row
        with non-zero Energy statistics belongs to a country without a row in
        *energy_totals*.
    """
    if energy_totals is None:
        raise ValueError("energy_totals is required to compute domestic shares (D4).")
    if kind not in ("aviation", "navigation"):
        raise ValueError(f"kind must be 'aviation' or 'navigation', got: {kind!r}")
    nonzero = energy_stats.ne(0)
    if isinstance(energy_stats, pd.DataFrame):
        nonzero = nonzero.any(axis=1)
    countries = energy_stats.index.get_level_values("location").str[:2]
    needed = pd.Index(countries[nonzero.to_numpy()]).unique()
    missing = needed.difference(energy_totals.index)
    if not missing.empty:
        raise ValueError(
            f"No energy totals row for the countries {sorted(missing)} with "
            f"{kind} demand (D4)."
        )
    domestic = energy_totals.loc[needed, f"total domestic {kind}"]
    total = domestic + energy_totals.loc[needed, f"total international {kind}"]
    share = domestic.div(total).where(total.ne(0), 0.0)
    factor = pd.Series(countries, index=energy_stats.index).map(share).fillna(0.0)
    return energy_stats.mul(factor, axis=0)


def non_energy_use(
    demand: pd.Series | pd.DataFrame,
    shares: pd.DataFrame | None,
    carrier: str,
) -> pd.Series | pd.DataFrame:
    """Return the industrial non-energy use ``NE_x(l)`` (D5, Eurostat fallback).

    ``NE_x(l) = S[c, x] · demand(l)`` with ``c`` = the first two characters of
    the location and ``S`` the Eurostat shares (C2.5). A country without a row
    for *carrier* gets the unweighted mean of all rows of *carrier*, with one
    ``WARNING`` per call naming the countries (none for the copperplate
    ``EU``). ``NE_H2`` is 0, with one ``WARNING`` per call. ``0 ≤ S ≤ 1`` is
    checked when the file is read; a share outside ``[0, 1]`` here (e.g. after
    an adaptation of the shares) is clipped to ``[0, 1]`` with one ``WARNING``
    per call, so ``0 ≤ NE_x(l) ≤ demand(l)``.

    Parameters
    ----------
    demand : pd.Series | pd.DataFrame
        Industry demand of *carrier* (e.g. the ``gas for industry`` Load) with
        a ``location`` index level; a DataFrame has snapshots as columns.
    shares : pd.DataFrame | None
        Index (``country``, ``carrier``), column ``non_energy_share`` (C2.5).
        Read from the CSV written by the sister package
        ``eurostat-energy-balance_processing``
        (``utils.calculate_industry_non_energy_shares``, written by
        ``IAMC_Creator.write_industry_non_energy_shares``).
    carrier : str
        ``"Natural Gas"``, ``"Oil"``, ``"Coal"`` or ``"H2"``.

    Returns
    -------
    pd.Series | pd.DataFrame
        Non-energy use with the index and columns of *demand*.

    Raises
    ------
    ValueError
        If *carrier* is not supported, or *shares* is ``None`` for a carrier
        other than ``"H2"``.
    """
    if carrier == "H2":
        logger.warning(
            "H2 non-energy use is skipped: Eurostat has no hydrogen share (D5)."
        )
        return demand * 0.0
    if carrier not in ("Natural Gas", "Oil", "Coal"):
        raise ValueError(
            "carrier must be 'Natural Gas', 'Oil', 'Coal' or 'H2', " f"got: {carrier!r}"
        )
    if shares is None:
        raise ValueError("industry_non_energy_shares is required (D5, C2.5).")
    carrier_shares = shares.xs(carrier, level="carrier")["non_energy_share"]
    countries = pd.Series(
        demand.index.get_level_values("location").str[:2], index=demand.index
    )
    missing = sorted(
        set(countries) - set(carrier_shares.index) - {COPPERPLATE_LOCATION}
    )
    if missing:
        logger.warning(
            "No industry non-energy share of '%s' for %s; using the mean of all "
            "countries in the shares table (D5).",
            carrier,
            missing,
        )
    factor = countries.map(carrier_shares).fillna(carrier_shares.mean())
    out_of_range = ~factor.between(0.0, 1.0)
    if out_of_range.any():
        logger.warning(
            "Industry non-energy share of '%s' outside [0, 1] for %s; clipped to "
            "[0, 1] so that 0 <= non-energy use <= demand (D5).",
            carrier,
            sorted(set(countries[out_of_range])),
        )
        factor = factor.clip(0.0, 1.0)
    return demand.mul(factor, axis=0)


def apply_coke_correction(
    coal_energy: pd.Series | pd.DataFrame, kappa: float | None = None
) -> pd.Series | pd.DataFrame:
    """Apply the coke correction to the energy part of industrial coal (D6).
       PyPSA reports with `coal for industry` the coal, that goes _into_ coke
       ovens, Eurostats final energy counts the coke, that _comes out_ of them.

    ``FE = E · (1 − κ) + E · κ / MWH_COAL_PER_MWH_COKE`` with ``E`` the
    ``coal for industry`` demand minus its non-energy use (D5).

    Parameters
    ----------
    coal_energy : pd.Series | pd.DataFrame
        Energy part ``E`` of the industrial coal demand.
    kappa : float | None, optional
        Coke share ``κ`` in ``[0, 1]`` from the physical method (C2.5). If
        ``None`` (default), the Eurostat fallback ``κ = 0`` applies and one
        ``WARNING`` is logged.

    Returns
    -------
    pd.Series | pd.DataFrame
        Coal final energy with the index and columns of *coal_energy*.

    Raises
    ------
    ValueError
        If *kappa* is outside ``[0, 1]``.
    """
    if kappa is None:
        logger.warning(
            "Coke correction is skipped (kappa = 0): Eurostat has no usable coke "
            "share (D6)."
        )
        kappa = 0.0
    if not 0.0 <= kappa <= 1.0:
        raise ValueError(f"kappa must be in [0, 1], got: {kappa!r}")
    return coal_energy * (1.0 - kappa) + coal_energy * kappa / MWH_COAL_PER_MWH_COKE


# D8: decentral heat bus carriers and the Load carriers of each sector
DECENTRAL_HEAT_BUS_CARRIERS: tuple[str, ...] = ("rural heat", "urban decentral heat")
DECENTRAL_HEAT_SECTORS: dict[str, str] = {
    "rural heat": "rc",
    "urban decentral heat": "rc",
    "agriculture heat": "agr",
    "low-temperature heat for industry": "ind",
}
DECENTRAL_HEAT_OTHER_SECTOR = "other"
# D8: heat storage and dumped heat are neither input nor demand
_HEAT_EXCLUDED_PATTERN = r"water tanks|water pits|heat vent"
_D8_KWARGS = {"groupby": ["name", "carrier", "location", "unit"], "nice_names": False}


def _decentral_heat_input(
    n: pypsa.Network, bus_carrier: str, aggregate_per_year: bool
) -> list[pd.Series | pd.DataFrame]:
    """Return the parts of the input ``I_b`` to buses of *bus_carrier* (D8.1).

    Each part has the levels ``location``, ``carrier`` (input carrier) and
    ``unit``. ``pypsa.statistics`` is called once per bus carrier, because
    without ``bus_carrier`` it keeps only one of several supplying ports of a
    Link (pypsa 1.1.2).
    """
    heat = n.statistics.supply(
        bus_carrier=bus_carrier, components=["Link", "Generator"], **_D8_KWARGS
    )
    heat = heat[
        heat.gt(0)
        & ~heat.index.get_level_values("carrier").str.contains(_HEAT_EXCLUDED_PATTERN)
    ]
    is_link = heat.index.get_level_values("component") == "Link"
    links = heat.index[is_link].get_level_values("name")
    ports = n.links.loc[links, n.links.columns[n.links.columns.str.match(r"bus\d+$")]]
    port_carriers = ports.stack().map(n.buses["carrier"]).dropna()
    other = sorted(set(port_carriers) - {bus_carrier})
    other = [bc for bc in other if "co2" not in bc]
    carriers = sorted(set(n.links.loc[links, "carrier"]))
    chp = set()
    for bc in other:
        supply = n.statistics.supply(
            bus_carrier=bc,
            components=["Link"],
            carrier=carriers,
            groupby=["name"],
            nice_names=False,
        )
        chp |= set(supply[supply.gt(0)].index.get_level_values("name"))
    is_received = ~heat.index.get_level_values("name").isin(links.difference(chp))
    received = heat.index[is_received].get_level_values("name")
    parts = [
        _label_input(
            n.statistics.supply(
                bus_carrier=bus_carrier,
                components=["Link", "Generator"],
                groupby_time=aggregate_per_year,
                **_D8_KWARGS,
            ),
            received,
            bus_carrier,
        )
    ]
    for bc in other:
        withdrawal = n.statistics.withdrawal(
            bus_carrier=bc,
            components=["Link"],
            carrier=carriers,
            groupby_time=aggregate_per_year,
            **_D8_KWARGS,
        )
        parts.append(
            _label_input(attribute_locations(n, withdrawal), links.difference(chp), bc)
        )
    return parts


def _label_input(
    flows: pd.Series | pd.DataFrame, names: pd.Index, input_carrier: str
) -> pd.Series | pd.DataFrame:
    """Keep the rows of *names*, label them with *input_carrier* (D8.1)."""
    flows = flows[flows.index.get_level_values("name").isin(names)]
    index = flows.index.to_frame(index=False)
    index["carrier"] = input_carrier
    flows = flows.copy()
    flows.index = pd.MultiIndex.from_frame(index)
    return flows.groupby(["location", "carrier", "unit"]).sum()


def _decentral_heat_shares(n: pypsa.Network, bus_carrier: str) -> pd.DataFrame:
    """Return the yearly sector shares ``σ_b,x(l)`` (D8.2, D8.3).

    Rows are locations, columns the sectors of ``DECENTRAL_HEAT_SECTORS`` and
    ``DECENTRAL_HEAT_OTHER_SECTOR``; a location without demand has 0 shares.
    """
    demand = n.statistics.withdrawal(
        bus_carrier=bus_carrier, groupby=["carrier", "location"], nice_names=False
    )
    demand = demand.drop("Store", level="component", errors="ignore")
    carriers = demand.index.get_level_values("carrier")
    demand = demand[~carriers.str.contains(_HEAT_EXCLUDED_PATTERN)]
    index = demand.index.to_frame(index=False)
    is_load = index["component"].eq("Load")
    index["sector"] = index["carrier"].map(DECENTRAL_HEAT_SECTORS).where(is_load)
    index["sector"] = index["sector"].fillna(DECENTRAL_HEAT_OTHER_SECTOR)
    sectors = list(dict.fromkeys(DECENTRAL_HEAT_SECTORS.values())) + [
        DECENTRAL_HEAT_OTHER_SECTOR
    ]
    by_sector = (
        pd.Series(
            demand.to_numpy(),
            index=pd.MultiIndex.from_frame(index[["location", "sector"]]),
        )
        .groupby(["location", "sector"])
        .sum()
        .unstack("sector")
        .reindex(columns=sectors)
        .fillna(0.0)
    )
    total = by_sector.sum(axis=1)
    return by_sector.div(total.where(total.ne(0)), axis=0).fillna(0.0)


def decentral_heat_split(
    n: pypsa.Network, aggregate_per_year: bool = True
) -> pd.Series | pd.DataFrame:
    """Split the input to decentral heat supply between sectors (D8).

    For each bus carrier ``b`` of ``DECENTRAL_HEAT_BUS_CARRIERS`` and location
    ``l``: ``D8_x(l) = Σ_b σ_b,x(l) · I_b(l)``. ``I_b`` is the withdrawal of
    the Links that supply heat to ``b`` at their non-heat input ports
    (location per D1), plus the heat supplied by Generators (solar thermal)
    and by CHPs (Links with a further non-heat output) to ``b``. Heat storage
    and heat vents are excluded. ``σ_b,x`` are yearly demand shares, applied
    to every snapshot.

    Parameters
    ----------
    n : pypsa.Network
        Network to evaluate.
    aggregate_per_year : bool, optional
        If ``True`` (default), return yearly values as a Series; otherwise a
        DataFrame with snapshots as columns.

    Returns
    -------
    pd.Series | pd.DataFrame
        Index levels ``sector`` (``rc``, ``agr``, ``ind``, ``other``),
        ``location``, ``carrier`` (input carrier) and ``unit`` (normalised
        to ``MWh``, C6.5). Empty if the network has no decentral heat buses.
    """
    sector_parts = []
    for bus_carrier in DECENTRAL_HEAT_BUS_CARRIERS:
        if bus_carrier not in set(n.buses["carrier"]):
            continue
        inputs = pd.concat(_decentral_heat_input(n, bus_carrier, aggregate_per_year))
        inputs = remap_unit_index(inputs).groupby(["location", "carrier", "unit"]).sum()
        shares = _decentral_heat_shares(n, bus_carrier)
        locations = inputs.index.get_level_values("location")
        for sector in shares.columns:
            factor = shares[sector].reindex(locations).fillna(0.0).to_numpy()
            sector_parts.append(
                pd.concat({sector: inputs.mul(factor, axis=0)}, names=["sector"])
            )
    levels = ["sector", "location", "carrier", "unit"]
    if not sector_parts:
        empty_index = pd.MultiIndex.from_tuples([], names=levels)
        if aggregate_per_year:
            return pd.Series(dtype=float, index=empty_index)
        return pd.DataFrame(index=empty_index, columns=n.snapshots, dtype=float)
    return pd.concat(sector_parts).groupby(levels).sum()


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
