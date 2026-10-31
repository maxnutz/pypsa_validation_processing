# Tests

Unit tests for `pypsa_validation_processing`. They use mock PyPSA objects and temporary files only; no network files are needed. The integration run against real networks is `pixi run workflow_test`.

## Running Tests

```bash
pixi run test                                   # all tests with coverage, fails below 90 %
pixi run pytest tests/test_network_processor.py -v
pixi run pytest tests/test_network_processor.py::TestConfigValidation -v
```

## Test Files

| File | Tests for | Test classes |
|---|---|---|
| `conftest.py` | shared mocks and fixtures | `MockStatisticsAccessor` (simulates `n.statistics.energy_balance()` etc.), `MockPyPSANetwork`, `MockNetworkCollection`; fixtures `mock_network`, `mock_network_collection`, `mock_pypsa_network_with_metadata`, `temp_config_file`, `energy_totals_df` |
| `test_network_processor.py` | `Network_Processor` (`class_definitions.py`) | initialisation and config validation (`TestNetworkProcessorInit`, `TestConfigValidation`, `TestNetworkProcessorConfigReading`), network inputs (`TestGetNetworkConfig`, `TestNetworkInputs`, `TestIndustryNonEnergyShares`), function interface and result validation (`TestNetworkProcessorFunctionExecution`, `TestStatisticsFunctionInterface`, `TestResultValidation`), aggregation and post-processing (`TestNetworkProcessorAggregation`, `TestNetworkProcessorCountryAll`, `TestNetworkProcessorAggregationAndFiltering`, `TestNetworkProcessorDataPostprocessing`, `TestCalculateVariablesValuesAggregation`), output (`TestNetworkProcessorOutputGeneration`, `TestNetworkProcessorFileIO`, `TestOutputNames`) |
| `test_aggregation.py` | aggregation to countries / regions (C8) | `TestPostprocesslocationWiseMode`, `TestPostprocessTimeseriesMode`, `TestAggregationAllCountries`, `TestOutputFilenameAllCountries`, `TestPyamStructuringAllCountries`, `TestBackwardCompatibilityCountryFilter`, `TestIntensiveAggregation`, `TestCopperplateAndEuropeanUnion` |
| `test_unit_conversion.py` | unit normalisation and conversion (C9) | `TestCommonDefinitionsConfiguration`, `TestGetUnitFromCommonDefinitions`, `TestConvertUnitsToCommonDefinitions`, `TestUnitNormalisation` |
| `test_statistics_functions.py` | `statistics_functions.py` | one class per function (e.g. `TestFinalEnergyByCarrierElectricity`, `TestNetImportsOil`, `TestFinalEnergyBySectorIndustry`) and `TestAggregatePerYearFalse` |
| `test_eval_helpers.py` | `eval_helpers.py` (repository root, scenario comparison helpers) | functions with dummy network classes |
| `test_format_timestamps.py` | `class_definitions.format_timestamps` | functions |
| `test_utils.py` | constants in `utils.py` | `TestRegionsCodes` |
| `test_workflow.py` | `workflow.py` (CLI) | `TestGetDefaultConfigPath`, `TestResolveConfigPath`, `TestBuildParser`, `TestMainWorkflow`, `TestMainGuard`, `TestCLIBehavior` |
| `test_no_duplicate_test_classes.py` | the test suite itself | fails if two test classes share a name |

## Conventions

- Every test has a one-line docstring; tests for a spec acceptance criterion start with its ID, e.g. `"""C1-AC1: …"""`.
- Tests have no `-> None` return annotation.
- Prefer the mocks in `conftest.py`; patch `pypsa.NetworkCollection` and `nomenclature.DataStructureDefinition` when constructing a `Network_Processor` from a temporary config.

## Adding Tests for a New Statistics Function

Every test class for a function in `statistics_functions.py` MUST test the output format (C6, `CLAUDE.md` "Testing Rules"):

- `aggregate_per_year=True`: a `pd.Series` with a MultiIndex containing `location` and `unit`.
- `aggregate_per_year=False`: a `pd.DataFrame` with snapshots as columns and a MultiIndex containing `location` and `unit`, not a `pd.Series`.
- The MultiIndex MAY contain more levels. Values that are all zero or all NaN are valid; zero rows are not (C6.7).

```python
class TestMyNewIamcVariable:
    """Tests for My_New_IAMC_Variable."""

    def test_yearly_output_format(self, mock_network: MockPyPSANetwork):
        """C6: aggregate_per_year=True returns a Series indexed by location and unit."""
        result = My_New_IAMC_Variable(mock_network, aggregate_per_year=True)
        assert isinstance(result, pd.Series)
        assert {"location", "unit"} <= set(result.index.names)
        assert len(result) > 0

    def test_timeseries_output_format(self, mock_network: MockPyPSANetwork):
        """C6: aggregate_per_year=False returns a DataFrame with snapshot columns."""
        result = My_New_IAMC_Variable(mock_network, aggregate_per_year=False)
        assert isinstance(result, pd.DataFrame)
        assert {"location", "unit"} <= set(result.index.names)
```

Register the function in `pypsa_validation_processing/configs/mapping.default.yaml` (`My New IAMC Variable: My_New_IAMC_Variable`) and run `pixi run pytest tests/test_statistics_functions.py::TestMyNewIamcVariable -v`.
