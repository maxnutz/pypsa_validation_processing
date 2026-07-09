# PyPSA Validation Processing

This package processes PyPSA network results into IAMC-formatted variables for validation against the Eurostat Energy Balance, as part of the PyPSA-AT project.

## Scenario Explorer

Processed output from this package is intended for submission to the [PyPSA-AT Scenario Explorer](https://pypsa-at-dev.apps.ece.iiasa.ac.at/). Submitting to the Explorer requires registering a user account on the site.

Keep the following in mind when preparing a submission:

- **Model name:** the Explorer only accepts model names starting with `"Pypsa-AT v1.0"`. The `model_name` value in your config must exactly match one of the models defined in the [pypsa-at-dev-workflow mappings file](https://github.com/iiasa/pypsa-at-dev-workflow/blob/d71aab41172992f020a3fb149b166dee548a4543/mappings/pypsa-at_v1.x.yaml#L2) — set it accordingly in `config.default.yaml` (or your own config) before running the workflow.
- **Submission time:** large files can take a while to process; you will be notified by e-mail once the submission succeeds.
- **Output format:** this package's exported Excel files are already formatted to fit Explorer submission requirements. A few config flags directly affect whether a submission validates:
  - `convert_units` — converts PyPSA units to the IAMC-valid units expected by the Explorer.
  - `map_country_codes_to_names` — controls whether output regions use country codes (`AT`) or full names (`Austria`); make sure this matches what the Explorer expects for your submission.
  - `aggregation_level` — controls whether output rows are aggregated to `country` or kept at `region` granularity.

## API Reference

Use the API Reference section (nav) for the automatically rendered module documentation.

## Contributing

See [Contributing](contributing.md) for coding-style and participation guidelines.
