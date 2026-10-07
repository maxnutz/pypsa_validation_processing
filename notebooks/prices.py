import marimo

__generated_with = "0.24.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pypsa
    import pandas as pd

    return mo, pypsa


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


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
