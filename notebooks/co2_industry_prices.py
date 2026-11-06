import marimo

__generated_with = "0.25.1"
app = marimo.App(
    width="medium",
    app_title="CO2 price in industry carrier prices",
)


@app.cell
def _():
    import logging
    import re
    import urllib.request
    import warnings
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import pypsa

    logging.getLogger("pypsa").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    return Path, mo, np, pd, plt, pypsa, re, urllib


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Effect of the CO2 price on industry carrier prices

    Discussion notebook for issue #160 (context: PR #148, D9 in
    `specs/variables/shared_definitions.md`, variables `Price|Final Energy|Industry|…`, #99–#104).

    The marginal price `λ_b` of an industry Load bus contains the CO2 price, because the Link that supplies
    the bus has a port to `co2 atmosphere`, `co2 stored` or `process emissions`. D9 reports the price
    **without** this CO2 cost `γ`. This notebook shows how large `γ` is, where it comes from in the network,
    how it is derived from the PyPSA nodal balance, and how the model prices compare with historical prices.

    All code is in this notebook (no import of package code). Run it with `pixi run -e notebook notebook`.
    Relative paths are resolved against the repository root.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Setup
    """)
    return


@app.cell
def _(mo):
    network_dir = mo.ui.text(
        value="resources/20261020_carbon_accounting_run/networks",
        label="Network folder (relative to repo root)",
        full_width=True,
    )
    network_dir
    return (network_dir,)


@app.cell
def _(Path, mo, network_dir, pypsa, re):
    REPO_ROOT = mo.notebook_dir().parent
    _dir = Path(network_dir.value)
    _dir = _dir if _dir.is_absolute() else REPO_ROOT / _dir
    _files = {
        int(re.search(r"(\d{4})", _f.stem).group(1)): _f
        for _f in sorted(_dir.glob("solved_*.nc"))
        if re.search(r"(\d{4})", _f.stem)
    }
    mo.stop(
        not _files,
        mo.callout(mo.md(f"No `solved_<year>.nc` files in `{_dir}`."), kind="danger"),
    )
    networks = {_y: pypsa.Network(_f) for _y, _f in _files.items()}
    return REPO_ROOT, networks


@app.cell
def _(mo, networks):
    ALL_CARRIERS = [
        "industry electricity",
        "gas for industry",
        "H2 for industry",
        "solid biomass for industry",
        "coal for industry",
        "naphtha for industry",
        "industry methanol",
    ]
    # fixed colour per carrier (validated categorical palette, fixed order)
    CARRIER_COLORS = dict(
        zip(
            ALL_CARRIERS,
            ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
        )
    )
    COLOR_WITHOUT = "#2a78d6"  # price without CO2
    COLOR_CO2 = "#eb6834"  # CO2 part γ
    COLOR_MUTED = "#8a8984"

    _years = sorted(networks)
    year = mo.ui.dropdown(
        options={str(_y): _y for _y in _years},
        value=str(2040 if 2040 in _years else _years[-1]),
        label="Investment year",
    )
    carriers = mo.ui.multiselect(options=ALL_CARRIERS, value=ALL_CARRIERS, label="Load carriers")
    location_mode = mo.ui.radio(
        options=["All locations", "AT only", "Without AT", "Custom"],
        value="All locations",
        label="Locations",
        inline=True,
    )
    return (
        ALL_CARRIERS,
        CARRIER_COLORS,
        COLOR_CO2,
        COLOR_MUTED,
        COLOR_WITHOUT,
        carriers,
        location_mode,
        year,
    )


@app.cell
def _(mo, networks, year):
    n = networks[year.value]
    _locs = sorted(n.buses.location.replace("", None).dropna().unique())
    custom_locations = mo.ui.multiselect(
        options=_locs, value=[l for l in _locs if l.startswith("AT")], label="Custom locations"
    )
    return custom_locations, n


@app.cell
def _(carriers, custom_locations, location_mode, mo, year):
    mo.vstack(
        [
            mo.hstack([year, carriers], justify="start", gap=2),
            location_mode,
            custom_locations if location_mode.value == "Custom" else mo.md(""),
        ]
    )
    return


@app.cell
def _(custom_locations, location_mode):
    def location_mask(locations):
        """Boolean mask for the location selection in the UI."""
        _mode = location_mode.value
        locations = locations.fillna("")
        if _mode == "AT only":
            return locations.str.startswith("AT")
        if _mode == "Without AT":
            return ~locations.str.startswith("AT")
        if _mode == "Custom":
            return locations.isin(custom_locations.value)
        return locations.notna()

    return (location_mask,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### D9, written out

    * **CO2 ports** of a Link: ports `k ≥ 2` whose bus carrier contains `co2` or is `process emissions`.
    * **Supplying Links** of a Load bus `b`: Links with `bus1 = b`.
    * $\gamma_t(b) = \dfrac{\sum_\text{links} p_{0,t} \sum_{k \in \text{CO2}} (-\eta_k \lambda_{k,t})}{\sum_\text{links} p_{0,t}\,\eta_1}$, and `0` if the denominator is `0`.
    * Yearly Load-weighted price: $P = \dfrac{\sum_t g_t \sum_\text{loads} p_t (\lambda_{b,t} - \gamma_t(b))}{\sum_t g_t \sum_\text{loads} p_t}$
      with snapshot weighting $g_t$; "with CO2" drops the $\gamma$ term.
    """)
    return


@app.cell
def _(np, pd):
    def is_co2_carrier(bus_carrier):
        """D9: a port is a CO2 port if its bus carrier contains 'co2' or is 'process emissions'."""
        return isinstance(bus_carrier, str) and ("co2" in bus_carrier or bus_carrier == "process emissions")

    def link_ports(n):
        return sorted(int(c[3:]) for c in n.links.columns if c.startswith("bus") and c[3:].isdigit())

    def efficiency(n, k):
        """Dense (snapshot × link) efficiency of port k (time-varying values included)."""
        return n.get_switchable_as_dense("Link", "efficiency" if k == 1 else f"efficiency{k}")

    def port_terms(n, links):
        """Per snapshot and Link: Σ_{k≥2} (−η_k·λ_k), split into CO2 ports and other ports."""
        lam = n.buses_t.marginal_price
        co2 = pd.DataFrame(0.0, index=n.snapshots, columns=links)
        other = pd.DataFrame(0.0, index=n.snapshots, columns=links)
        for k in link_ports(n):
            if k < 2:
                continue
            bk = n.links.loc[links, f"bus{k}"]
            bk = bk[bk.notna() & bk.ne("")]
            if bk.empty:
                continue
            term = -(efficiency(n, k)[bk.index] * lam[bk.values].set_axis(bk.index, axis=1))
            co2_mask = bk.map(n.buses.carrier).map(is_co2_carrier)
            co2[bk.index[co2_mask]] += term.loc[:, co2_mask.values]
            other[bk.index[~co2_mask]] += term.loc[:, ~co2_mask.values]
        return co2, other

    def national_co2_duals(n):
        """Duals of national CO2 limits `co2_limit-<ct>` (EUR/t, ≤ constraint → mu ≤ 0)."""
        gc = n.global_constraints
        return {i.split("-", 1)[1]: gc.at[i, "mu"] for i in gc.index if i.startswith("co2_limit-")}

    def national_co2_term(n, links):
        """Per snapshot and Link: −μ_ct · Σ η_k over `co2 atmosphere` ports, for Links named `<ct>…`.

        Mirrors pypsa-de `add_national_co2_budgets` (`additional_functionality.py` l.406ff): the constraint sums
        p·η_k over Links with index prefix `ct` and a port to `co2 atmosphere`. Not part of D9.
        """
        mu = national_co2_duals(n)
        out = pd.DataFrame(0.0, index=n.snapshots, columns=links)
        for k in link_ports(n):
            if k < 1:
                continue
            bk = n.links.loc[links, f"bus{k}"]
            hit = (bk == "co2 atmosphere") & bk.index.str[:2].isin(list(mu))
            if not hit.any():
                continue
            idx = bk.index[hit]
            mu_l = pd.Series([mu[i[:2]] for i in idx], index=idx)
            out[idx] += -efficiency(n, k)[idx] * mu_l
        return out

    def gamma(n, buses, national=False):
        """D9 item 2: CO2 cost per delivered MWh γ_t(b) (snapshot × bus).

        With `national=True` the national CO2 constraint term is added to the CO2 ports (not D9).
        """
        sup = n.links.index[n.links.bus1.isin(buses)]
        p0 = n.links_t.p0.reindex(columns=sup, fill_value=0.0)
        co2, _ = port_terms(n, sup)
        if national:
            co2 = co2 + national_co2_term(n, sup)
        bus1 = n.links.loc[sup, "bus1"]
        num = (p0 * co2).T.groupby(bus1).sum().T
        den = (p0 * efficiency(n, 1)[sup]).T.groupby(bus1).sum().T
        g = (num / den.where(den != 0)).fillna(0.0)
        return g.reindex(index=n.snapshots, columns=pd.Index(buses), fill_value=0.0)

    def load_frames(n, carriers, national=False):
        """Load withdrawal p, bus price λ and CO2 cost γ (snapshot × load) plus load metadata."""
        loads = n.loads[n.loads.carrier.isin(carriers)]
        meta = pd.DataFrame(
            {"carrier": loads.carrier, "bus": loads.bus, "location": loads.bus.map(n.buses.location)}
        )
        p = n.loads_t.p.reindex(columns=loads.index, fill_value=0.0)
        lam = n.buses_t.marginal_price[loads.bus].set_axis(loads.index, axis=1)
        gam = gamma(n, loads.bus.unique(), national=national)[loads.bus].set_axis(loads.index, axis=1)
        return meta, p, lam, gam

    def yearly_table(n, carriers):
        """Per load: weight W = Σ g·p, cost with / without CO2 (K = Σ g·p·λ, Σ g·p·(λ−γ)).

        `K_without_nat` additionally removes the national CO2 constraint term (not D9).
        """
        meta, p, lam, gam = load_frames(n, carriers)
        _, _, _, gam_nat = load_frames(n, carriers, national=True)
        g = n.snapshot_weightings.generators
        tab = meta.copy()
        tab["W"] = p.mul(g, axis=0).sum()
        tab["K_with"] = (p * lam).mul(g, axis=0).sum()
        tab["K_without"] = (p * (lam - gam)).mul(g, axis=0).sum()
        tab["K_without_nat"] = (p * (lam - gam_nat)).mul(g, axis=0).sum()
        return tab

    def aggregate(tab, by):
        """Load-weighted price per group (NaN for zero weight, D9 item 4)."""
        s = tab.groupby(by)[["W", "K_with", "K_without", "K_without_nat"]].sum()
        w = s["W"].where(s["W"] != 0, np.nan)
        out = pd.DataFrame({"with CO2": s["K_with"] / w, "without CO2": s["K_without"] / w})
        out["CO2 part"] = out["with CO2"] - out["without CO2"]
        out["CO2 share"] = out["CO2 part"] / out["with CO2"]
        out["without CO2 incl. national"] = s["K_without_nat"] / w
        out["national CO2 part"] = out["without CO2"] - out["without CO2 incl. national"]
        return out

    return (
        aggregate,
        efficiency,
        gamma,
        is_co2_carrier,
        link_ports,
        load_frames,
        national_co2_duals,
        national_co2_term,
        port_terms,
        yearly_table,
    )


@app.cell
def _(ALL_CARRIERS, networks, yearly_table):
    # D9 per load for every investment year (all carriers; selections filter later)
    year_tables = {_y: yearly_table(_n, ALL_CARRIERS) for _y, _n in networks.items()}
    return (year_tables,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. With vs. without CO2
    """)
    return


@app.cell
def _(aggregate, carriers, location_mask, year, year_tables):
    _tab = year_tables[year.value]
    sel_tab = _tab[_tab.carrier.isin(carriers.value) & location_mask(_tab.location)]
    by_carrier = aggregate(sel_tab, "carrier").reindex([c for c in carriers.value if c in set(sel_tab.carrier)])
    return by_carrier, sel_tab


@app.cell(expand_output=True)
def _(
    COLOR_CO2,
    COLOR_MUTED,
    COLOR_WITHOUT,
    by_carrier,
    location_mode,
    mo,
    np,
    plt,
    year,
):
    _fig, (_a, _b) = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    _x = np.arange(len(by_carrier))
    _labels = [c.replace(" for industry", "").replace("industry ", "") for c in by_carrier.index]
    _a.bar(_x - 0.2, by_carrier["with CO2"], 0.38, color=COLOR_CO2, label="with CO2 (λ_b)")
    _a.bar(_x + 0.2, by_carrier["without CO2"], 0.38, color=COLOR_WITHOUT, label="without CO2 (λ_b − γ)")
    for _i, (_w, _wo) in enumerate(zip(by_carrier["with CO2"], by_carrier["without CO2"])):
        _a.text(_i - 0.2, _w, f"{_w:.0f}", ha="center", va="bottom", fontsize=8, color="#52514e")
        _a.text(_i + 0.2, _wo, f"{_wo:.0f}", ha="center", va="bottom", fontsize=8, color="#52514e")
    _a.set_title("Load-weighted yearly price")
    _a.legend(frameon=False, fontsize=8)
    # stacked: CO2-free part + CO2 part (a negative CO2 part is drawn hatched below the top)
    _b.bar(_x, by_carrier["without CO2"], 0.6, color=COLOR_WITHOUT, label="without CO2", edgecolor="white", linewidth=2)
    _co2 = by_carrier["CO2 part"]
    _b.bar(_x, _co2, 0.6, bottom=by_carrier["without CO2"], color=COLOR_CO2, label="CO2 part γ",
           hatch=["//" if v < 0 else "" for v in _co2], edgecolor="white", linewidth=2)
    for _i, _s in enumerate(by_carrier["CO2 share"]):
        _b.text(_i, by_carrier["with CO2"].iloc[_i], f"{_s:.0%}", ha="center", va="bottom", fontsize=8, color="#52514e")
    _b.set_title("Price split: CO2-free part + CO2 part (label: CO2 share)")
    _b.legend(frameon=False, fontsize=8)
    for _ax in (_a, _b):
        _ax.set_xticks(_x, _labels, rotation=30, ha="right")
        _ax.axhline(0, color=COLOR_MUTED, linewidth=0.8)
        _ax.spines[["top", "right"]].set_visible(False)
        _ax.grid(axis="y", color="#e5e4e0", linewidth=0.6)
        _ax.set_axisbelow(True)
    _a.set_ylabel("EUR/MWh")
    _fig.suptitle(f"{year.value}, {location_mode.value}")
    _fig.tight_layout()
    mo.vstack([_fig, mo.ui.table(by_carrier.round(3).reset_index(), selection=None)])
    return


@app.cell
def _(aggregate, mo, pd, year_tables):
    # Acceptance check: reproduce the D9 values of issue #160 / PR #148 (2040, all 51 locations)
    REFERENCE_2040 = pd.DataFrame(
        {
            "with CO2": [100.61, 85.08, 72.06, 68.14, 111.94, 53.99, 121.13],
            "without CO2": [100.61, 23.23, 72.06, 68.94, 6.96, 44.71, None],
        },
        index=[
            "industry electricity",
            "gas for industry",
            "H2 for industry",
            "solid biomass for industry",
            "coal for industry",
            "naphtha for industry",
            "industry methanol",
        ],
    )
    if 2040 in year_tables:
        _calc = aggregate(year_tables[2040], "carrier").reindex(REFERENCE_2040.index)
        _chk = REFERENCE_2040.join(_calc[["with CO2", "without CO2"]], rsuffix=" (notebook)")
        _ok = all(
            (_chk[c].isna() | ((_chk[c] - _chk[f"{c} (notebook)"]).abs() < 0.005)).all()
            for c in ["with CO2", "without CO2"]
        )
        _out = mo.vstack(
            [
                mo.callout(
                    mo.md(
                        "**D9 reference values reproduced** (2040, all locations, rounded to 0.01 EUR/MWh)."
                        if _ok
                        else "**D9 reference values NOT reproduced** — check network and D9 code."
                    ),
                    kind="success" if _ok else "danger",
                ),
                mo.ui.table(_chk.round(3).reset_index(names="carrier"), selection=None),
            ]
        )
    else:
        _out = mo.md("_No 2040 network in the folder: reference check skipped._")
    _out
    return


@app.cell
def _(by_carrier, location_mode, mo, year):
    def _fmt(c):
        if c not in by_carrier.index:
            return f"`{c}`: not selected"
        r = by_carrier.loc[c]
        return f"`{c}` {r['with CO2']:.2f} → {r['without CO2']:.2f} EUR/MWh (CO2 part {r['CO2 part']:+.2f}, {r['CO2 share']:.0%})"

    def _nat_txt():
        _t = by_carrier["national CO2 part"].dropna()
        _t = _t[_t.abs() > 0.005]
        return ", ".join(f"`{c}` {v:.2f}" for c, v in _t.items()) + " EUR/MWh" if len(_t) else "nothing (limit not binding or no AT location selected)"

    mo.md(
        f"""
    **Answer ({year.value}, {location_mode.value}).** The CO2 price only enters the prices of the carriers whose
    supplying Link has a CO2 port: {_fmt("coal for industry")}; {_fmt("gas for industry")};
    {_fmt("naphtha for industry")}; {_fmt("industry methanol")}. For `solid biomass for industry` the CO2 part is
    **negative** ({_fmt("solid biomass for industry")}): the CC Link withdraws CO2 from `co2 atmosphere`
    (negative efficiency), which earns the CO2 price, so removing it makes the price higher.
    `industry electricity` and `H2 for industry` have no CO2 port at the supplying Link, so γ = 0; their price still
    contains the CO2 cost of *upstream* conversion (e.g. gas power plants), which D9 keeps.

    **Caveat (AT):** a binding national CO2 limit (`co2_limit-AT`) adds a further CO2 price to AT Links with a
    `co2 atmosphere` port that does not go through a CO2 bus, so D9 does not remove it. In the selection, the
    D9 "without CO2" price still contains on average {_nat_txt()} (Section 3, "national CO2 limits").
    """
    )
    return


@app.cell
def _(ALL_CARRIERS, carriers, mo, networks, year):
    carrier_one = mo.ui.dropdown(
        options=[c for c in ALL_CARRIERS if c in carriers.value] or ALL_CARRIERS,
        value="gas for industry" if "gas for industry" in carriers.value else (carriers.value or ALL_CARRIERS)[0],
        label="Carrier for detail plots",
    )
    _locs = sorted(networks[year.value].loads.bus.map(networks[year.value].buses.location).dropna().unique())
    location_one = mo.ui.dropdown(options=_locs, value="AT11" if "AT11" in _locs else _locs[0], label="Location for detail plots")
    mo.hstack([carrier_one, location_one], justify="start", gap=2)
    return carrier_one, location_one


@app.cell
def _(
    COLOR_CO2,
    COLOR_MUTED,
    COLOR_WITHOUT,
    aggregate,
    carrier_one,
    mo,
    n,
    plt,
    sel_tab,
):
    _t = aggregate(sel_tab[sel_tab.carrier == carrier_one.value], "location").sort_values("with CO2")
    mo.stop(_t.empty, mo.md(f"_`{carrier_one.value}` has no Load in the selected locations._"))
    _is_at = _t.index.str.startswith("AT")
    _fig, (_a, _m) = plt.subplots(1, 2, figsize=(13, 4.5), gridspec_kw={"width_ratios": [2.2, 1]})
    _a.bar(_t.index, _t["without CO2"], color=COLOR_WITHOUT, label="without CO2", edgecolor="white", linewidth=1)
    _a.bar(_t.index, _t["CO2 part"], bottom=_t["without CO2"], color=COLOR_CO2, label="CO2 part γ",
           edgecolor="white", linewidth=1)
    _a.axhline(0, color=COLOR_MUTED, linewidth=0.8)
    _a.tick_params(axis="x", rotation=90, labelsize=7)
    for _lbl, _at in zip(_a.get_xticklabels(), _is_at):
        _lbl.set_fontweight("bold" if _at else "normal")
    _a.set_ylabel("EUR/MWh")
    _a.set_title(f"{carrier_one.value}: yearly price per location (AT locations bold)")
    _a.legend(frameon=False, fontsize=8)
    _a.spines[["top", "right"]].set_visible(False)
    # map: location coordinates, colour = CO2 part
    _xy = n.buses.loc[_t.index.intersection(n.buses.index), ["x", "y"]]
    _sc = _m.scatter(_xy.x, _xy.y, c=_t.loc[_xy.index, "CO2 share"], cmap="Oranges", s=60, edgecolor="#52514e", linewidth=0.5)
    _m.scatter(_xy.x[_xy.index.str.startswith("AT")], _xy.y[_xy.index.str.startswith("AT")], s=110,
               facecolor="none", edgecolor="#0b0b0b", linewidth=1)
    _fig.colorbar(_sc, ax=_m, label="CO2 share of λ_b")
    _m.set_title("CO2 share per location (AT circled)")
    _m.set_xticks([]); _m.set_yticks([])
    _m.set_aspect("equal", adjustable="datalim")
    _fig.tight_layout()
    _at, _rest = _t[_is_at], _t[~_is_at]
    mo.vstack([
        _fig,
        mo.md(
            f"Spread of the CO2 part over the selected locations: {_t['CO2 part'].min():.2f} … {_t['CO2 part'].max():.2f} EUR/MWh "
            + (f"(AT mean {_at['CO2 part'].mean():.2f}, others {_rest['CO2 part'].mean():.2f}; unweighted means)." if len(_at) and len(_rest) else ".")
            + " A CO2 part that is the same everywhere comes from a global CO2 bus (`co2 atmosphere`); regional"
            " differences come from regional `co2 stored` / `process emissions` buses or from the CC share."
            + (f" No price (zero or no withdrawal, NaN by D9): {', '.join(_t.index[_t['with CO2'].isna()])}."
               if _t["with CO2"].isna().any() else "")
        ),
    ])
    return


@app.cell
def _(
    COLOR_CO2,
    COLOR_WITHOUT,
    carrier_one,
    load_frames,
    location_mask,
    mo,
    n,
    np,
    plt,
):
    _meta, _p, _lam, _gam = load_frames(n, [carrier_one.value])
    _sel = location_mask(_meta.location)
    _p, _lam, _gam = _p.loc[:, _sel], _lam.loc[:, _sel], _gam.loc[:, _sel]
    mo.stop(_p.shape[1] == 0, mo.md("_No Load in the selection._"))
    _w = _p.sum(axis=1)
    _with = (_p * _lam).sum(axis=1) / _w.where(_w != 0)
    _without = (_p * (_lam - _gam)).sum(axis=1) / _w.where(_w != 0)
    _g = n.snapshot_weightings.generators
    _fig, (_a, _b) = plt.subplots(1, 2, figsize=(12, 3.8))
    _a.plot(_with.index, _with, color=COLOR_CO2, linewidth=2, marker="o", markersize=4, label="λ_b (with CO2)")
    _a.plot(_without.index, _without, color=COLOR_WITHOUT, linewidth=2, marker="o", markersize=4, label="λ_b − γ (without CO2)")
    _a.set_title(f"{carrier_one.value}: Load-weighted price per snapshot")
    _a.set_ylabel("EUR/MWh")
    _a.tick_params(axis="x", rotation=30)
    for _s, _c, _lab in [(_with, COLOR_CO2, "with CO2"), (_without, COLOR_WITHOUT, "without CO2")]:
        _o = _s.sort_values(ascending=False)
        _h = np.concatenate([[0.0], np.cumsum(_g.loc[_o.index].values)])
        _b.step(_h, np.append(_o.values, _o.values[-1]), where="post", color=_c, linewidth=2, label=_lab)
    _b.set_title("Duration curve (snapshot weighting)")
    _b.set_xlabel("hours per year")
    for _ax in (_a, _b):
        _ax.legend(frameon=False, fontsize=8)
        _ax.spines[["top", "right"]].set_visible(False)
        _ax.grid(color="#e5e4e0", linewidth=0.6)
    _fig.tight_layout()
    mo.vstack([_fig, mo.md(f"{len(n.snapshots)} snapshots, weighting {sorted(_g.unique())} h. "
                           f"The CO2 part per snapshot ranges {(_with - _without).min():.2f} … {(_with - _without).max():.2f} EUR/MWh.")])
    return


@app.cell
def _(
    CARRIER_COLORS,
    aggregate,
    carriers,
    location_mask,
    location_mode,
    mo,
    pd,
    plt,
    year_tables,
):
    _rows = {}
    for _y, _tab in year_tables.items():
        _t = _tab[_tab.carrier.isin(carriers.value) & location_mask(_tab.location)]
        _rows[_y] = aggregate(_t, "carrier")
    _fig, (_a, _b) = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for _c in carriers.value:
        _with = [(_y, _r.loc[_c, "with CO2"]) for _y, _r in _rows.items() if _c in _r.index]
        _wo = [(_y, _r.loc[_c, "without CO2"]) for _y, _r in _rows.items() if _c in _r.index]
        if not _with:
            continue
        _lbl = _c.replace(" for industry", "").replace("industry ", "")
        _a.plot(*zip(*_with), marker="o", linewidth=2, color=CARRIER_COLORS[_c], label=_lbl)
        _b.plot(*zip(*_wo), marker="o", linewidth=2, color=CARRIER_COLORS[_c], label=_lbl)
    _a.set_title("with CO2")
    _b.set_title("without CO2")
    _a.set_ylabel("EUR/MWh")
    for _ax in (_a, _b):
        _ax.set_xticks(sorted(year_tables))
        _ax.spines[["top", "right"]].set_visible(False)
        _ax.grid(color="#e5e4e0", linewidth=0.6)
    _b.legend(frameon=False, fontsize=8, bbox_to_anchor=(1.02, 1), loc="upper left")
    _fig.suptitle(f"Load-weighted yearly price over investment years ({location_mode.value})")
    _fig.tight_layout()
    _co2 = {(_y): _r["CO2 part"].round(2) for _y, _r in _rows.items()}
    mo.vstack([_fig, mo.md("CO2 part γ [EUR/MWh] per investment year:"),
               mo.ui.table(pd.DataFrame(_co2).reset_index(names="carrier"), selection=None)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Network structure
    """)
    return


@app.cell
def _(ALL_CARRIERS, efficiency, is_co2_carrier, link_ports, n, pd):
    def supply_ports(n, load_carriers):
        """Long table: Load carrier × supplying Link carrier × port, with bus carrier and efficiency."""
        loads = n.loads[n.loads.carrier.isin(load_carriers)]
        sup = n.links[n.links.bus1.isin(loads.bus)]
        bus_to_load_carrier = loads.set_index("bus").carrier
        rows = []
        for k in link_ports(n):
            bk = sup[f"bus{k}"]
            bk = bk[bk.notna() & bk.ne("")]
            if bk.empty:
                continue
            eta = efficiency(n, k)[bk.index].mean() if k >= 1 else pd.Series(-1.0, index=bk.index)
            rows.append(
                pd.DataFrame(
                    {
                        "load carrier": sup.loc[bk.index, "bus1"].map(bus_to_load_carrier),
                        "link carrier": sup.loc[bk.index, "carrier"],
                        "port": f"bus{k}",
                        "bus carrier": bk.map(n.buses.carrier),
                        "efficiency": eta,
                    }
                )
            )
        long = pd.concat(rows)
        long["CO2 port"] = long["bus carrier"].map(is_co2_carrier) & (long["port"] >= "bus2")
        return long

    _long = supply_ports(n, ALL_CARRIERS)
    port_table = (
        _long.groupby(["load carrier", "link carrier", "port", "bus carrier", "CO2 port"])
        .agg(links=("efficiency", "size"), eff_min=("efficiency", "min"), eff_max=("efficiency", "max"))
        .reset_index()
    )
    return (port_table,)


@app.cell
def _(carriers, mo, port_table):
    _t = port_table[port_table["load carrier"].isin(carriers.value)].round(4)
    mo.vstack(
        [
            mo.md(
                "Supplying Links (`bus1` = industry Load bus) and their ports. `efficiency` is the snapshot mean per Link; "
                "`eff_min`/`eff_max` span the Links. `bus0` is the input (efficiency −1 by convention)."
            ),
            mo.ui.table(_t, selection=None, page_size=40),
        ]
    )
    return


@app.cell
def _(
    carrier_one,
    efficiency,
    is_co2_carrier,
    link_ports,
    location_one,
    mo,
    n,
):
    def schematic(n, load_carrier, location):
        loads = n.loads[(n.loads.carrier == load_carrier) & (n.loads.bus.map(n.buses.location) == location)]
        if loads.empty:
            return None
        b = loads.bus.iloc[0]
        sup = n.links[n.links.bus1 == b]
        ids, lines = {}, ["flowchart LR"]

        def node(name, shape="bus"):
            if name not in ids:
                ids[name] = f"n{len(ids)}"
                carrier = n.buses.carrier.get(name, "")
                cls = ":::co2" if is_co2_carrier(carrier) else ""
                lines.append(f'  {ids[name]}["{name}<br/><i>{carrier}</i>"]{cls}' if shape == "bus" else f'  {ids[name]}(["{name}"]):::link')
            return ids[name]

        load_id = "L0"
        lines.append(f'  {load_id}[/"Load {loads.index[0]}"/]:::load')
        lines.append(f"  {node(b)} --> {load_id}")
        for l, r in sup.iterrows():
            lid = node(l, "link")
            lines.append(f"  {node(r.bus0)} --> {lid}")
            for k in link_ports(n):
                if k == 0:
                    continue
                bk = r.get(f"bus{k}", "")
                if not isinstance(bk, str) or not bk:
                    continue
                eta = efficiency(n, k)[l].mean()
                lines.append(f'  {lid} -- "η{k}={eta:.3g}" --> {node(bk)}')
        lines += [
            "  classDef co2 fill:#fbe0d4,stroke:#eb6834,color:#0b0b0b",
            "  classDef link fill:#e8f0fb,stroke:#2a78d6,color:#0b0b0b",
            "  classDef load fill:#f0efec,stroke:#52514e,color:#0b0b0b",
        ]
        return "\n".join(lines)

    _m = schematic(n, carrier_one.value, location_one.value)
    mo.vstack(
        [
            mo.md(
                f"**Schematic** of `{location_one.value} {carrier_one.value}`: buses (rectangles, CO2 buses orange), "
                "supplying Links (rounded), port efficiencies on the edges (mean over snapshots). "
                "A negative efficiency means the Link withdraws from that bus."
            ),
            mo.mermaid(_m) if _m else mo.md("_No such Load._"),
        ]
    )
    return


@app.cell
def _(mo, n, pd):
    # Links with bus1 on an industry Load bus that run in reverse (p0 < 0): they enter the D9 denominator negatively
    _loads = n.loads[n.loads.carrier.str.contains("industry")]
    _sup = n.links[n.links.bus1.isin(_loads.bus)]
    _p0 = n.links_t.p0.reindex(columns=_sup.index, fill_value=0.0)
    _neg = (_p0 < -1e-6).any()
    _t = (
        pd.DataFrame({"link carrier": _sup.carrier, "bus1 carrier": _sup.bus1.map(n.buses.carrier), "reverse": _neg})
        .groupby(["bus1 carrier", "link carrier"])["reverse"]
        .agg(["size", "sum"])
        .rename(columns={"size": "links", "sum": "links with p0 < 0"})
        .reset_index()
    )
    mo.vstack(
        [
            mo.md(
                "**Check: supplying Links with negative `p0`.** D9 sums `p0·η1` over all Links with `bus1 = b`. "
                "Heat pumps in this network have `bus0` = heat and `bus1` = `low voltage` and run with `p0 < 0`, i.e. "
                "they *withdraw* from the `industry electricity` bus. They have no CO2 port, so γ stays 0 there, "
                "but the D9 denominator would be distorted on a bus that has both. Rows with `links with p0 < 0 > 0` "
                "on a bus with a CO2 port would need a spec decision."
            ),
            mo.ui.table(_t, selection=None),
        ]
    )
    return


@app.cell(expand_output=True)
def _(mo, n):
    def oil_schematic_at(n):
        """Copperplate EU oil bus in pypsa-at, summarised by carrier."""
        bus = "EU oil"
        if bus not in n.buses.index:
            return None, None
        into = n.links[n.links.bus1 == bus].carrier.value_counts()
        out = n.links[n.links.bus0 == bus].carrier.value_counts()
        gens = n.generators[n.generators.bus == bus].carrier.value_counts()
        stores = n.stores[n.stores.bus == bus].carrier.value_counts()
        lines = ["flowchart LR", '  EU["EU oil<br/><i>oil, copperplate</i>"]']
        for i, (c, k) in enumerate(into.items()):
            lines.append(f'  i{i}(["{c} ×{k}"]) --> EU')
        for i, (c, k) in enumerate(gens.items()):
            lines.append(f'  g{i}[/"Generator {c} ×{k}"/] --> EU')
        for i, (c, k) in enumerate(stores.items()):
            lines.append(f'  EU <--> s{i}[("Store {c} ×{k}")]')
        for i, (c, k) in enumerate(out.items()):
            node = f'o{i}(["{c} ×{k}"])'
            lines.append(f"  EU --> {node}")
            if c == "naphtha for industry":
                lines.append(f'  o{i} --> NI["&lt;loc&gt; naphtha for industry ×{k}"]')
                lines.append(f'  o{i} -- "η2≈0.03" --> PE["&lt;loc&gt; process emissions"]:::co2')
        lines.append("  classDef co2 fill:#fbe0d4,stroke:#eb6834,color:#0b0b0b")
        return "\n".join(lines), out

    _at, _ = oil_schematic_at(n)
    _de = """flowchart LR
      G[/"Generator DE oil primary"/] --> DP["DE oil primary"]
      DP --> R(["DE oil refining"])
      R --> DO["DE oil"]
      R -- "η2 = refining emissions" --> CA["co2 atmosphere"]:::co2
      DRL(["DE: unsustainable bioliquids, BtL, BtL CC,<br/>electrobiofuels, Fischer-Tropsch"]) --> DR["DE renewable oil"]
      ERL(["non-DE: same carriers"]) --> ER["EU renewable oil"]
      DR -- "renewable oil" --> DO
      ER -- "renewable oil (mc 0.01)" --> DO
      DR -- "renewable oil (export, can be banned)" --> EO["EU oil"]
      ER -- "renewable oil" --> EO
      DO <--> DS[("DE oil Store")]
      DO --> DC(["German consumers of EU oil<br/>(bus0 moved to DE oil)"])
      EO --> EC(["other consumers"])
      classDef co2 fill:#fbe0d4,stroke:#eb6834,color:#0b0b0b
    """
    mo.vstack(
        [
            mo.md(
                r"""
    ### Oil: pypsa-at vs. pypsa-de

    **pypsa-at** (this network): one copperplate `EU oil` bus. Every `naphtha for industry` Link takes oil from
    `EU oil` and books its CO2 at the regional `process emissions` bus (`bus2`). So the naphtha price is
    `λ(EU oil) + marginal_cost + CO2 part` — the same `EU oil` price everywhere; the CO2 part is the only
    location-dependent term (via the `process emissions` dual).
    """
            ),
            mo.mermaid(_at) if _at else mo.md("_No `EU oil` bus in this network._"),
            mo.md(
                r"""
    **pypsa-de** (`scripts/pypsa-de/modify_prenetwork.py::unravel_carbonaceous_fuels`, l.314–460, commit `a5baa7e9`):
    the EU oil bus is split into `DE oil`, `DE oil primary`, `DE renewable oil` and `EU renewable oil`. German oil
    consumers are moved from `EU oil` to `DE oil`, and `DE oil refining` carries refining emissions to
    `co2 atmosphere`. The German oil price therefore has its own dual, and part of its CO2 cost sits **upstream** in
    `λ(DE oil)` (refining), where D9 does not remove it. pypsa-de reports `Price|…|Oil` cost-based
    (`get_weighted_costs_links`), not from the bus price — the reason the Oil spec is a semantic match only.
    """
            ),
            mo.mermaid(_de),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. How is the CO2 part calculated?

    **Step 1 — nodal balance of one Link.** For a Link with input `bus0` and outputs `bus1 … busK`, the KKT
    condition of the dispatch variable `p0` is, in every snapshot where its dispatch bounds are not binding
    (`mu_upper = mu_lower = 0`; a Link at full capacity is fine as long as that capacity costs nothing),

    $$\eta_1 \lambda_{1,t} = \lambda_{0,t} + c^\text{marg} - \sum_{k \ge 2} \eta_k \lambda_{k,t} \;\; \big[ - \mu_\text{ct} \textstyle\sum_{k:\,\text{co2 atmosphere}} \eta_k \big].$$

    One MWh of input costs $\lambda_0 + c^\text{marg}$; it yields $\eta_1$ MWh at `bus1` and $\eta_k$ units at every
    other port, which are valued at $\lambda_k$. The bracket is **not** in D9: it is the dual $\mu_\text{ct}$ of a
    national CO2 limit `co2_limit-<ct>` (pypsa-de `add_national_co2_budgets`, `additional_functionality.py`
    l.406ff, commit `a5baa7e9`), which sums `p·η_k` over all Links named `<ct>…` with a `co2 atmosphere` port. It is
    a CO2 price that reaches λ_b **without passing through a CO2 bus** (see the national-CO2 cell below).

    **Step 2 — split the port sum.** Ports $k \ge 2$ are either CO2 ports (`co2 atmosphere`, `co2 stored`,
    `process emissions`, …) or energy ports (e.g. the `AC` port of CC Links). Dividing by $\eta_1$:

    $$\lambda_{1,t} = \underbrace{\frac{\lambda_{0,t} + c^\text{marg} - \sum_{k \notin \text{CO2}} \eta_k\lambda_{k,t}}{\eta_1}}_{\text{without CO2}}
    + \underbrace{\frac{\sum_{k \in \text{CO2}} (-\eta_k \lambda_{k,t})}{\eta_1}}_{\gamma_t \text{ of this Link (D9)}}
    \;\big[+ \text{national CO2 term}/\eta_1\big].$$

    CO2 duals are negative (e.g. `co2 atmosphere` ≈ −312 EUR/t in 2040), so a positive emission efficiency
    ($\eta_k > 0$) gives a positive γ: emitting costs money.

    **Step 3 — several Links on one bus.** D9 weights the per-Link γ by delivered energy $p_{0,t}\eta_1$:
    $\gamma_t(b) = \sum p_0 \sum_\text{CO2}(-\eta_k\lambda_k) / \sum p_0 \eta_1$. All Links with non-binding bounds share
    the same $\lambda_b$, but they can split it differently into CO2 and non-CO2 parts. A Link at a *costly* bound
    (e.g. a CC Link whose capacity has a capital cost) carries a capacity rent instead.

    **Step 4 — Load-weighted price.** $P = \sum_t g_t \sum p_t(\lambda_{b,t} - \gamma_t(b)) / \sum_t g_t \sum p_t$.
    """)
    return


@app.cell
def _(
    COLOR_CO2,
    COLOR_WITHOUT,
    carriers,
    efficiency,
    mo,
    n,
    national_co2_term,
    np,
    pd,
    plt,
    port_terms,
):
    def nodal_residual(n, links):
        """η1·λ1 − (λ0 + mc − Σ_{k≥2} η_k λ_k), the national CO2 term, and the mask of non-binding bounds."""
        lam = n.buses_t.marginal_price
        co2, other = port_terms(n, links)
        lam0 = lam[n.links.loc[links, "bus0"]].set_axis(links, axis=1)
        lam1 = lam[n.links.loc[links, "bus1"]].set_axis(links, axis=1)
        mc = n.get_switchable_as_dense("Link", "marginal_cost")[links]
        res = efficiency(n, 1)[links] * lam1 - (lam0 + mc + co2 + other)
        nat = national_co2_term(n, links)
        mu_u = n.links_t.mu_upper.reindex(columns=links, fill_value=0.0)
        mu_l = n.links_t.mu_lower.reindex(columns=links, fill_value=0.0)
        free = (mu_u.abs() < 1e-6) & (mu_l.abs() < 1e-6)
        return res, nat, free

    _loads = n.loads[n.loads.carrier.isin(carriers.value)]
    _links = n.links.index[n.links.bus1.isin(_loads.bus)]
    _res, _nat, _free = nodal_residual(n, _links)
    _summary = pd.DataFrame(
        {
            "link carrier": n.links.loc[_links, "carrier"],
            "AT": _links.str.startswith("AT"),
            "max |residual| D9 terms": _res.where(_free).abs().max(),
            "max |residual| + national CO2": (_res - _nat).where(_free).abs().max(),
            "checked snapshots": _free.sum(),
            "snapshots": len(n.snapshots),
        }
    ).groupby(["link carrier", "AT"]).agg(
        {"max |residual| D9 terms": "max", "max |residual| + national CO2": "max", "checked snapshots": "sum", "snapshots": "sum"}
    )
    _fig, _ax = plt.subplots(figsize=(5.5, 5))
    _r1 = _res.where(_free).stack()
    _r2 = (_res - _nat).where(_free).stack()
    _ax.hist([_r1, _r2], bins=40, color=[COLOR_CO2, COLOR_WITHOUT], label=["D9 terms only", "+ national CO2 term"])
    _ax.set_yscale("log")
    _ax.set_xlabel("residual η1·λ1 − rhs  [EUR/MWh input]")
    _ax.set_ylabel("Link-snapshots")
    _ax.set_title("Nodal balance residual (non-binding bounds)")
    _ax.legend(frameon=False, fontsize=8)
    _ax.spines[["top", "right"]].set_visible(False)
    _fig.tight_layout()
    mo.vstack(
        [
            mo.md(
                "**Per-snapshot check** of step 1 for all supplying Links of the selected carriers, in the snapshots "
                "where `mu_upper = mu_lower = 0`. Links at a costly bound (e.g. CC Links, heat pumps, distribution grid) "
                f"are left out. Residual with D9 terms only: max {np.nanmax(_r1.abs()) if len(_r1) else float('nan'):.4g}; "
                f"with the national CO2 term: max {np.nanmax(_r2.abs()) if len(_r2) else float('nan'):.2g} EUR/MWh input."
            ),
            mo.hstack([_fig, mo.ui.table(_summary.round(6).reset_index(), selection=None)], widths=[1, 1.6]),
        ]
    )
    return


@app.cell
def _(
    COLOR_CO2,
    COLOR_MUTED,
    carrier_one,
    efficiency,
    gamma,
    location_one,
    mo,
    n,
    national_co2_term,
    pd,
    plt,
    port_terms,
):
    _loads = n.loads[(n.loads.carrier == carrier_one.value) & (n.loads.bus.map(n.buses.location) == location_one.value)]
    mo.stop(_loads.empty, mo.md("_No such Load._"))
    _b = _loads.bus.iloc[0]
    _sup = n.links.index[n.links.bus1 == _b]
    _lam = n.buses_t.marginal_price
    _co2, _other = port_terms(n, _sup)
    _nat = national_co2_term(n, _sup)
    _eta1 = efficiency(n, 1)[_sup]
    _p0 = n.links_t.p0.reindex(columns=_sup, fill_value=0.0)
    _main = _p0.clip(lower=0).sum().idxmax()
    _parts = pd.DataFrame(
        {
            "λ0 / η1": _lam[n.links.at[_main, "bus0"]] / _eta1[_main],
            "marginal cost / η1": n.get_switchable_as_dense("Link", "marginal_cost")[_main] / _eta1[_main],
            "other ports / η1": _other[_main] / _eta1[_main],
            "CO2 ports / η1 (D9 γ)": _co2[_main] / _eta1[_main],
            "national CO2 limit / η1": _nat[_main] / _eta1[_main],
        }
    )
    _parts["rest (bound duals)"] = _lam[_b] - _parts.sum(axis=1)
    _colors = ["#2a78d6", "#1baf7a", "#eda100", COLOR_CO2, "#e87ba4", "#c3c2b7"]
    _fig, _ax = plt.subplots(figsize=(12, 4.3))
    _x = range(len(_parts))
    _pos = _parts.clip(lower=0).cumsum(axis=1).shift(axis=1).fillna(0)
    _neg = _parts.clip(upper=0).cumsum(axis=1).shift(axis=1).fillna(0)
    for _col, _c in zip(_parts.columns, _colors):
        _v = _parts[_col]
        _bottom = _pos[_col].where(_v >= 0, _neg[_col])
        _ax.bar(_x, _v, bottom=_bottom, color=_c, label=_col, edgecolor="white", linewidth=1)
    _ax.plot(_x, _lam[_b].values, color="#0b0b0b", marker="o", markersize=4, linewidth=1.5, label="λ_b (bus price)")
    _ax.plot(_x, (_lam[_b] - gamma(n, [_b])[_b]).values, color=COLOR_MUTED, marker="s", markersize=4, linewidth=1.5,
             linestyle="--", label="λ_b − γ_t(b) (D9)")
    _ax.axhline(0, color=COLOR_MUTED, linewidth=0.8)
    _ax.set_xticks(list(_x), [t.strftime("%m-%d") for t in _parts.index], rotation=45)
    _ax.set_ylabel("EUR/MWh delivered")
    _ax.set_title(f"Decomposition of λ_b for {_b} via its largest supplier '{_main}'")
    _ax.legend(frameon=False, fontsize=8, ncols=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    _ax.spines[["top", "right"]].set_visible(False)
    _fig.tight_layout()
    # per-Link CO2 cost per delivered MWh (delivery-weighted over the year)
    _g = n.snapshot_weightings.generators
    _deliv = (_p0 * _eta1).mul(_g, axis=0).sum()
    _per_link = pd.DataFrame(
        {
            "carrier": n.links.loc[_sup, "carrier"],
            "delivered [MWh]": _deliv,
            "share of delivery": _deliv / _deliv.sum() if _deliv.sum() else float("nan"),
            "D9 CO2 cost [EUR/MWh delivered]": (_p0 * _co2).mul(_g, axis=0).sum() / _deliv.where(_deliv != 0),
            "national CO2 cost [EUR/MWh delivered]": (_p0 * _nat).mul(_g, axis=0).sum() / _deliv.where(_deliv != 0),
        }
    )
    mo.vstack(
        [
            _fig,
            mo.md(
                "The grey `rest` closes the stack to λ_b: it is ≈ 0 when the shown Link's bounds are not binding, "
                "otherwise it is the capacity rent. Supplying Links of this bus (delivery-weighted yearly CO2 cost; "
                "D9 γ is the delivery-weighted mean of the D9 column):"
            ),
            mo.ui.table(_per_link.round(3).reset_index(names="link"), selection=None),
        ]
    )
    return


@app.cell(expand_output=True)
def _(
    COLOR_CO2,
    COLOR_WITHOUT,
    aggregate,
    carriers,
    mo,
    national_co2_duals,
    networks,
    np,
    pd,
    plt,
    year,
    year_tables,
):
    _mu = {_y: national_co2_duals(_n) for _y, _n in networks.items()}
    _tab = year_tables[year.value]
    _at = aggregate(_tab[_tab.location.str.startswith("AT") & _tab.carrier.isin(carriers.value)], "carrier")
    _at = _at.reindex([c for c in carriers.value if c in _at.index])
    _fig, _ax = plt.subplots(figsize=(10, 4))
    _x = np.arange(len(_at))
    for _off, _col, _c, _lab in [
        (-0.27, "with CO2", COLOR_CO2, "with CO2 (λ_b)"),
        (0.0, "without CO2", COLOR_WITHOUT, "without CO2 (D9)"),
        (0.27, "without CO2 incl. national", "#6250d6", "without CO2 incl. national limit"),
    ]:
        _ax.bar(_x + _off, _at[_col], 0.26, color=_c, label=_lab)
        for _xi, _v in zip(_x + _off, _at[_col]):
            _ax.text(_xi, _v, f"{_v:.0f}", ha="center", va="bottom", fontsize=7, color="#52514e")
    _ax.set_xticks(_x, [c.replace(" for industry", "").replace("industry ", "") for c in _at.index], rotation=30, ha="right")
    _ax.set_ylabel("EUR/MWh")
    _ax.set_title(f"AT locations, {year.value}: Load-weighted price with CO2, D9, and without the national CO2 limit too")
    _ax.legend(frameon=False, fontsize=8, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    _ax.spines[["top", "right"]].set_visible(False)
    _ax.grid(axis="y", color="#e5e4e0", linewidth=0.6)
    _ax.set_axisbelow(True)
    _fig.tight_layout()
    _mu_tab = pd.DataFrame(_mu).T.rename_axis("year")
    mo.vstack(
        [
            mo.md(
                r"""
    ### Special case: national CO2 limits

    Duals of `co2_limit-<ct>` in the networks [EUR/t]. A non-zero value means the national limit binds, and every
    Link named `<ct>…` with a `co2 atmosphere` port pays $-\mu_\text{ct}\,\eta_k$ per MWh input **on top of** the
    `co2 atmosphere` bus price. D9 only looks at bus duals, so this part stays in the "without CO2" price.
    `naphtha for industry` is not affected directly: its CO2 goes to `process emissions`, and the national term
    of the Link from `process emissions` to `co2 atmosphere` is already in the `process emissions` bus dual (D9
    removes it).
    """
            ),
            mo.ui.table(_mu_tab.round(3).reset_index(), selection=None),
            _fig,
            mo.ui.table(_at[["with CO2", "without CO2", "without CO2 incl. national", "national CO2 part"]].round(3).reset_index(), selection=None),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Special cases

    * **CC Links** (`gas for industry CC`, `solid biomass for industry CC`): two CO2 ports — `co2 atmosphere`
      (residual emissions) and `co2 stored` (captured CO2, positive efficiency, priced at the negative `co2 stored`
      dual, i.e. the Link *pays* for disposal capacity or earns from it depending on the sign). Both are CO2 ports
      and are removed. The fourth port (`AC`, negative efficiency) is the electricity demand of the capture unit;
      it is an energy input, not CO2, and stays in the price.
    * **Negative `co2` efficiency** of `solid biomass for industry CC`: the Link withdraws biogenic CO2 from
      `co2 atmosphere` (η₂ < 0). With a negative dual this term is $-\eta_2\lambda_2 < 0$ — a CO2 *credit* —, and
      the `co2 stored` term is positive. Net γ can be negative, so the price **without** CO2 is higher than λ_b.
    * **Several Links on one bus** (`gas for industry` + `… CC`, `solid biomass for industry` + `… CC`,
      `H2 for industry` + `methane pyrolysis plasma`): γ is the delivery-weighted mean of the per-Link CO2 cost
      (step 3). Choose a location and carrier above to see the per-Link split in the table.
    * **National CO2 limit** (`co2_limit-AT` binding, e.g. −65.4 EUR/t in 2040): an extra CO2 price on AT Links
      with a `co2 atmosphere` port that is not a bus dual, so D9 keeps it (cell "national CO2 limits" above). For
      `solid biomass for industry CC` it is a credit (negative emissions), so it *lowers* λ_b.
    * **No CO2 port** (`industry electricity`, `H2 for industry`): γ = 0 by construction. CO2 costs of upstream
      conversion (inside λ₀) are not removed.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Historical prices

    **Sources:** Eurostat `nrg_pc_205` (electricity prices for non-household consumers, bi-annual data from 2007)
    and `nrg_pc_203` (gas prices for non-household consumers, bi-annual data from 2007), years **2023–2024**
    (yearly value = unweighted mean of the semesters S1 and S2). Downloaded from the Eurostat SDMX API and
    cached in `resources/eurostat/`. Sources for coal, oil/naphtha, solid biomass and hydrogen are **still open**
    (to be agreed in #160).
    """)
    return


@app.cell
def _(REPO_ROOT, mo, pd, urllib):
    def eurostat_prices(dataset):
        """Load (download once) a Eurostat price dataset as long table [EUR/kWh]."""
        path = REPO_ROOT / "resources" / "eurostat" / f"{dataset}.tsv.gz"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = (
                "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
                f"{dataset}?format=TSV&compressed=true"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "pypsa-validation-notebook"})
            with urllib.request.urlopen(req, timeout=120) as r:
                path.write_bytes(r.read())
        df = pd.read_csv(path, sep="\t")
        key = df.columns[0]
        dims = key.split("\\")[0].split(",")
        idx = df[key].str.split(",", expand=True).set_axis(dims, axis=1)
        df = pd.concat([idx, df.drop(columns=key)], axis=1)
        df.columns = [c.strip() for c in df.columns]
        long = df.melt(id_vars=dims, var_name="period", value_name="raw")
        long["value"] = pd.to_numeric(long["raw"].str.extract(r"([-\d.]+)")[0], errors="coerce")
        long["year"] = long["period"].str[:4].astype(int)
        return long.drop(columns="raw")

    try:
        hist_raw = {"Electricity": eurostat_prices("nrg_pc_205"), "Gas": eurostat_prices("nrg_pc_203")}
        _err = None
    except Exception as e:  # network or parse error: the section stops, the rest of the notebook works
        hist_raw, _err = None, e
    mo.stop(
        hist_raw is None,
        mo.callout(mo.md(f"Eurostat download failed: `{_err}`. Put the files into `resources/eurostat/` manually."), kind="warn"),
    )
    return (hist_raw,)


@app.cell
def _(hist_raw, mo):
    def _bands(df, unit):
        return sorted(df[(df.unit == unit) & df.currency.eq("EUR")].nrg_cons.unique())

    band_el = mo.ui.dropdown(_bands(hist_raw["Electricity"], "KWH"), value="MWH20000-69999", label="Electricity band (MWh/a)")
    band_gas = mo.ui.dropdown(_bands(hist_raw["Gas"], "KWH"), value="GJ100000-999999", label="Gas band (GJ/a)")
    hist_years = mo.ui.multiselect(["2023", "2024"], value=["2023", "2024"], label="Historical years")
    hist_geo = mo.ui.multiselect(["AT", "DE", "EU27_2020"], value=["AT", "EU27_2020"], label="Regions")
    mo.hstack([band_el, band_gas, hist_years, hist_geo], justify="start", gap=1, wrap=True)
    return band_el, band_gas, hist_geo, hist_years


@app.cell
def _(band_el, band_gas, hist_geo, hist_raw, hist_years, pd):
    GAS_NCV_PER_GCV = 0.9  # IEA convention for natural gas: net calorific value ≈ 0.9 × gross

    def _hist(df, band, factor):
        d = df[
            (df.nrg_cons == band)
            & (df.unit == "KWH")
            & (df.currency == "EUR")
            & df.tax.isin(["X_TAX", "X_VAT"])
            & df.geo.isin(hist_geo.value)
            & df.year.isin([int(y) for y in hist_years.value])
        ]
        # EUR/kWh → EUR/MWh (gas: per MWh GCV → per MWh LHV)
        return (d.groupby(["geo", "tax", "year"]).value.mean() * 1000 * factor).rename("EUR/MWh")

    hist = pd.concat(
        {
            "industry electricity": _hist(hist_raw["Electricity"], band_el.value, 1.0),
            "gas for industry": _hist(hist_raw["Gas"], band_gas.value, 1 / GAS_NCV_PER_GCV),
        },
        names=["carrier"],
    ).reset_index()
    return (hist,)


@app.cell
def _(
    COLOR_CO2,
    COLOR_WITHOUT,
    aggregate,
    hist,
    mo,
    np,
    plt,
    year,
    year_tables,
):
    _tab = year_tables[year.value]
    _model = aggregate(_tab[_tab.location.str.startswith("AT")], "carrier")
    _cars = ["industry electricity", "gas for industry"]
    _hcols = sorted({(g, t) for g, t in zip(hist.geo, hist.tax)})
    _palette = ["#1baf7a", "#eda100", "#e87ba4", "#008300", "#e34948"]
    _fig, _ax = plt.subplots(figsize=(11, 4.2))
    _nb = 3 + len(_hcols)
    _wdt = 0.8 / _nb
    for _i, _c in enumerate(_cars):
        _ax.bar(_i - 0.4 + _wdt / 2, _model.loc[_c, "with CO2"] if _c in _model.index else np.nan, _wdt,
                color=COLOR_CO2, label="model AT, with CO2" if _i == 0 else None)
        _ax.bar(_i - 0.4 + 1.5 * _wdt, _model.loc[_c, "without CO2"] if _c in _model.index else np.nan, _wdt,
                color=COLOR_WITHOUT, label="model AT, without CO2 (D9)" if _i == 0 else None)
        _ax.bar(_i - 0.4 + 2.5 * _wdt, _model.loc[_c, "without CO2 incl. national"] if _c in _model.index else np.nan, _wdt,
                color="#6250d6", label="model AT, without CO2 incl. national limit" if _i == 0 else None)
        for _j, (_g, _t) in enumerate(_hcols):
            _v = hist[(hist.carrier == _c) & (hist.geo == _g) & (hist.tax == _t)]["EUR/MWh"].mean()
            _ax.bar(_i - 0.4 + (3.5 + _j) * _wdt, _v, _wdt, color=_palette[_j % len(_palette)],
                    label=f"Eurostat {_g} {_t} (mean {', '.join(sorted(map(str, hist.year.unique())))})" if _i == 0 else None)
    _ax.set_xticks(range(len(_cars)), ["Electricity [EUR/MWh_el]", "Gas [EUR/MWh_LHV]"])
    _ax.set_ylabel("EUR/MWh")
    _ax.set_title(f"Model {year.value} (AT locations, Load-weighted) vs. historical non-household prices")
    _ax.legend(frameon=False, fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")
    _ax.spines[["top", "right"]].set_visible(False)
    _ax.grid(axis="y", color="#e5e4e0", linewidth=0.6)
    _ax.set_axisbelow(True)
    _fig.tight_layout()
    mo.vstack([_fig, mo.ui.table(hist.round(2), selection=None)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Which price components are comparable?

    | Component | Model λ_b (with CO2) | Model λ_b − γ (D9) | Eurostat `X_TAX` | Eurostat `X_VAT` |
    |---|---|---|---|---|
    | Energy and supply (commodity) | yes | yes | yes | yes |
    | Network charges | only as far as grid capacity is priced in λ (marginal) | same | yes | yes |
    | Taxes, fees, levies, charges | no | no | no | yes (non-recoverable part) |
    | VAT | no | no | no | no |
    | CO2 cost of upstream conversion (e.g. power plants in the electricity price) | yes | yes | yes, via wholesale price | yes |
    | National CO2 limit dual (`co2_limit-AT`, AT Links with `co2 atmosphere` port) | yes | **yes** (not removed by D9) | no | possibly (national CO2 pricing, to verify) |
    | CO2 cost of the industry's own combustion / process emissions | **yes (γ)** | **no** | no for EU ETS installations (they surrender allowances outside the energy bill); national CO2 pricing for non-ETS users is presumably in taxes/levies (to verify) | see left |

    So the closest historical counterpart of the D9 price is `X_TAX` for **electricity**, and for **gas** the
    D9 price (without CO2) against `X_TAX`, with the caveat that `X_TAX` contains network charges that the model
    does not price. The model with CO2 corresponds to the *total* cost of an ETS installation (energy bill +
    allowances), which no Eurostat price table shows. Historical years (2023–2024) are a crisis/after-crisis
    period; the model years are 2025–2050. Eurostat gas prices are per kWh GCV; they are converted to LHV with the
    IEA convention NCV ≈ 0.9 GCV (`GAS_NCV_PER_GCV`). Model currency year: see OQ-34.
    """)
    return


if __name__ == "__main__":
    app.run()
