import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pypsa
    import pandas as pd

    return mo, pd, pypsa


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Function for Prices
    """)
    return


@app.cell
def _(pypsa):
    n = pypsa.Network("/home/maxnutz/Documents/pypsa-at-validation/pypsa-validation_processing/resources/AT_KN2040/networks/base_s_adm__none_2020.nc")

    return (n,)


@app.cell
def _(n):
    n.statistics.prices(
        bus_carrier = ["low voltage","AC"],
        groupby = False,
        groupby_time = True
    )
    return


@app.cell
def _(n):
    n.carriers[n.carriers.index.str.contains("electricity")]
    return


@app.cell
def _(n):
    n.links[n.links.carrier == "industry electricity"]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Price elements of the `Price|Final Energy|Industry|…` variables

    Network: `scenarios_industry_demand_mini`, scenario **industry_demand 100%**
    (`configs/config.scenario.industry/config.100industry_demand.yaml`), all four
    investment years. Each price variable is the Load-weighted bus marginal price
    λ of the industry Loads (D9, `utils.load_weighted_price`). This section splits λ
    into its cost elements.

    **Method (KKT price tracing).** At every snapshot, each component that supplies a
    bus *r* satisfies its LP stationarity condition (linopy sign convention,
    `mu_upper ≤ 0`, `mu_lower ≥ 0`, both stored ×`w`):

    $$\eta_r\,\lambda_r = mc \;-\; \tfrac{\mu^{upper}+\mu^{lower}}{w} \;-\; \textstyle\sum_g \mu_g c_g \;-\; \sum_{i\neq r}\eta_i\lambda_i$$

    The price of *r* is the supply-weighted mean of these identities over all its
    suppliers. Energy inputs (λ of an input bus) are traced further upstream in the
    same way, until the trace reaches generators, storage or the CO2 buses. This
    gives a linear system that is solved per snapshot. The elements add up to λ
    **exactly**, because anything the explicit terms do not cover goes into a
    labelled residual category.

    | Element | Source term | Bucket |
    |---|---|---|
    | opex: primary fuel/generation | Generator `marginal_cost` (fossil imports, biomass, …) | **opex** |
    | opex: conversion | Link `marginal_cost` (VOM) | **opex** |
    | capacity rent | bound duals `mu_upper/mu_lower`. For extendable assets, these are the capex annuity recovered in the hours the capacity binds (zero-profit). For existing or limited assets, they are a scarcity rent. | **capex** |
    | resource potential rent | KKT residual of generators with finite `e_sum_max` (biomass/biogas potentials) | scarcity of primary resource |
    | CO2 price (EU cap) | −η·λ of the ports at `co2 atmosphere` / `process emissions` (`CO2Limit`) | **emissions, overall cap** |
    | CO2 national cap (AT) | −μ(`co2_limit-AT`)·η of the CO2-atmosphere port of `AT…` links | **emissions, national cap** |
    | CO2 capture/storage value | −η·λ of the ports at `co2 stored` (sequestration limit, CO2 use) | emissions (CCS) |
    | AT EAG constraints | KKT residual of `AT…` components: `net-zero-electricity-production-AT`, `green-gas-production-AT`, `green-h2-production-AT` | national policy |
    | other | other GCs, by-product credits (CHP heat), transmission congestion, storage discharge (intertemporal value, not traced further), unattributed loops | – |
    """)
    return


@app.cell
def _(pd, pypsa):
    import numpy as np
    import scipy.sparse as sp

    PRICE_ELEMENTS = [
        "opex: primary fuel/generation",
        "opex: conversion",
        "capacity rent (capex/scarcity)",
        "resource potential rent",
        "CO2 price (EU cap)",
        "CO2 national cap (AT)",
        "CO2 capture/storage value",
        "AT EAG constraints",
        "other constraints",
        "by-product credit",
        "transmission congestion",
        "storage (intertemporal)",
        "unattributed",
    ]
    _K = {c: i for i, c in enumerate(PRICE_ELEMENTS)}
    _CO2_PORT = {
        "co2": "CO2 price (EU cap)",
        "process emissions": "CO2 price (EU cap)",
        "co2 stored": "CO2 capture/storage value",
    }
    _EPS = 1e-6

    class PriceTracer:
        """Collect supply arcs per (snapshot, bus) and trace prices upstream."""

        def __init__(self, n: pypsa.Network) -> None:
            self.n = n
            self.buses = n.buses.index
            self.bi = pd.Series(np.arange(len(self.buses)), index=self.buses)
            self.T, self.B = len(n.snapshots), len(self.buses)
            self.lam = n.buses_t.marginal_price.reindex(columns=self.buses).fillna(0.0).to_numpy()
            self.w = n.snapshot_weightings.objective.to_numpy()[:, None]
            self.W = np.zeros((self.T, self.B))
            self.D = np.zeros((self.T, self.B, len(PRICE_ELEMENTS)))
            self.arcs = []
            self.checks = []

        def idx(self, names) -> np.ndarray:
            return self.bi.reindex(names).fillna(0).astype(int).to_numpy()

        def add(self, r, inj, direct, upstream, residual_cat, comp, carrier) -> None:
            """Register arcs (arrays (T, m)); the KKT residual goes to *residual_cat*."""
            inj = np.where(np.nan_to_num(inj) > _EPS, inj, 0.0)
            t = np.broadcast_to(np.arange(self.T)[:, None], inj.shape)
            r = np.broadcast_to(r, inj.shape)
            m = inj > 0
            tt, rr, ww = t[m], r[m], inj[m]
            np.add.at(self.W, (tt, rr), ww)
            explained = np.zeros(ww.shape)
            for cat, val in direct.items():
                v = np.broadcast_to(val, inj.shape)[m]
                np.add.at(self.D, (tt, rr, _K[cat]), ww * v)
                explained += v
            for u, f in upstream:
                u = np.broadcast_to(u, inj.shape)[m]
                f = np.broadcast_to(f, inj.shape)[m]
                keep = f != 0
                self.arcs.append((tt[keep], rr[keep], u[keep], (ww * f)[keep]))
                explained += f * self.lam[tt, u]
            res = self.lam[tt, rr] - explained
            rc = np.broadcast_to(np.asarray(residual_cat), inj.shape)[m]
            np.add.at(self.D, (tt, rr, np.array([_K[c] for c in rc], dtype=int)), ww * res)
            car = np.broadcast_to(np.asarray(carrier, dtype=object), inj.shape)[m]
            self.checks.append(pd.DataFrame({"comp": comp, "carrier": car, "w": ww, "res": res, "cat": rc}))

        def solve(self, depth: int = 300, tol: float = 1e-10) -> tuple[np.ndarray, np.ndarray]:
            """Return traced elements C and direct (one-step) elements, both (T, B, K).

            Truncated series C = Σ_k A^k D; the remainder (lossless loops, e.g.
            simultaneous charge/discharge) goes to "unattributed", so Σ C = λ.
            """
            tt, rr, uu, vv = (np.concatenate([a[j] for a in self.arcs]) for j in range(4))
            C = np.zeros_like(self.D)
            direct = np.zeros_like(self.D)
            for t in range(self.T):
                has = self.W[t] > 0
                inv = np.where(has, 1.0 / np.where(has, self.W[t], 1.0), 0.0)
                m = tt == t
                A = sp.csr_matrix((vv[m] * inv[rr[m]], (rr[m], uu[m])), shape=(self.B, self.B))
                D = self.D[t] * inv[:, None]
                direct[t] = D
                term, acc = D, D.copy()
                for _ in range(depth):
                    term = A @ term
                    acc += term
                    if np.abs(term).max() < tol:
                        break
                acc[:, _K["unattributed"]] += self.lam[t] - acc.sum(axis=1)
                C[t] = acc
            return C, direct

    def _ports(df: pd.DataFrame) -> list[int]:
        return sorted(int(c[3:]) for c in df.columns if c.startswith("bus") and c[3:].isdigit())

    def _residual_cat(names: pd.Index, shape, limited=None) -> np.ndarray:
        cat = np.where(names.str.startswith("AT"), "AT EAG constraints", "other constraints")
        if limited is not None:
            cat = np.where(limited, "resource potential rent", cat)
        return np.broadcast_to(cat, shape)

    def _add_links(tr: PriceTracer, national_co2: dict[str, str]) -> None:
        n, links = tr.n, tr.n.links
        ports = _ports(links)
        p = {i: n.links_t[f"p{i}"].reindex(columns=links.index).fillna(0.0).to_numpy() for i in ports}
        p0 = np.where(np.abs(p[0]) > 1e-9, p[0], np.nan)
        eta = {i: -p[i] / p0 for i in ports}
        bus = {i: links[f"bus{i}"].where(links[f"bus{i}"].isin(tr.buses), "").to_numpy() for i in ports}
        bcar = {i: pd.Series(bus[i]).map(n.buses.carrier).fillna("").to_numpy() for i in ports}
        lam = {i: np.where(bus[i] != "", tr.lam[:, tr.idx(bus[i])], 0.0) for i in ports}
        bound = -(
            n.links_t.mu_upper.reindex(columns=links.index).fillna(0.0)
            + n.links_t.mu_lower.reindex(columns=links.index).fillna(0.0)
        ).to_numpy() / tr.w
        gc = n.global_constraints.mu
        nat = np.zeros_like(p[0])
        for gname, ct in national_co2.items():
            if gname not in gc:
                continue
            # pypsa-de add_national_co2_budgets: Link-p × eff of co2-atmosphere ports
            sel = (links.index.str[:2] == ct) & ~links.carrier.str.contains("shipping|aviation")
            for i in ports:
                nat += np.where(sel & (bus[i] == "co2 atmosphere"), -gc[gname] * np.nan_to_num(eta[i]), 0.0)
        rescat = _residual_cat(links.index, p[0].shape)
        for r in ports:
            inj = np.where(bus[r] != "", -p[r], 0.0)
            if not (inj > _EPS).any():
                continue
            er = eta[r]
            direct = {
                "opex: conversion": links.marginal_cost.to_numpy() / er,
                "capacity rent (capex/scarcity)": bound / er,
                "CO2 national cap (AT)": nat / er,
                "CO2 price (EU cap)": 0.0,
                "CO2 capture/storage value": 0.0,
                "by-product credit": 0.0,
            }
            upstream = []
            for i in ports:
                if i == r:
                    continue
                ok = bus[i] != ""
                term = np.where(ok, -eta[i] * lam[i] / er, 0.0)
                for car, cat in _CO2_PORT.items():
                    direct[cat] = direct[cat] + np.where(ok & (bcar[i] == car), term, 0.0)
                energy = ok & ~np.isin(bcar[i], list(_CO2_PORT))
                is_input = energy & (eta[i] * np.sign(p0) < 0)
                direct["by-product credit"] = direct["by-product credit"] + np.where(energy & ~is_input, term, 0.0)
                upstream.append((tr.idx(bus[i]), np.where(is_input, -eta[i] / er, 0.0)))
            direct = {k: np.nan_to_num(v) for k, v in direct.items()}
            upstream = [(u, np.nan_to_num(f)) for u, f in upstream]
            tr.add(tr.idx(bus[r]), inj, direct, upstream, rescat, "Link", links.carrier.to_numpy())

    def _add_generators(tr: PriceTracer) -> None:
        n = tr.n
        g = n.generators[(n.generators.sign > 0) & n.generators.bus.isin(tr.buses)]
        p = n.generators_t.p.reindex(columns=g.index).fillna(0.0).to_numpy()
        bound = -(
            n.generators_t.mu_upper.reindex(columns=g.index).fillna(0.0)
            + n.generators_t.mu_lower.reindex(columns=g.index).fillna(0.0)
        ).to_numpy() / tr.w
        mc = n.get_switchable_as_dense("Generator", "marginal_cost")[g.index].to_numpy()
        limited = np.isfinite(g.e_sum_max.to_numpy()) if "e_sum_max" in g else None
        tr.add(
            tr.idx(g.bus),
            p,
            {"opex: primary fuel/generation": mc, "capacity rent (capex/scarcity)": bound},
            [],
            _residual_cat(g.index, p.shape, limited),
            "Generator",
            g.carrier.to_numpy(),
        )

    def _add_storage(tr: PriceTracer) -> None:
        n = tr.n
        for comp, df, pt in [("Store", n.stores, n.stores_t.p), ("StorageUnit", n.storage_units, n.storage_units_t.p)]:
            df = df[df.bus.isin(tr.buses)]
            if df.empty:
                continue
            p = pt.reindex(columns=df.index).fillna(0.0).to_numpy()
            b = tr.idx(df.bus)
            tr.add(b, p, {"storage (intertemporal)": tr.lam[:, b]}, [],
                   np.broadcast_to("unattributed", p.shape), comp, df.carrier.to_numpy())

    def _add_branches(tr: PriceTracer) -> None:
        n = tr.n
        for comp, df, dft in [("Line", n.lines, n.lines_t), ("Transformer", n.transformers, n.transformers_t)]:
            if df.empty:
                continue
            p0 = dft.p0.reindex(columns=df.index).fillna(0.0).to_numpy()
            p1 = dft.p1.reindex(columns=df.index).fillna(0.0).to_numpy()
            b0, b1 = tr.idx(df.bus0), tr.idx(df.bus1)
            for r, u, inj in [(b1, b0, -p1), (b0, b1, -p0)]:
                cong = tr.lam[:, r] - tr.lam[:, u]
                tr.add(r, inj, {"transmission congestion": cong}, [(u, np.ones_like(inj))],
                       np.broadcast_to("unattributed", inj.shape), comp, df.carrier.to_numpy())

    def decompose_prices(n: pypsa.Network, national_co2: dict[str, str] | None = None) -> dict[str, pd.DataFrame]:
        """Return traced and direct price elements [snapshot, bus] × PRICE_ELEMENTS, plus KKT residuals."""
        national_co2 = {"co2_limit-AT": "AT"} if national_co2 is None else national_co2
        with np.errstate(all="ignore"):
            tr = PriceTracer(n)
            _add_links(tr, national_co2)
            _add_generators(tr)
            _add_storage(tr)
            _add_branches(tr)
            C, direct = tr.solve()
        idx = pd.MultiIndex.from_product([n.snapshots, tr.buses], names=["snapshot", "bus"])
        frame = lambda a: pd.DataFrame(a.reshape(-1, len(PRICE_ELEMENTS)), index=idx, columns=PRICE_ELEMENTS)
        return {"traced": frame(C), "direct": frame(direct), "residuals": pd.concat(tr.checks, ignore_index=True)}

    def load_weighted_elements(n: pypsa.Network, elements: pd.DataFrame, carriers: dict[str, str], country: str = "AT") -> pd.DataFrame:
        """Load-weighted (D9) price elements per variable for one country."""
        w = n.snapshot_weightings.objective
        rows = {}
        for var, car in carriers.items():
            loads = n.loads[(n.loads.carrier == car) & n.loads.bus.map(n.buses.location).str.startswith(country)]
            p = n.loads_t.p[loads.index].mul(w, axis=0)
            total_w = p.to_numpy().sum()
            if loads.empty or total_w <= 0:
                continue
            cost = sum(elements.xs(b, level="bus").mul(p[l], axis=0).sum() for l, b in loads.bus.items())
            rows[var] = cost / total_w
        return pd.DataFrame(rows).T

    return PRICE_ELEMENTS, decompose_prices, load_weighted_elements, np


@app.cell
def _(decompose_prices, load_weighted_elements, np, pd, pypsa):
    from pypsa_validation_processing.utils import load_weighted_price

    NETWORK_DIR = (
        "/home/maxnutz/Documents/infra-enshure/202606-coupling_workshop/"
        "mini_model_industrial_demand/industry_demand_100/networks"
    )
    YEARS = [2025, 2030, 2040, 2050]
    INDUSTRY_LOADS = {
        "Electricity": "industry electricity",
        "Gases": "gas for industry",
        "Hydrogen": "H2 for industry",
        "Solids|Biomass": "solid biomass for industry",
        "Solids|Coal": "coal for industry",
        "Liquids|Oil": "naphtha for industry",
    }

    def _d9_at(n: pypsa.Network, carrier: str) -> float:
        r = load_weighted_price(n, [carrier], True)
        r = r[r.index.get_level_values("location").str.startswith("AT")]
        if r.empty:
            return np.nan
        val, wt = r.xs("value", level="quantity"), r.xs("weight", level="quantity")
        return (val.fillna(0.0) * wt).sum() / wt.sum() if wt.sum() > 0 else np.nan

    _traced, _direct, _resid, _gc = {}, {}, {}, {}
    for _y in YEARS:
        _n = pypsa.Network(f"{NETWORK_DIR}/base_s_adm__none_{_y}.nc")
        _res = decompose_prices(_n)
        _t = load_weighted_elements(_n, _res["traced"], INDUSTRY_LOADS)
        _t["D9 price"] = pd.Series({v: _d9_at(_n, c) for v, c in INDUSTRY_LOADS.items()})
        _traced[_y] = _t
        _direct[_y] = load_weighted_elements(_n, _res["direct"], INDUSTRY_LOADS)
        _resid[_y] = _res["residuals"]
        _gc[_y] = _n.global_constraints.mu
    traced_elements = pd.concat(_traced, names=["year", "variable"])
    direct_elements = pd.concat(_direct, names=["year", "variable"])
    kkt_residuals = pd.concat(_resid, names=["year", "row"])
    global_constraint_duals = pd.DataFrame(_gc)
    return YEARS, direct_elements, global_constraint_duals, kkt_residuals, traced_elements


@app.cell
def _(PRICE_ELEMENTS, mo, traced_elements):
    _check = (traced_elements[PRICE_ELEMENTS].sum(axis=1) - traced_elements["D9 price"]).abs().max()
    mo.vstack([
        mo.md(f"""
    ## Full-chain price elements, AT, EUR_2020/MWh

    Load-weighted over all AT industry Loads and snapshots. Check: the largest
    |Σ elements − D9 price| is **{_check:.1e}** EUR/MWh. In 2050 there is no
    `coal for industry` Load, so that row is missing.
    """),
        traced_elements.round(2).T,
    ])
    return


@app.cell
def _(PRICE_ELEMENTS, pd, traced_elements):
    PRICE_BUCKETS = {
        "opex": ["opex: primary fuel/generation", "opex: conversion"],
        "capex / capacity rent": ["capacity rent (capex/scarcity)"],
        "resource potential rent": ["resource potential rent"],
        "CO2 EU cap": ["CO2 price (EU cap)"],
        "CO2 national cap AT": ["CO2 national cap (AT)"],
        "CO2 capture/storage": ["CO2 capture/storage value"],
        "AT EAG constraints": ["AT EAG constraints"],
        "storage (intertemporal)": ["storage (intertemporal)"],
        "other": ["other constraints", "by-product credit", "transmission congestion", "unattributed"],
    }
    assert sorted(sum(PRICE_BUCKETS.values(), [])) == sorted(PRICE_ELEMENTS)
    price_buckets = pd.DataFrame(
        {b: traced_elements[cols].sum(axis=1) for b, cols in PRICE_BUCKETS.items()}
    ).assign(**{"D9 price": traced_elements["D9 price"]})
    price_buckets.round(1)
    return (price_buckets,)


@app.cell
def _(YEARS, price_buckets):
    import matplotlib.pyplot as plt

    # categorical slots 1–8 (validated palette, light mode); "other" in neutral gray
    _colors = dict(zip(price_buckets.columns[:-1], [
        "#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647", "#9c9c9c",
    ]))
    _fig, _axes = plt.subplots(1, len(YEARS), figsize=(16, 4.8), sharey=True)
    for _ax, _y in zip(_axes, YEARS):
        _df = price_buckets.loc[_y]
        _x = range(len(_df))
        _pos = _df.iloc[:, :-1].clip(lower=0).cumsum(axis=1).shift(axis=1, fill_value=0)
        _neg = _df.iloc[:, :-1].clip(upper=0).cumsum(axis=1).shift(axis=1, fill_value=0)
        for _b in _colors:
            _v = _df[_b]
            _ax.bar(_x, _v, 0.6, bottom=_pos[_b].where(_v >= 0, _neg[_b]), color=_colors[_b],
                    edgecolor="white", linewidth=1, label=_b)
        _ax.scatter(_x, _df["D9 price"], marker="D", s=40, color="#1a1a1a", zorder=3, label="D9 price (total)")
        _ax.axhline(0, color="#9c9c9c", linewidth=0.8)
        _ax.set_xticks(list(_x), _df.index, rotation=45, ha="right")
        _ax.set_title(str(_y))
        _ax.grid(axis="y", color="#e6e6e6", linewidth=0.6)
        _ax.set_axisbelow(True)
        for _s in ["top", "right"]:
            _ax.spines[_s].set_visible(False)
    _axes[0].set_ylabel("EUR_2020/MWh")
    _h, _l = _axes[0].get_legend_handles_labels()
    _fig.legend(_h, _l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.12))
    _fig.suptitle("Price elements of Price|Final Energy|Industry|… (AT, industry_demand 100%)")
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(direct_elements, mo, traced_elements):
    _up = traced_elements["D9 price"] - direct_elements.sum(axis=1)
    _tab = direct_elements.loc[:, (direct_elements.abs() > 0.005).any()].assign(
        **{"upstream commodity price": _up, "D9 price": traced_elements["D9 price"]}
    )
    mo.vstack([
        mo.md("""
    ## One-step view: what is added at the industry conversion link

    Only the last step (e.g. `AT11 gas → AT11 gas for industry`). Everything before it
    is in *upstream commodity price*. This is where the **direct** end-use emissions
    show up. The full-chain table above nets them against upstream credits, e.g.
    biogenic CO2 taken from the atmosphere in biogas/BioSNG production.
    """),
        _tab.round(2).T,
    ])
    return


@app.cell(hide_code=True)
def _(global_constraint_duals, kkt_residuals, mo):
    _gc = global_constraint_duals.loc[
        ["CO2Limit", "co2_limit-AT", "co2_sequestration_limit",
         "net-zero-electricity-production-AT", "green-gas-production-AT", "green-h2-production-AT"]
    ]
    _r = kkt_residuals.assign(wr=lambda d: d.w * d.res, absw=lambda d: d.w * d.res.abs())
    _g = _r.groupby(["year", "cat"])[["w", "wr", "absw"]].sum()
    _g = _g.assign(mean_residual=_g.wr / _g.w, mean_abs_residual=_g.absw / _g.w)[["mean_residual", "mean_abs_residual"]]
    mo.vstack([
        mo.md("""
    ## Driving constraint duals and KKT residuals

    Global-constraint duals μ (the CO2 caps are in EUR/tCO2; the EAG constraints are in
    EUR/MWh of the constrained energy). Below them is the supply-weighted KKT residual
    per residual category, over all European suppliers. "unattributed" ≈ 0 shows
    that the explicit terms (mc, bound duals, CO2 ports, `co2_limit-AT`) fully explain
    storage and branch arcs.
    """),
        _gc.round(2),
        _g.round(2),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Reading the results (industry_demand 100%)

    - **Opex** is small for everything except oil, hydrogen and part of gas.
      - Oil: the `EU oil` fuel cost, plus the conversion opex of synthetic/bio liquids
        upstream (2040: ≈ 32 + 21 EUR/MWh).
      - Hydrogen (2040/2050): mostly the `import H2` generators (marginal cost
        ≈ 74 EUR/MWh), which reach AT via H2 pipelines. Note that this import price
        hides the capex of the producers abroad.
    - **Capex (capacity rent)** dominates electricity at 70–110 EUR/MWh from 2030 on.
      Of this, ≈ 30–47 EUR/MWh arise at the low-voltage bus where the industry Load
      sits (one-step table), mainly from the distribution grid AC → low voltage; the rest is generation and
      storage capacity, recovered in scarcity hours. In 2030, capex is also most of
      the hydrogen price (electrolysers).
    - **Emission costs:**
      - In 2025, only the **national AT cap** binds (μ ≈ −179 EUR/t), because the EU cap
        is not binding. It adds 0.198 × 179 ≈ 34 EUR/MWh to gas and ≈ 60 EUR/MWh to coal.
      - From 2040 on, the **EU cap** carries the CO2 price (≈ 331 EUR/t in 2040), and
        `co2_limit-AT` is almost slack. At the industry link, gas then pays
        0.198 × 331 ≈ 66 EUR/MWh (one-step table). In the full chain this is mostly
        offset by the biogenic CO2 credit of green gas, so the EU-cap element of gas
        nets to ≈ 7–10 EUR/MWh. Coal keeps the full ≈ 111 EUR/MWh.
      - Biomass: a negative EU-cap element (CO2 removal by biomass CC), offset by the
        CO2 storage cost (`co2 stored` price).
    - **AT EAG constraints** *lower* the AT electricity price by 14–58 EUR/MWh. The
      net-zero electricity constraint (μ ≈ 107 EUR/MWh in 2040) pays domestic
      renewables, and it is the electricity *consumers in P2X/heat pumps* who carry
      the constraint, not the fixed industry Load. The green-gas constraint lowers
      the gas price in the same way.
    - **Resource potential rent** (biomass/biogas `e_sum_max`) is the main element of
      the biomass price and an important part of gas (biogas) from 2040 on.
    - **storage (intertemporal)** is the value of discharged storage (gas storage,
      batteries, H2 stores). It is not traced back to the charging hours, so it is a
      mix of the other elements.
    """)
    return


if __name__ == "__main__":
    app.run()
