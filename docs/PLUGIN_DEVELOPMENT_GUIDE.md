# Plugin Development Guide

**Version:** 1.0
**Last Updated:** 2025-11-21
**Audience:** Developers adding new data sources to the Traffic Safety Index system

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Plugin Architecture](#plugin-architecture)
4. [Creating a New Plugin](#creating-a-new-plugin)
5. [Testing Your Plugin](#testing-your-plugin)
6. [Registration & Configuration](#registration--configuration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Examples](#examples)

---

## Overview

The Traffic Safety Index system uses a **plugin architecture** to integrate data from multiple sources (VCC, weather, crash data, etc.). This architecture enables:

- **Adding new data sources without modifying core code**
- **Parallel data collection from multiple sources**
- **Graceful failure handling** (one plugin fails, others continue)
- **Configurable feature weights** through environment variables
- **Easy testing and maintenance**

### Key Concepts

- **Plugin**: A Python class that implements the `DataSourcePlugin` interface
- **Registry**: Manages all plugins, orchestrates parallel collection
- **Features**: Normalized (0-1 scale) values that contribute to the safety index
- **Weights**: Each plugin's contribution to the overall safety index (must sum to 1.0)

---

## Quick Start

### 1. Create Your Plugin Class

```python
# backend/app/plugins/my_plugin.py

from datetime import datetime
from typing import List
import pandas as pd

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus

class MyDataPlugin(DataSourcePlugin):
    """My custom data source plugin."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_data",
            version="1.0.0",
            description="My custom data source",
            author="Your Name",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.15)
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Fetch data from your source."""
        # TODO: Implement data collection
        data = self._fetch_from_api(start_time, end_time)

        return pd.DataFrame({
            'timestamp': data['times'],
            'my_feature_normalized': self._normalize(data['values'])
        })

    def get_features(self) -> List[str]:
        """List features this plugin provides."""
        return ['my_feature_normalized']

    def health_check(self) -> PluginHealthStatus:
        """Check if data source is accessible."""
        try:
            # Test API connection
            response = requests.get(self.api_url, timeout=5)
            return PluginHealthStatus(
                healthy=response.status_code == 200,
                message="API accessible",
                last_check=datetime.now()
            )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"Connection failed: {e}",
                last_check=datetime.now()
            )
```

### 2. Add Configuration

```bash
# backend/.env

# Enable your plugin
ENABLE_MY_DATA_PLUGIN=true
MY_DATA_PLUGIN_WEIGHT=0.15
MY_DATA_API_KEY=your_api_key_here
```

### 3. Register Your Plugin

```python
# backend/data_collector.py (or wherever plugins are registered)

from app.plugins.my_plugin import MyDataPlugin

registry = PluginRegistry()

if settings.ENABLE_MY_DATA_PLUGIN:
    my_data_config = {
        'api_key': settings.MY_DATA_API_KEY,
        'enabled': True,
        'weight': settings.MY_DATA_PLUGIN_WEIGHT
    }
    registry.register('my_data', MyDataPlugin(my_data_config))
```

---

## Plugin Architecture

### DataSourcePlugin Interface

All plugins must implement the `DataSourcePlugin` abstract base class:

```python
class DataSourcePlugin(ABC):
    def __init__(self, config: Dict[str, Any])
    def _init_metadata(self) -> PluginMetadata  # Abstract
    def collect(start_time, end_time) -> pd.DataFrame  # Abstract
    def get_features(self) -> List[str]  # Abstract
    def health_check(self) -> PluginHealthStatus  # Abstract
    def _validate_config(self) -> None  # Optional override
```

### Plugin Lifecycle

1. **Initialization**: `__init__(config)` → `_init_metadata()` → `_validate_config()`
2. **Health Check**: Called on startup and periodically for monitoring
3. **Data Collection**: Called every N seconds/minutes to fetch data
4. **Shutdown**: Cleanup resources (if needed)

### Data Flow

```
Plugin Registry
    ├─> VCC Plugin ────────┐
    ├─> Weather Plugin ────┤
    └─> Your Plugin ───────┴──> Parallel Collection
                                      │
                                      ▼
                              Merge DataFrames
                                      │
                                      ▼
                              Safety Index Calculation
                                      │
                                      ▼
                        Storage (Parquet + PostgreSQL + GCS)
```

---

## Creating a New Plugin

### Step 1: Define Requirements

Before writing code, answer these questions:

1. **What data source are you integrating?** (API, database, file, stream)
2. **What features will you provide?** (e.g., traffic volume, weather conditions)
3. **How often should data be collected?** (real-time, hourly, daily)
4. **What's the expected data volume?** (KB, MB, GB per day)
5. **What authentication is required?** (API key, OAuth, none)

### Step 2: Create Plugin File

```bash
# Create your plugin file
touch backend/app/plugins/your_plugin.py
```

### Step 3: Implement Required Methods

#### `_init_metadata()` - Plugin Identity

```python
def _init_metadata(self) -> PluginMetadata:
    """Return plugin metadata."""
    return PluginMetadata(
        name="your_plugin",           # Unique identifier
        version="1.0.0",               # Semantic versioning
        description="Brief description",
        author="Your Team",
        enabled=self.config.get('enabled', True),
        weight=self.config.get('weight', 0.15)
    )
```

**Best Practices:**
- Use lowercase with underscores for `name` (e.g., `noaa_weather`, not `NOAA-Weather`)
- Enable/weight should come from config (not hard-coded)
- Keep description concise (<80 characters)

#### `collect()` - Data Collection

```python
def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
    """
    Collect data for the specified time range.

    Args:
        start_time: Start of collection window (inclusive)
        end_time: End of collection window (exclusive)

    Returns:
        DataFrame with columns: [timestamp, feature1_normalized, feature2_normalized, ...]

    Raises:
        PluginCollectionError: If data collection fails
    """
    try:
        # 1. Fetch raw data from source
        raw_data = self._fetch_from_api(start_time, end_time)

        # 2. Parse and validate data
        if not raw_data:
            logger.warning(f"No data available for {start_time} to {end_time}")
            return pd.DataFrame()

        # 3. Transform to DataFrame
        df = pd.DataFrame(raw_data)

        # 4. Normalize features to 0-1 scale
        df['feature1_normalized'] = self._normalize_feature1(df['feature1'])
        df['feature2_normalized'] = self._normalize_feature2(df['feature2'])

        # 5. Ensure required columns
        df['timestamp'] = pd.to_datetime(df['time'])

        return df[['timestamp', 'feature1_normalized', 'feature2_normalized']]

    except Exception as e:
        raise PluginCollectionError(
            self.metadata.name,
            f"Failed to collect data: {str(e)}",
            original_error=e
        )
```

**Best Practices:**
- **Always return a DataFrame** (even if empty)
- **Normalize features to 0-1 scale** where 0 = low risk, 1 = high risk
- **Include 'timestamp' column** (datetime, timezone-aware)
- **Handle missing data gracefully** (use NaN or reasonable defaults)
- **Use exponential backoff** for API retries
- **Log warnings, not errors** for expected issues (no data available)

#### `get_features()` - Feature List

```python
def get_features(self) -> List[str]:
    """Return list of feature names this plugin provides."""
    return [
        'your_plugin_feature1',
        'your_plugin_feature2',
        'your_plugin_feature3'
    ]
```

**Best Practices:**
- **Prefix feature names** with plugin name (e.g., `weather_precipitation`, not just `precipitation`)
- **Use descriptive names** (e.g., `traffic_volume_normalized`, not `tv`)
- **Match `collect()` output columns**
- **Order doesn't matter** but should be consistent

#### `health_check()` - Connectivity Check

```python
def health_check(self) -> PluginHealthStatus:
    """Verify plugin can connect to data source."""
    start_time = time.time()

    try:
        # Lightweight check (e.g., HEAD request, ping)
        response = requests.head(self.api_url, timeout=5)

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return PluginHealthStatus(
                healthy=True,
                message="API accessible",
                last_check=datetime.now(),
                latency_ms=latency_ms
            )
        else:
            return PluginHealthStatus(
                healthy=False,
                message=f"HTTP {response.status_code}",
                last_check=datetime.now(),
                latency_ms=latency_ms
            )
    except Exception as e:
        return PluginHealthStatus(
            healthy=False,
            message=f"Connection failed: {str(e)}",
            last_check=datetime.now()
        )
```

**Best Practices:**
- **Never raise exceptions** (return unhealthy status instead)
- **Keep checks lightweight** (< 5 seconds, preferably < 1 second)
- **Include latency measurement** if possible
- **Use HEAD requests** instead of GET when possible
- **Don't fetch actual data** (save that for `collect()`)

### Step 4: Optional - Config Validation

```python
def _validate_config(self) -> None:
    """Validate plugin configuration."""
    required_keys = ['api_key', 'api_url']

    for key in required_keys:
        if key not in self.config:
            raise PluginConfigError(
                self.metadata.name,
                f"Missing required config key: '{key}'"
            )

    # Type validation
    if not isinstance(self.config['api_key'], str):
        raise PluginConfigError(
            self.metadata.name,
            "'api_key' must be a string"
        )

    # Value validation
    if len(self.config['api_key']) < 10:
        raise PluginConfigError(
            self.metadata.name,
            "'api_key' is too short (minimum 10 characters)"
        )
```

---

## Testing Your Plugin

### Unit Tests

Create tests for your plugin in `tests/plugins/test_your_plugin.py`:

```python
import pytest
from datetime import datetime
import pandas as pd

from app.plugins.your_plugin import YourPlugin
from app.plugins.exceptions import PluginCollectionError, PluginConfigError


class TestYourPlugin:
    """Unit tests for YourPlugin."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        config = {'api_key': 'test_key', 'enabled': True, 'weight': 0.15}
        plugin = YourPlugin(config)

        assert plugin.metadata.name == "your_plugin"
        assert plugin.get_weight() == 0.15

    def test_plugin_collect_success(self):
        """Test successful data collection."""
        plugin = YourPlugin({'api_key': 'test_key'})

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        df = plugin.collect(start, end)

        assert not df.empty
        assert 'timestamp' in df.columns
        assert 'your_plugin_feature1' in df.columns

    def test_plugin_collect_no_data(self):
        """Test collection when no data available."""
        plugin = YourPlugin({'api_key': 'test_key'})

        start = datetime(1970, 1, 1)  # Date with no data
        end = datetime(1970, 1, 2)

        df = plugin.collect(start, end)

        # Should return empty DataFrame, not crash
        assert df.empty

    def test_plugin_health_check_success(self):
        """Test health check when API is accessible."""
        plugin = YourPlugin({'api_key': 'test_key'})

        status = plugin.health_check()

        assert status.healthy is True
        assert status.latency_ms is not None

    def test_plugin_config_validation_missing_key(self):
        """Test config validation catches missing API key."""
        with pytest.raises(PluginConfigError):
            YourPlugin({})  # Missing 'api_key'

    def test_plugin_features_list(self):
        """Test get_features returns expected list."""
        plugin = YourPlugin({'api_key': 'test_key'})

        features = plugin.get_features()

        assert 'your_plugin_feature1' in features
        assert isinstance(features, list)
```

### Integration Tests

Test your plugin with the registry:

```python
def test_your_plugin_with_registry():
    """Test YourPlugin works with PluginRegistry."""
    registry = PluginRegistry()

    plugin = YourPlugin({'api_key': 'test_key', 'enabled': True, 'weight': 0.15})
    registry.register('your_plugin', plugin)

    start = datetime(2024, 11, 21, 10, 0)
    end = datetime(2024, 11, 21, 10, 15)

    # Should not raise errors
    data = registry.collect_all(start, end)

    assert not data.empty
```

### Manual Testing

```python
# Quick test script
python -c "
from datetime import datetime, timedelta
from app.plugins.your_plugin import YourPlugin

plugin = YourPlugin({'api_key': 'your_key'})

# Test health check
status = plugin.health_check()
print(f'Health: {status.healthy}, Message: {status.message}')

# Test data collection
end = datetime.now()
start = end - timedelta(hours=1)
df = plugin.collect(start, end)
print(f'Collected {len(df)} rows')
print(df.head())
"
```

---

## Registration & Configuration

### Add to Settings

```python
# backend/app/core/config.py

class Settings(BaseSettings):
    # ... existing settings ...

    # Your Plugin Configuration
    ENABLE_YOUR_PLUGIN: bool = Field(
        False,
        env="ENABLE_YOUR_PLUGIN",
        description="Enable Your Data Plugin"
    )
    YOUR_PLUGIN_WEIGHT: float = Field(
        0.15,
        env="YOUR_PLUGIN_WEIGHT",
        description="Weight of your plugin features in safety index"
    )
    YOUR_PLUGIN_API_KEY: str = Field(
        "",
        env="YOUR_PLUGIN_API_KEY",
        description="API key for your data source"
    )
```

### Register at Startup

```python
# backend/data_collector.py

from app.plugins.registry import PluginRegistry
from app.plugins.your_plugin import YourPlugin

def initialize_plugins() -> PluginRegistry:
    """Initialize plugin registry with all enabled plugins."""
    registry = PluginRegistry(max_workers=5)

    # Register VCC plugin
    if settings.USE_VCC_PLUGIN:
        vcc_config = {...}
        registry.register('vcc', VCCPlugin(vcc_config))

    # Register Weather plugin
    if settings.ENABLE_WEATHER_PLUGIN:
        weather_config = {...}
        registry.register('weather', NOAAWeatherPlugin(weather_config))

    # Register YOUR plugin
    if settings.ENABLE_YOUR_PLUGIN:
        your_config = {
            'api_key': settings.YOUR_PLUGIN_API_KEY,
            'enabled': True,
            'weight': settings.YOUR_PLUGIN_WEIGHT
        }
        registry.register('your_plugin', YourPlugin(your_config))

    # Validate weights sum to 1.0
    validation = registry.validate_weights()
    if not validation['valid']:
        logger.warning(f"Plugin weights sum to {validation['total_weight']}, expected 1.0")

    return registry
```

### Update Environment

```bash
# backend/.env

ENABLE_YOUR_PLUGIN=true
YOUR_PLUGIN_WEIGHT=0.15
YOUR_PLUGIN_API_KEY=your_api_key_here
```

---

## Best Practices

### Data Collection

1. **Use Exponential Backoff for Retries**
   ```python
   def _fetch_with_retry(self, url, max_retries=3):
       for attempt in range(max_retries):
           try:
               return requests.get(url, timeout=10)
           except requests.RequestException:
               if attempt < max_retries - 1:
                   delay = 2 ** attempt  # 1s, 2s, 4s
                   time.sleep(delay)
               else:
                   raise
   ```

2. **Normalize Features Consistently**
   ```python
   def _normalize_feature(self, raw_values, min_val, max_val):
       """Normalize to 0-1 scale where 0=low risk, 1=high risk."""
       normalized = (raw_values - min_val) / (max_val - min_val)
       return normalized.clip(0, 1)  # Ensure 0-1 range
   ```

3. **Handle Time Zones Properly**
   ```python
   import pytz

   def collect(self, start_time, end_time):
       # Ensure timezone-aware datetimes
       if start_time.tzinfo is None:
           start_time = pytz.utc.localize(start_time)
       # ...
   ```

4. **Log Appropriately**
   ```python
   import logging
   logger = logging.getLogger(__name__)

   # Info: Normal operations
   logger.info(f"Collected {len(df)} observations from {start_time} to {end_time}")

   # Warning: Expected issues
   logger.warning(f"No data available for {date}")

   # Error: Unexpected issues (with stack trace)
   logger.error(f"API request failed: {e}", exc_info=True)
   ```

### Performance

1. **Batch Requests** - Fetch multiple time periods in one API call
2. **Cache Results** - Avoid re-fetching the same data
3. **Use Connection Pooling** - Reuse HTTP connections
4. **Limit Data Volume** - Only fetch necessary fields/columns

### Security

1. **Never Log Credentials**
   ```python
   # BAD
   logger.info(f"Using API key: {api_key}")

   # GOOD
   logger.info(f"Using API key: {api_key[:4]}...")
   ```

2. **Validate Input Data**
   ```python
   def _validate_data(self, df):
       # Check for SQL injection attempts
       if df['column'].str.contains(';|--').any():
           raise ValueError("Suspicious data detected")
   ```

3. **Use Environment Variables for Secrets**
   ```python
   # Store in .env, not hard-coded
   api_key = settings.YOUR_PLUGIN_API_KEY  # ✓
   api_key = "hardcoded_key_123"           # ✗
   ```

---

## Troubleshooting

### Common Issues

#### Plugin Not Collecting Data

**Symptoms:**
- `collect()` returns empty DataFrame
- No errors in logs

**Solutions:**
1. Check if plugin is enabled: `ENABLE_YOUR_PLUGIN=true`
2. Verify time range has data
3. Test API manually with curl/Postman
4. Check API rate limiting
5. Verify authentication credentials

#### Weight Validation Fails

**Symptoms:**
- Warning: "Plugin weights sum to 0.85, expected 1.0"

**Solutions:**
1. Adjust plugin weights to sum to 1.0:
   ```bash
   VCC_PLUGIN_WEIGHT=0.70
   WEATHER_PLUGIN_WEIGHT=0.15
   YOUR_PLUGIN_WEIGHT=0.15
   # Total: 1.00
   ```

2. Or disable one plugin:
   ```bash
   ENABLE_WEATHER_PLUGIN=false
   VCC_PLUGIN_WEIGHT=0.85
   YOUR_PLUGIN_WEIGHT=0.15
   ```

#### Health Check Always Fails

**Symptoms:**
- `health_check()` returns `healthy=False`
- Plugin disabled by monitoring system

**Solutions:**
1. Test API connectivity manually
2. Check firewall/network rules
3. Increase timeout in health_check
4. Verify API endpoint URL is correct

#### Plugin Crashes Other Plugins

**Symptoms:**
- All plugins fail when yours is enabled
- Errors in other plugins' logs

**Solutions:**
1. Ensure `collect()` doesn't raise unhandled exceptions
2. Wrap all external calls in try/except
3. Return empty DataFrame instead of raising errors
4. Check for resource leaks (unclosed connections)

### Debug Mode

Enable debug logging for your plugin:

```python
# backend/app/plugins/your_plugin.py

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class YourPlugin(DataSourcePlugin):
    def collect(self, start_time, end_time):
        logger.debug(f"Starting collection for {start_time} to {end_time}")
        # ...
        logger.debug(f"Fetched {len(data)} records from API")
        # ...
        logger.debug(f"Returning DataFrame with {len(df)} rows, {len(df.columns)} columns")
        return df
```

---

## Examples

### Example 1: Simple REST API Plugin

```python
# backend/app/plugins/rest_api_plugin.py

import requests
from datetime import datetime
from typing import List
import pandas as pd

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus

class SimpleRESTPlugin(DataSourcePlugin):
    """Example plugin for a simple REST API."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="rest_api",
            version="1.0.0",
            description="Simple REST API data source",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.10)
        )

    def __init__(self, config):
        super().__init__(config)
        self.api_url = config['api_url']
        self.api_key = config.get('api_key')

    def collect(self, start_time, end_time):
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat()
        }

        response = requests.get(self.api_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        return pd.DataFrame({
            'timestamp': pd.to_datetime([d['time'] for d in data]),
            'rest_feature_normalized': [d['value'] / 100.0 for d in data]
        })

    def get_features(self):
        return ['rest_feature_normalized']

    def health_check(self):
        try:
            response = requests.head(self.api_url, timeout=5)
            return PluginHealthStatus(
                healthy=response.status_code == 200,
                message="API accessible",
                last_check=datetime.now()
            )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=str(e),
                last_check=datetime.now()
            )
```

### Example 2: Database Plugin

```python
# backend/app/plugins/database_plugin.py

from datetime import datetime
from typing import List
import pandas as pd
import psycopg2

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus

class DatabasePlugin(DataSourcePlugin):
    """Example plugin for PostgreSQL database."""

    def _init_metadata(self):
        return PluginMetadata(
            name="database",
            description="PostgreSQL database data source",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.10)
        )

    def __init__(self, config):
        super().__init__(config)
        self.connection_string = config['connection_string']
        self.table_name = config['table_name']

    def collect(self, start_time, end_time):
        query = f"""
            SELECT timestamp, feature_value
            FROM {self.table_name}
            WHERE timestamp >= %s AND timestamp < %s
            ORDER BY timestamp
        """

        with psycopg2.connect(self.connection_string) as conn:
            df = pd.read_sql_query(query, conn, params=[start_time, end_time])

        df['db_feature_normalized'] = df['feature_value'] / df['feature_value'].max()

        return df[['timestamp', 'db_feature_normalized']]

    def get_features(self):
        return ['db_feature_normalized']

    def health_check(self):
        try:
            with psycopg2.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return PluginHealthStatus(
                healthy=True,
                message="Database accessible",
                last_check=datetime.now()
            )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"Database error: {e}",
                last_check=datetime.now()
            )
```

---

## Additional Resources

- **Plugin Base Class**: `backend/app/plugins/base.py`
- **Plugin Registry**: `backend/app/plugins/registry.py`
- **Mock Plugins (for testing)**: `tests/plugins/test_mock_plugin.py`
- **Unit Tests Examples**: `tests/plugins/test_base.py`, `tests/plugins/test_registry.py`

---

## Getting Help

If you encounter issues or have questions:

1. **Check existing plugins** (VCC, Weather) for examples
2. **Review unit tests** for expected behavior
3. **Enable debug logging** to troubleshoot
4. **Ask the team** in #traffic-safety Slack channel

---

**Happy Plugin Development!** 🚀
