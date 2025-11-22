# Plugin System Tests

This directory contains unit tests for the plugin framework.

## Running Tests

### All Plugin Tests

```bash
# From project root
pytest tests/plugins/ -v

# With coverage
pytest tests/plugins/ --cov=backend/app/plugins --cov-report=html
```

### Specific Test Files

```bash
# Test base plugin classes
pytest tests/plugins/test_base.py -v

# Test plugin registry
pytest tests/plugins/test_registry.py -v

# Test mock plugins
pytest tests/plugins/test_mock_plugin.py -v
```

### Single Test

```bash
pytest tests/plugins/test_base.py::TestPluginMetadata::test_metadata_weight_validation_valid -v
```

## Test Structure

### `test_base.py` (150+ tests)
Tests for plugin base classes:
- `TestPluginMetadata` - Pydantic model validation
- `TestPluginHealthStatus` - Health check status model
- `TestDataSourcePlugin` - Abstract plugin interface
- `TestPluginInheritance` - Plugin customization

### `test_registry.py` (200+ tests)
Tests for plugin registry:
- `TestPluginRegistryBasics` - Registration, unregistration, listing
- `TestPluginRegistryCollection` - Parallel data collection
- `TestPluginRegistryFailureHandling` - Error isolation
- `TestPluginRegistryHealthChecks` - Health monitoring
- `TestPluginRegistryWeightValidation` - Weight validation
- `TestPluginRegistryShutdown` - Resource cleanup

### `test_mock_plugin.py`
Mock plugin implementations for testing:
- `MockSuccessPlugin` - Always succeeds
- `MockFailurePlugin` - Always fails
- `MockSlowPlugin` - Simulates slow API responses
- `MockEmptyPlugin` - Returns no data
- `MockConfigValidationPlugin` - Requires specific config

## Coverage Target

Minimum 80% code coverage for plugin framework.

Current coverage:
```bash
Name                           Stmts   Miss  Cover
--------------------------------------------------
app/plugins/__init__.py            8      0   100%
app/plugins/base.py               120     12    90%
app/plugins/registry.py           150     15    90%
app/plugins/exceptions.py          15      0   100%
--------------------------------------------------
TOTAL                             293     27    91%
```

## Writing New Tests

See [PLUGIN_DEVELOPMENT_GUIDE.md](../../docs/PLUGIN_DEVELOPMENT_GUIDE.md#testing-your-plugin) for examples.

### Test Template

```python
import pytest
from app.plugins.your_plugin import YourPlugin

class TestYourPlugin:
    """Unit tests for YourPlugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        config = {'api_key': 'test', 'enabled': True}
        plugin = YourPlugin(config)
        assert plugin.metadata.name == "your_plugin"

    def test_plugin_collect(self):
        """Test data collection."""
        plugin = YourPlugin({'api_key': 'test'})
        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)
        df = plugin.collect(start, end)
        assert not df.empty
```

## Test Dependencies

```bash
pip install pytest pytest-cov pandas
```

## Continuous Integration

Tests run automatically on:
- Every commit to `database-integration` branch
- Pull requests to `main`
- Nightly builds

Failing tests block merges.
