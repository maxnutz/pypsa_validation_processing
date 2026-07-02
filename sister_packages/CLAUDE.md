# Sister packages
- Related packages are placed here.
- Use packages, information is provided for a specific task
- This folder and subfolders is **read-only**
- Do not change code in `/sister_packages`

## Blueprint for statistics-functions
> Script `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py`

The structure in func:``get_final_energy`` is useful as a semantic map of what should be counted for final-energy variables, but it is too monolithic for your package style. For your statistics functions, the best reuse is the accounting logic per variable, while keeping implementation modular, one-variable-per-function, and output-format-driven as required in file:``README.md:74``.
