# Mission

Status: draft

## Purpose
`pypsa_validation_processing` turns solved PyPSA network results into IAMC-formatted variables and writes them to Excel, so that PyPSA-AT results can be validated against IAMC-formatted reference data.

- Input: a folder of solved PyPSA networks, one per investment year (see [contracts.md](../contracts.md) C2).
- Processing: one statistics function per IAMC variable, evaluated per network (C4–C7), then aggregated (C8) and unit-converted (C9).
- Output: a `pyam.IamDataFrame` written as `.xlsx` (C10).

Sources: `README.md` (intro, "Output behavior"), `docs/index.md`, `pypsa_validation_processing/class_definitions.py::Network_Processor`.

## Users
- PyPSA-AT modellers who validate model runs (`CLAUDE.md`, "Project Context").
- Users of the PyPSA-AT Scenario Explorer, which receives the exported files (`docs/index.md`, "Scenario Explorer").
- Contributors who add statistics functions for new IAMC variables (`README.md`, "Register statistics for a new variable").

## Problem it solves
PyPSA results are organised by components, carriers and buses. Reference data, e.g. the Eurostat energy balance processed by the sister package `eurostat-energy-balance_processing` (`README.md`, tip box), is organised by IAMC variables. This package bridges the two with documented, reproducible accounting rules per variable, so both sides can be compared in the same format (`model, scenario, region, variable, unit`).

## Guiding principles
1. **Specs first.** Specs in `specs/` state intended behaviour. Where code differs, the spec wins and the difference becomes a GitHub issue (`CLAUDE.md`, "Roles").
2. **One variable, one function.** Each IAMC variable maps to exactly one stand-alone statistics function (C4, C7).
3. **Reuse proven accounting.** Statistics functions port the logic of pypsa-de's `export_ariadne_variables.py` where it evaluates the same variable ([principles.md](principles.md), P6).
4. **IAMC conformity.** Variable names and units come from the common definitions in `sister_packages/energy-scenarios-at-workflow/definitions/`.
5. **Fail early and loud.** Problems are detected as early as possible and reported visibly ([principles.md](principles.md), P5).
6. **Traceability.** Every accounting rule cites its source.

## Non-goals
- Building or solving networks (upstream PyPSA-AT / pypsa-de model logic).
- Defining or changing IAMC variable definitions (owned by `energy-scenarios-at-workflow`).
- Validation, comparison or plotting of the exported Excel files against reference data.
- Processing reference data (owned by `eurostat-energy-balance_processing`).
- Performance requirements (none documented).
