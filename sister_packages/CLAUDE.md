# Sister packages
- Related packages are placed here.
- Use packages, information is provided for a specific task
- This folder and subfolders is **read-only**
- Do not change code in `/sister_packages`

## Blueprint for statistics-functions
> Script `sister_packages/pypsa-de/scripts/pypsa-de/export_ariadne_variables.py`

Rule P6 in `specs/constitution/principles.md` is binding: for every variable this script evaluates (exact or semantic match), port its accounting logic as is (same components, carriers, bus carriers, sign conventions and special cases); use `pypsa.statistics` only for variables without a match. Deviations are allowed only as listed in the variable spec in `specs/variables/`.

func:``get_final_energy`` is too monolithic for this package's style: split the ported logic into one stand-alone function per variable, with shared helpers in `utils.py` and the output format required in file:``README.md:74``.
