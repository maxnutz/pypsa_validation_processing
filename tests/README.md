# Tests

Comprehensive unit and integration tests for `pypsa_validation_processing`.

## Running Tests

Run all tests:

```bash
pytest tests/ -v
```

Run tests for a specific module:

```bash
pytest tests/test_statistics_functions.py -v
pytest tests/test_network_processor.py -v
pytest tests/test_workflow.py -v
pytest tests/test_utils.py -v
```

Run with coverage:

```bash
pytest tests/ --cov=pypsa_validation_processing --cov-report=html
```

## Test Structure

### `conftest.py`
Shared pytest fixtures and mock objects:
- **`MockStatisticsAccessor`**: Mock PyPSA statistics accessor that simulates `network.statistics.energy_balance()` calls
- **`MockPyPSANetwork`**: Minimal mock PyPSA Network with required interface for statistics functions
- **`MockNetworkCollection`**: Mock collection of PyPSA networks
- **Fixtures**: Reusable fixtures for mock networks and configuration files

### `test_statistics_functions.py`
Tests for `pypsa_validation_processing/statistics_functions.py`:

**`TestFinalEnergyByCarrierElectricity`**:
- Validates return type (DataFrame)
- Checks MultiIndex structure (country, unit levels)
- Verifies non-empty results
- Confirms numeric value types
- Tests with multiple networks

**`TestFinalEnergyBySectorTransportation`**:
- Similar comprehensive coverage as electricity tests
- Validates sector-specific data extraction
- Tests multi-network processing

### `test_network_processor.py`
Tests for `pypsa_validation_processing/class_definitions.py` (`Network_Processor` class):

**`TestNetworkProcessorInit`**:
- Valid configuration initialization
- Validation of required config parameters
- `__repr__` method output

**`TestNetworkProcessorConfigReading`**:
- YAML configuration file parsing
- Path validation and error handling

**`TestNetworkProcessorFunctionExecution`**:
- Function lookup and execution
- Handling of missing functions

**`TestNetworkProcessorOutputGeneration`**:
- Output file creation
- Error handling when no data available
- Excel file generation

### `test_workflow.py`
Tests for `pypsa_validation_processing/workflow.py`:

**`TestGetDefaultConfigPath`**:
- Default config path resolution
- Path existence and format validation

**`TestResolveConfigPath`**:
- Configuration path resolution from CLI arguments
- Tilde expansion
- Path absolutization

**`TestBuildParser`**:
- ArgumentParser creation and configuration
- CLI argument handling

**`TestMainWorkflow`**:
- Main workflow execution
- Network_Processor integration

**`TestCLIBehavior`**:
- Help message generation
- Error handling for invalid arguments

### `test_utils.py`
Tests for `pypsa_validation_processing/utils.py`:

**`TestEU27CountryCodes`**:
- Dictionary structure validation
- All 27 EU member states present
- Sample country code mappings
- EU27 aggregate key presence

## Adding Tests for New Statistics Functions

When you add a new function to `pypsa_validation_processing/statistics_functions.py`, follow these steps:

### Step 1: Create the Function
Add your function to `pypsa_validation_processing/statistics_functions.py`:

```python
def My_New_IAMC_Variable(n: pypsa.Network) -> pd.DataFrame:
    """Extract IAMC variable from PyPSA Network.
    
    Parameters
    ----------
    n : pypsa.Network
        PyPSA Network to extract data from
    
    Returns
    -------
    pd.DataFrame
        DataFrame with MultiIndex including 'country' and 'unit'
    """
    # Implementation here
    result = n.statistics.energy_balance(...)
    return result.groupby(["country", "unit"]).sum()
```

### Step 2: Update the Mapping File
Add the function mapping to `pypsa_validation_processing/configs/mapping.default.yaml`:

```yaml
My New IAMC Variable: My_New_IAMC_Variable
```

### Step 3: Add Test Class
In `tests/test_statistics_functions.py`, add a new test class for your function:

```python
class TestMyNewIamcVariable:
    """Test suite for My_New_IAMC_Variable function."""

    def test_returns_dataframe(self, mock_network: MockPyPSANetwork):
        """Test that the function returns a pandas DataFrame."""
        result = My_New_IAMC_Variable(mock_network)
        assert isinstance(result, pd.DataFrame)

    def test_has_country_and_unit_index(self, mock_network: MockPyPSANetwork):
        """Test that result has country and unit in the index."""
        result = My_New_IAMC_Variable(mock_network)
        assert "country" in result.index.names
        assert "unit" in result.index.names

    def test_not_empty(self, mock_network: MockPyPSANetwork):
        """Test that result is not empty."""
        result = My_New_IAMC_Variable(mock_network)
        assert len(result) > 0

    def test_numeric_values(self, mock_network: MockPyPSANetwork):
        """Test that result values are numeric."""
        result = My_New_IAMC_Variable(mock_network)
        assert pd.api.types.is_numeric_dtype(result.dtype)

    def test_contains_austria(self, mock_network: MockPyPSANetwork):
        """Test that result contains Austria (AT) data."""
        result = My_New_IAMC_Variable(mock_network)
        assert "AT" in result.index.get_level_values("country")
```

### Step 4: Run Tests
Verify your new tests pass:

```bash
pytest tests/test_statistics_functions.py::TestMyNewIamcVariable -v
```

## Test Coverage Goals

- **statistics_functions.py**: 100% - Each function must have dedicated test class
- **Network_Processor class**: Unit tests for all public methods
- **workflow.py**: Tests for CLI argument parsing and main execution
- **utils.py**: Tests for constant definitions and mappings

## Mock Objects

The test suite uses mock PyPSA objects to avoid requiring actual network files:

- **`MockStatisticsAccessor`**: Simulates `network.statistics.energy_balance()` with realistic MultiIndex structure
- **`MockPyPSANetwork`**: Minimal network with metadata and statistics interface
- **`MockNetworkCollection`**: Iterable collection of mock networks

These mocks provide sufficient interface for testing without network file dependencies.
