![Python](https://img.shields.io/badge/python-3.11-blue)  [![license](https://img.shields.io/badge/License-MIT-blue)](https://github.com/maxnutz/pypsa_validation_processing/blob/master/LICENSE) [![pyam](https://img.shields.io/badge/pyam-iamc-blue)](https://github.com/IAMconsortium/pyam) [![Tests](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml/badge.svg)](https://github.com/maxnutz/pypsa_validation_processing/actions/workflows/test.yml)

# PyPSA-network processing for validation
This repository is licensed under the [MIT License](https://github.com/maxnutz/pypsa_validation_processing/blob/main/LICENSE)

> [!NOTE]  
> This package is currently in an **early state of development**. Expect ongoing changes and updates. Documentation and Readme will be continuously updated with changes.

This package processes a PyPSA network for a given set of defined IAMC-Variables to build a structured timeseries output and data-output to be used for model validation against the Eurostat Energy Balance. 

> [!TIP]
> The corresponding package for Eurostat Energy Balance Evaluation is available [here](https://github.com/maxnutz/eurostat-energy-balance_processing/tree/main)



## Project structure

```text
pypsa_validation_processing/
|-- workflow.py                         # CLI/entry script
|-- pypsa_validation_processing/
|   |-- workflow.py                     # package-level workflow orchestration
|   |-- class_definitions.py            # core processing classes
|   `-- configs/                        # package configuration files
|-- resources/
`-- tests/                              # test suite
```

