# Sprint Plan: Data Integration & Extensibility

**Sprint Goal:** Implement pluggable data source architecture with NOAA weather integration

**Duration:** 6 weeks (30 working days)
**Team:** 1-2 developers
**Estimated Effort:** 180-220 hours
**Priority:** High
**Status:** Planning

---

## Sprint Overview

This sprint implements a production-grade plugin architecture for data source extensibility, refactors VCC as a plugin, integrates NOAA/NWS weather data, and provides UI transparency for safety index calculations.

### Success Criteria
- [ ] Plugin architecture supports adding new data sources without code changes
- [ ] VCC refactored as plugin with zero data loss
- [ ] Weather data integrated with ≥5% improvement in crash prediction accuracy
- [ ] UI displays safety index formula breakdown
- [ ] <5% performance overhead from plugin architecture
- [ ] Historical weather data backfilled for all existing traffic data

---

## Dependencies

### Prerequisites
- ✅ PostgreSQL migration Phase 3 complete (triple-write working)
- ✅ Frontend dashboard accessible and deployed
- ⏳ Historical crash data available for validation
- ⏳ NOAA weather station identified (default: KRIC - Richmond Intl Airport)

### External Dependencies
- NOAA/NWS API (free, public, no authentication required)
- PostgreSQL 15+ with sufficient storage for weather data
- Frontend team availability for UI components (Week 5)

---

## Phase 1: Plugin Architecture Foundation (Days 1-5, 35 hours)

**Goal:** Build the core plugin framework without touching existing data collection.

### Task 1.1: Plugin Base Classes & Interfaces ✅ Ready to Start
**Time:** 8 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/app/plugins/__init__.py`
- `backend/app/plugins/base.py`
- `backend/app/plugins/exceptions.py`

**Implementation:**
```python
# backend/app/plugins/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from pydantic import BaseModel, Field

class PluginMetadata(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str
    author: str
    enabled: bool = True
    weight: float = Field(ge=0.0, le=1.0, default=0.0)

class PluginHealthStatus(BaseModel):
    healthy: bool
    message: str
    last_check: datetime
    latency_ms: Optional[float] = None

class DataSourcePlugin(ABC):
    """Abstract base class for all data source plugins"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metadata = self._init_metadata()
        self._validate_config()

    @abstractmethod
    def _init_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass

    @abstractmethod
    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Collect data for time range"""
        pass

    @abstractmethod
    def get_features(self) -> List[str]:
        """Return list of feature names this plugin provides"""
        pass

    @abstractmethod
    def health_check(self) -> PluginHealthStatus:
        """Verify plugin can connect to data source"""
        pass
```

**Testing:**
- [  ] Unit tests for abstract base class
- [  ] Pydantic model validation tests
- [  ] Mock plugin implementation for testing
- [  ] Coverage ≥90% for base.py

**Acceptance Criteria:**
- ✅ `DataSourcePlugin` abstract class with all required methods
- ✅ `PluginMetadata` and `PluginHealthStatus` Pydantic models
- ✅ Custom exception classes (PluginCollectionError, PluginConfigError)
- ✅ Type hints for all methods
- ✅ Comprehensive docstrings

**Dependencies:** None

---

### Task 1.2: Plugin Registry Implementation ✅ Ready to Start
**Time:** 12 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/app/plugins/registry.py`

**Implementation:**
```python
# backend/app/plugins/registry.py
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

class PluginRegistry:
    """Centralized registry for managing data source plugins"""

    def __init__(self, max_workers: int = 5):
        self.plugins: Dict[str, DataSourcePlugin] = {}
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def register(self, name: str, plugin: DataSourcePlugin):
        """Register a plugin instance"""
        if name in self.plugins:
            raise ValueError(f"Plugin '{name}' already registered")
        self.plugins[name] = plugin

    def collect_all(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Collect data from all enabled plugins in parallel"""
        # Parallel collection with ThreadPoolExecutor
        # Merge results with outer join on timestamp
        pass

    def health_check_all(self) -> Dict[str, PluginHealthStatus]:
        """Run health checks on all plugins"""
        pass

    def validate_weights(self) -> Dict[str, Any]:
        """Validate that enabled plugin weights sum to 1.0"""
        pass
```

**Testing:**
- [  ] Register multiple plugins
- [  ] Parallel collection from 3+ plugins
- [  ] Plugin failure doesn't crash registry
- [  ] Weight validation (sum to 1.0)
- [  ] Health check aggregation
- [  ] Data merge strategy (outer join)

**Acceptance Criteria:**
- ✅ Registry can manage multiple plugins
- ✅ Parallel collection with ThreadPoolExecutor
- ✅ Graceful failure handling (one plugin fails, others continue)
- ✅ Weight validation with 1% tolerance
- ✅ Thread-safe operations

**Dependencies:** Task 1.1 complete

---

### Task 1.3: Configuration Management ✅ Ready to Start
**Time:** 6 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Modify:**
- `backend/app/core/config.py`
- `backend/.env.example`
- `docker-compose.yml`

**Environment Variables:**
```bash
# Data Plugin Configuration
ENABLE_DATA_PLUGINS=false  # Feature flag

# VCC Plugin (refactored)
USE_VCC_PLUGIN=false
VCC_PLUGIN_WEIGHT=0.70

# Weather Plugin
ENABLE_WEATHER_PLUGIN=false
WEATHER_PLUGIN_WEIGHT=0.15
WEATHER_STATION_ID=KRIC
WEATHER_API_BASE=https://api.weather.gov
WEATHER_API_TIMEOUT=10
WEATHER_RETRY_ATTEMPTS=3
```

**Implementation:**
```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Plugin System
    ENABLE_DATA_PLUGINS: bool = Field(False, env="ENABLE_DATA_PLUGINS")

    # VCC Plugin
    USE_VCC_PLUGIN: bool = Field(False, env="USE_VCC_PLUGIN")
    VCC_PLUGIN_WEIGHT: float = Field(0.70, env="VCC_PLUGIN_WEIGHT")

    # Weather Plugin
    ENABLE_WEATHER_PLUGIN: bool = Field(False, env="ENABLE_WEATHER_PLUGIN")
    WEATHER_PLUGIN_WEIGHT: float = Field(0.15, env="WEATHER_PLUGIN_WEIGHT")
    WEATHER_STATION_ID: str = Field("KRIC", env="WEATHER_STATION_ID")
    WEATHER_API_BASE: str = Field("https://api.weather.gov", env="WEATHER_API_BASE")
    WEATHER_API_TIMEOUT: int = Field(10, env="WEATHER_API_TIMEOUT")
    WEATHER_RETRY_ATTEMPTS: int = Field(3, env="WEATHER_RETRY_ATTEMPTS")

    @validator('VCC_PLUGIN_WEIGHT', 'WEATHER_PLUGIN_WEIGHT')
    def validate_weight(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {v}")
        return v
```

**Testing:**
- [  ] Load configuration from environment
- [  ] Weight validation (0.0-1.0 range)
- [  ] Feature flags work correctly
- [  ] Docker environment variable passthrough

**Acceptance Criteria:**
- ✅ All plugin configuration loaded from environment
- ✅ Pydantic validation for weights
- ✅ Feature flags for gradual rollout
- ✅ Documentation in `.env.example`

**Dependencies:** Task 1.1 complete

---

### Task 1.4: Database Schema for Weather Data ✅ Ready to Start
**Time:** 5 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/db/migrations/003_add_weather_tables.sql`

**Schema:**
```sql
-- Weather observations table
CREATE TABLE weather_observations (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(10) NOT NULL,
    observation_time TIMESTAMPTZ NOT NULL,

    -- Raw measurements
    temperature_c FLOAT,
    precipitation_mm FLOAT,
    visibility_m FLOAT,
    wind_speed_ms FLOAT,
    wind_direction_deg INT CHECK (wind_direction_deg >= 0 AND wind_direction_deg < 360),
    weather_condition VARCHAR(100),

    -- Normalized features (0-1 scale)
    temperature_normalized FLOAT CHECK (temperature_normalized >= 0 AND temperature_normalized <= 1),
    precipitation_normalized FLOAT CHECK (precipitation_normalized >= 0 AND precipitation_normalized <= 1),
    visibility_normalized FLOAT CHECK (visibility_normalized >= 0 AND visibility_normalized <= 1),
    wind_speed_normalized FLOAT CHECK (wind_speed_normalized >= 0 AND wind_speed_normalized <= 1),

    -- Raw API response for debugging
    raw_json JSONB,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(station_id, observation_time)
);

-- Indexes
CREATE INDEX idx_weather_obs_time ON weather_observations(observation_time);
CREATE INDEX idx_weather_obs_station ON weather_observations(station_id);
CREATE INDEX idx_weather_obs_created ON weather_observations(created_at);

-- Partitioning (monthly, same as safety_indices_realtime)
-- Will be implemented separately

-- Plugin configuration table
CREATE TABLE data_source_plugins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    enabled BOOLEAN DEFAULT true,
    weight FLOAT DEFAULT 0.0 CHECK (weight >= 0.0 AND weight <= 1.0),
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Extend safety_indices_realtime for weather features
ALTER TABLE safety_indices_realtime
    ADD COLUMN IF NOT EXISTS weather_precipitation_normalized FLOAT CHECK (weather_precipitation_normalized >= 0 AND weather_precipitation_normalized <= 1),
    ADD COLUMN IF NOT EXISTS weather_visibility_normalized FLOAT CHECK (weather_visibility_normalized >= 0 AND weather_visibility_normalized <= 1),
    ADD COLUMN IF NOT EXISTS weather_wind_speed_normalized FLOAT CHECK (weather_wind_speed_normalized >= 0 AND weather_wind_speed_normalized <= 1),
    ADD COLUMN IF NOT EXISTS weather_temperature_normalized FLOAT CHECK (weather_temperature_normalized >= 0 AND weather_temperature_normalized <= 1),
    ADD COLUMN IF NOT EXISTS vcc_contribution FLOAT,
    ADD COLUMN IF NOT EXISTS weather_contribution FLOAT,
    ADD COLUMN IF NOT EXISTS formula_version VARCHAR(20) DEFAULT 'v2.0';
```

**Testing:**
- [  ] Schema applies cleanly to test database
- [  ] Constraints enforce valid data ranges
- [  ] Indexes improve query performance
- [  ] Unique constraint prevents duplicates

**Acceptance Criteria:**
- ✅ `weather_observations` table created
- ✅ `data_source_plugins` table created
- ✅ `safety_indices_realtime` extended with weather columns
- ✅ Proper indexes for performance
- ✅ Check constraints for data validation

**Dependencies:** None (can run in parallel with Task 1.1-1.3)

---

### Task 1.5: Plugin Unit Tests & Documentation ✅ Ready to Start
**Time:** 4 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `tests/plugins/test_base.py`
- `tests/plugins/test_registry.py`
- `tests/plugins/test_mock_plugin.py`
- `docs/PLUGIN_DEVELOPMENT_GUIDE.md`

**Testing:**
```python
# tests/plugins/test_base.py
def test_plugin_metadata_validation():
    """Test Pydantic validation of plugin metadata"""
    pass

def test_plugin_abstract_methods():
    """Ensure abstract methods raise NotImplementedError"""
    pass

# tests/plugins/test_registry.py
def test_register_multiple_plugins():
    """Test registering multiple plugins"""
    pass

def test_parallel_collection():
    """Test parallel data collection from 3 plugins"""
    pass

def test_plugin_failure_isolation():
    """Ensure one plugin failure doesn't crash others"""
    pass

def test_weight_validation():
    """Test weight sum validation"""
    pass
```

**Documentation:**
```markdown
# Plugin Development Guide

## Creating a New Data Source Plugin

1. Create a new file: `backend/app/plugins/your_plugin.py`
2. Implement the `DataSourcePlugin` interface
3. Register your plugin in `data_collector.py`
4. Add configuration to `.env`
5. Write tests

## Example: Simple Weather Plugin

[Full working example with code]

## Best Practices

- Always handle API failures gracefully
- Normalize features to 0-1 scale
- Include health checks
- Document your feature meanings
```

**Acceptance Criteria:**
- ✅ Unit test coverage ≥85%
- ✅ All edge cases tested
- ✅ Plugin development guide complete
- ✅ Code examples work

**Dependencies:** Tasks 1.1-1.2 complete

---

## Phase 2: VCC Plugin Refactoring (Days 6-10, 30 hours)

**Goal:** Refactor existing VCC client as a plugin without breaking production.

### Task 2.1: VCC Plugin Implementation ✅ Ready after Phase 1
**Time:** 10 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/app/plugins/vcc_plugin.py`

**Implementation Strategy:**
1. Copy existing VCC logic into plugin structure
2. Implement `DataSourcePlugin` interface
3. Keep existing `VCCClient` intact (dual implementation)
4. Add feature flag to switch between old/new

**Code:**
```python
# backend/app/plugins/vcc_plugin.py
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from app.services.vcc_client import VCCClient
from app.services.vcc_feature_engineering import (
    extract_bsm_features,
    extract_psm_features,
    detect_vru_vehicle_conflicts,
    detect_vehicle_vehicle_conflicts
)

class VCCPlugin(DataSourcePlugin):
    """VCC data source plugin"""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="vcc",
            version="1.0.0",
            description="Virginia Connected Corridors traffic data source",
            author="Traffic Safety Team",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.70)
        )

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = VCCClient(
            base_url=config.get('base_url'),
            client_id=config.get('client_id'),
            client_secret=config.get('client_secret')
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Collect VCC data and extract features"""
        # Fetch raw messages
        bsm_messages = self.client.fetch_bsm_messages(start_time, end_time)
        psm_messages = self.client.fetch_psm_messages(start_time, end_time)
        mapdata = self.client.fetch_mapdata()

        if not bsm_messages:
            return pd.DataFrame()

        # Extract features (reuse existing logic)
        bsm_features = extract_bsm_features(bsm_messages)
        psm_features = extract_psm_features(psm_messages) if psm_messages else pd.DataFrame()

        # Detect conflicts
        vru_conflicts = detect_vru_vehicle_conflicts(bsm_messages, psm_messages, mapdata)
        veh_conflicts = detect_vehicle_vehicle_conflicts(bsm_messages, mapdata)

        # Merge features
        features = self._merge_features(bsm_features, psm_features, vru_conflicts, veh_conflicts)
        features['timestamp'] = pd.to_datetime(features['time_15min'])

        return features

    def get_features(self) -> List[str]:
        return [
            'vcc_conflict_count',
            'vcc_ttc_min',
            'vcc_proximity_score',
            'vcc_speed_variance',
            'vcc_acceleration_events'
        ]

    def health_check(self) -> PluginHealthStatus:
        """Verify VCC API is accessible"""
        try:
            token = self.client.get_access_token()
            if token:
                return PluginHealthStatus(
                    healthy=True,
                    message="VCC API authentication successful",
                    last_check=datetime.now()
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message="Failed to obtain access token",
                    last_check=datetime.now()
                )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"VCC API error: {str(e)}",
                last_check=datetime.now()
            )
```

**Testing:**
- [  ] VCC plugin collects same data as legacy VCCClient
- [  ] Feature parity (all existing features present)
- [  ] Health check works
- [  ] Performance comparable to legacy

**Acceptance Criteria:**
- ✅ VCCPlugin implements all DataSourcePlugin methods
- ✅ Reuses existing VCC feature engineering code
- ✅ No functionality lost
- ✅ Health check validates OAuth2 authentication

**Dependencies:** Phase 1 complete

---

### Task 2.2: Dual-Collection Validation ✅ Ready after Task 2.1
**Time:** 8 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Modify:**
- `backend/data_collector.py`

**Implementation:**
```python
# backend/data_collector.py
class DataCollector:
    def __init__(self, ...):
        # ... existing initialization ...

        # Feature flag: use plugin or legacy client
        self.use_vcc_plugin = settings.USE_VCC_PLUGIN

        if self.use_vcc_plugin:
            # Initialize plugin registry
            self.plugin_registry = PluginRegistry()
            vcc_config = {
                'base_url': settings.VCC_BASE_URL,
                'client_id': settings.VCC_CLIENT_ID,
                'client_secret': settings.VCC_CLIENT_SECRET,
                'enabled': True,
                'weight': settings.VCC_PLUGIN_WEIGHT
            }
            self.plugin_registry.register('vcc', VCCPlugin(vcc_config))

    def collect_cycle(self) -> bool:
        if settings.DUAL_COLLECTION_VALIDATION:
            # Run BOTH legacy and plugin, compare results
            legacy_data = self._collect_legacy()
            plugin_data = self._collect_plugin()
            self._compare_results(legacy_data, plugin_data)
        elif self.use_vcc_plugin:
            # Use plugin only
            data = self._collect_plugin()
        else:
            # Use legacy only (current production)
            data = self._collect_legacy()

    def _compare_results(self, legacy: pd.DataFrame, plugin: pd.DataFrame):
        """Compare legacy vs plugin output for validation"""
        # Check row counts match
        assert len(legacy) == len(plugin), "Row count mismatch"

        # Check feature values are within tolerance
        for feature in ['conflict_count', 'ttc_min', 'proximity_score']:
            diff = abs(legacy[feature] - plugin[feature])
            max_diff = diff.max()
            assert max_diff < 0.01, f"Feature {feature} differs by {max_diff}"

        logger.info("✓ Legacy vs Plugin validation passed")
```

**Testing:**
- [  ] Dual collection runs without errors
- [  ] Results comparison within 1% tolerance
- [  ] Run for 48 hours in staging
- [  ] Monitor performance overhead

**Acceptance Criteria:**
- ✅ Dual collection feature flag works
- ✅ Results match within 1% tolerance
- ✅ Performance overhead <5%
- ✅ Validation script for comparison

**Dependencies:** Task 2.1 complete

---

### Task 2.3: Gradual Rollout to Plugin ✅ Ready after Task 2.2
**Time:** 6 hours
**Assignee:** DevOps + Backend Developer
**Priority:** P0

**Rollout Plan:**
1. **Day 6-7:** Dual collection in staging (48 hours)
2. **Day 8:** Enable plugin for 10% of production traffic
3. **Day 9:** Increase to 50% if no issues
4. **Day 10:** 100% plugin, keep legacy code as fallback

**Monitoring:**
```bash
# Key metrics to watch
- vcc_plugin_collection_success_rate (target: ≥99.9%)
- vcc_plugin_collection_latency_ms (target: <3000ms)
- vcc_plugin_data_completeness (target: 100%)
- error_rate_vcc_plugin (target: <0.1%)
```

**Rollback Criteria:**
- Error rate >1%
- Latency increase >20%
- Data completeness <95%

**Acceptance Criteria:**
- ✅ 10% rollout successful (monitored 24 hours)
- ✅ 50% rollout successful (monitored 24 hours)
- ✅ 100% rollout successful
- ✅ Legacy code remains as fallback

**Dependencies:** Task 2.2 validation passes

---

### Task 2.4: Remove Legacy VCC Code (Optional) ✅ Post-Sprint
**Time:** 4 hours
**Assignee:** Backend Developer
**Priority:** P2

**Files to Modify/Remove:**
- Mark legacy code as deprecated
- Plan removal for Sprint N+1
- Update documentation

**Acceptance Criteria:**
- ✅ Plugin runs 100% for 2 weeks
- ✅ No production incidents
- ✅ Legacy code removal plan documented

**Dependencies:** 2 weeks of stable plugin operation

---

### Task 2.5: VCC Plugin Tests & Documentation ✅ Ready after Task 2.1
**Time:** 2 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `tests/plugins/test_vcc_plugin.py`
- Update `docs/PLUGIN_DEVELOPMENT_GUIDE.md`

**Testing:**
```python
def test_vcc_plugin_collect():
    """Test VCC plugin data collection"""
    pass

def test_vcc_plugin_features():
    """Verify all expected features present"""
    pass

def test_vcc_plugin_health_check():
    """Test VCC health check"""
    pass
```

**Acceptance Criteria:**
- ✅ Test coverage ≥80%
- ✅ VCC plugin documented as example
- ✅ All tests passing

**Dependencies:** Task 2.1 complete

---

## Phase 3: NOAA Weather Plugin (Days 11-17, 45 hours)

**Goal:** Implement weather data collection without affecting safety index yet.

### Task 3.1: NOAA Weather Plugin Implementation ✅ Ready after Phase 2
**Time:** 14 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/app/plugins/noaa_weather_plugin.py`

**Implementation:**
```python
# backend/app/plugins/noaa_weather_plugin.py
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import requests
import time

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus

class NOAAWeatherPlugin(DataSourcePlugin):
    """NOAA/NWS weather data source plugin"""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="noaa_weather",
            version="1.0.0",
            description="NOAA/NWS weather observation data source",
            author="Traffic Safety Team",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.15)
        )

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base = config.get('api_base', 'https://api.weather.gov')
        self.station_id = config['station_id']
        self.user_agent = config.get('user_agent', 'TrafficSafetyIndex/1.0')
        self.timeout = config.get('timeout', 10)
        self.retry_attempts = config.get('retry_attempts', 3)

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Collect weather observations for time range"""
        observations = self._fetch_observations(start_time, end_time)

        if not observations:
            return pd.DataFrame()

        # Parse observations
        data = []
        for obs in observations:
            props = obs.get('properties', {})
            data.append({
                'timestamp': pd.to_datetime(props.get('timestamp')),
                'weather_temperature_c': self._extract_value(props.get('temperature')),
                'weather_precipitation_mm': self._extract_value(props.get('precipitationLastHour')),
                'weather_visibility_m': self._extract_value(props.get('visibility')),
                'weather_wind_speed_ms': self._extract_value(props.get('windSpeed')),
                'weather_wind_direction_deg': self._extract_value(props.get('windDirection')),
                'weather_condition': props.get('textDescription', 'Unknown')
            })

        df = pd.DataFrame(data)
        df = self._normalize_features(df)
        return df

    def get_features(self) -> List[str]:
        return [
            'weather_precipitation_mm',
            'weather_visibility_m',
            'weather_wind_speed_ms',
            'weather_temperature_c'
        ]

    def health_check(self) -> PluginHealthStatus:
        """Verify NOAA station is accessible"""
        try:
            url = f"{self.api_base}/stations/{self.station_id}"
            response = self._make_request(url)

            if response.status_code == 200:
                station = response.json()
                return PluginHealthStatus(
                    healthy=True,
                    message=f"Station {self.station_id} accessible",
                    last_check=datetime.now()
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message=f"HTTP {response.status_code}",
                    last_check=datetime.now()
                )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"Error: {str(e)}",
                last_check=datetime.now()
            )

    def _fetch_observations(self, start_time, end_time):
        """Fetch with retry logic and exponential backoff"""
        url = f"{self.api_base}/stations/{self.station_id}/observations"
        params = {'start': start_time.isoformat(), 'end': end_time.isoformat()}

        for attempt in range(self.retry_attempts):
            try:
                response = self._make_request(url, params=params)
                response.raise_for_status()
                return response.json().get('features', [])
            except requests.exceptions.RequestException as e:
                if attempt < self.retry_attempts - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    time.sleep(delay)
                else:
                    raise

    def _make_request(self, url, params=None):
        """Make HTTP request with User-Agent"""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/geo+json'
        }
        return requests.get(url, params=params, headers=headers, timeout=self.timeout)

    def _extract_value(self, value_obj):
        """Extract numeric value from NOAA value object"""
        if value_obj is None:
            return None
        if isinstance(value_obj, dict):
            return value_obj.get('value')
        return value_obj

    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize weather features to 0-1 scale"""
        df = df.copy()

        # Precipitation: 0 mm = 0.0, 20+ mm/hr = 1.0
        df['weather_precipitation_normalized'] = (
            df['weather_precipitation_mm'].fillna(0) / 20.0
        ).clip(0, 1)

        # Visibility: 10 km = 0.0 (good), 0 m = 1.0 (bad)
        df['weather_visibility_normalized'] = 1.0 - (
            df['weather_visibility_m'].fillna(10000) / 10000.0
        ).clip(0, 1)

        # Wind speed: 0 m/s = 0.0, 25+ m/s = 1.0
        df['weather_wind_speed_normalized'] = (
            df['weather_wind_speed_ms'].fillna(0) / 25.0
        ).clip(0, 1)

        # Temperature: extremes = bad, 20°C = optimal
        df['weather_temperature_normalized'] = df['weather_temperature_c'].fillna(20).apply(
            lambda t: min(abs(t - 20.0) / 20.0, 1.0)
        )

        return df
```

**Testing:**
- [  ] Fetch observations from NOAA API (real call)
- [  ] Parse API response correctly
- [  ] Normalization produces 0-1 values
- [  ] Retry logic works on failures
- [  ] Health check validates station

**Acceptance Criteria:**
- ✅ NOAAWeatherPlugin implements all required methods
- ✅ Fetches real weather data from API
- ✅ Features normalized to 0-1 scale
- ✅ Exponential backoff on failures
- ✅ User-Agent header set correctly

**Dependencies:** Phase 2 complete

---

### Task 3.2: Weather Data Storage Integration ✅ Ready after Task 3.1
**Time:** 8 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Modify:**
- `backend/data_collector.py`
- `backend/app/services/db_service.py`
- `backend/app/services/parquet_storage.py`
- `backend/app/services/gcs_storage.py`

**Implementation:**

**1. Database Service:**
```python
# backend/app/services/db_service.py
from pydantic import BaseModel

class WeatherObservation(BaseModel):
    station_id: str
    observation_time: datetime
    temperature_c: Optional[float]
    precipitation_mm: Optional[float]
    visibility_m: Optional[float]
    wind_speed_ms: Optional[float]
    wind_direction_deg: Optional[int]
    weather_condition: Optional[str]
    temperature_normalized: Optional[float]
    precipitation_normalized: Optional[float]
    visibility_normalized: Optional[float]
    wind_speed_normalized: Optional[float]
    raw_json: Optional[Dict]

def insert_weather_observations_batch(observations: List[WeatherObservation]) -> int:
    """Insert weather observations into PostgreSQL"""
    # Bulk insert with ON CONFLICT DO UPDATE for idempotency
    pass
```

**2. Parquet Storage:**
```python
# backend/app/services/parquet_storage.py
def save_weather_observations(self, observations: List[Dict], timestamp: datetime) -> str:
    """Save weather observations to Parquet"""
    df = pd.DataFrame(observations)
    date_str = timestamp.strftime("%Y%m%d")
    time_str = timestamp.strftime("%H%M%S")

    filepath = self.base_path / f"weather/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/weather_{date_str}_{time_str}.parquet"
    filepath.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(filepath, compression='snappy')
    return str(filepath)
```

**3. GCS Storage:**
```python
# backend/app/services/gcs_storage.py
def upload_weather_observations(self, local_path: Path, target_date: date) -> str:
    """Upload weather Parquet to GCS"""
    blob_name = f"raw/weather/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/{local_path.name}"
    # ... upload logic ...
```

**Testing:**
- [  ] Weather data written to PostgreSQL
- [  ] Weather data written to Parquet
- [  ] Weather data uploaded to GCS
- [  ] Triple-write works for weather
- [  ] Idempotent (duplicate inserts don't fail)

**Acceptance Criteria:**
- ✅ Weather data stored in all 3 backends
- ✅ Schema matches database design
- ✅ Parquet file structure matches other data types
- ✅ GCS upload uses lifecycle policies

**Dependencies:** Task 3.1 complete

---

### Task 3.3: Enable Weather Collection (Weight=0) ✅ Ready after Task 3.2
**Time:** 4 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Modify:**
- `backend/data_collector.py`
- `backend/.env`

**Configuration:**
```bash
# Enable weather plugin but don't affect safety index yet
ENABLE_WEATHER_PLUGIN=true
WEATHER_PLUGIN_WEIGHT=0.0  # Collect only, no impact on index
```

**Implementation:**
```python
# backend/data_collector.py
def __init__(self, ...):
    # ... existing plugin registry setup ...

    # Register weather plugin if enabled
    if settings.ENABLE_WEATHER_PLUGIN:
        weather_config = {
            'station_id': settings.WEATHER_STATION_ID,
            'api_base': settings.WEATHER_API_BASE,
            'timeout': settings.WEATHER_API_TIMEOUT,
            'retry_attempts': settings.WEATHER_RETRY_ATTEMPTS,
            'enabled': True,
            'weight': settings.WEATHER_PLUGIN_WEIGHT  # 0.0 initially
        }
        self.plugin_registry.register('noaa_weather', NOAAWeatherPlugin(weather_config))

def collect_cycle(self):
    # Collect from all plugins (including weather with weight=0.0)
    all_features = self.plugin_registry.collect_all(start_time, end_time)

    # Weather data collected but doesn't affect safety index (weight=0.0)
    indices_df = compute_safety_indices_multisource(
        all_features,
        plugin_weights=self._get_plugin_weights()
    )

def _get_plugin_weights(self) -> Dict[str, float]:
    """Get plugin weights from registry"""
    return {
        name: plugin.get_weight()
        for name, plugin in self.plugin_registry.plugins.items()
        if plugin.is_enabled()
    }
```

**Testing:**
- [  ] Weather plugin collects data
- [  ] Data stored in all 3 backends
- [  ] Safety index unchanged (weight=0.0)
- [  ] Run for 7 days to accumulate data

**Acceptance Criteria:**
- ✅ Weather data collecting hourly
- ✅ No impact on safety index scores
- ✅ Weather data visible in database
- ✅ No performance degradation

**Dependencies:** Task 3.2 complete

---

### Task 3.4: Weather Plugin Tests ✅ Ready after Task 3.1
**Time:** 6 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `tests/plugins/test_noaa_weather_plugin.py`
- `tests/integration/test_weather_storage.py`

**Testing:**
```python
def test_noaa_plugin_collect():
    """Test NOAA API data collection"""
    # Mock NOAA API response
    pass

def test_noaa_plugin_normalization():
    """Test feature normalization (0-1 scale)"""
    pass

def test_noaa_plugin_retry_logic():
    """Test exponential backoff on failures"""
    pass

def test_weather_triple_write():
    """Test weather data written to Parquet + PostgreSQL + GCS"""
    pass
```

**Acceptance Criteria:**
- ✅ Test coverage ≥80%
- ✅ Mock NOAA API for unit tests
- ✅ Integration tests with real database
- ✅ All tests passing

**Dependencies:** Task 3.1 complete

---

### Task 3.5: Weather Data Quality Monitoring ✅ Ready after Task 3.3
**Time:** 5 hours
**Assignee:** Backend Developer
**Priority:** P1

**Implementation:**

**Monitoring Metrics:**
```python
# Prometheus metrics
weather_observations_collected_total = Counter(
    'weather_observations_collected_total',
    'Total weather observations collected'
)

weather_api_errors_total = Counter(
    'weather_api_errors_total',
    'Total NOAA API errors',
    ['error_type']
)

weather_data_quality_score = Gauge(
    'weather_data_quality_score',
    'Weather data quality score (0-1)',
    ['station_id']
)

weather_missing_values_ratio = Gauge(
    'weather_missing_values_ratio',
    'Ratio of missing values in weather data',
    ['feature']
)
```

**Data Quality Checks:**
```python
def validate_weather_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Validate weather data quality"""
    results = {
        'total_rows': len(df),
        'missing_values': {
            col: df[col].isna().sum() / len(df)
            for col in df.columns
        },
        'outliers': {
            'temperature': ((df['temperature_c'] < -50) | (df['temperature_c'] > 60)).sum(),
            'wind_speed': (df['wind_speed_ms'] > 50).sum(),
            'visibility': (df['visibility_m'] > 20000).sum()
        },
        'quality_score': compute_quality_score(df)
    }
    return results
```

**Acceptance Criteria:**
- ✅ Prometheus metrics exported
- ✅ Data quality validation script
- ✅ Alerting for >20% missing values
- ✅ Dashboard showing weather data health

**Dependencies:** Task 3.3 complete

---

### Task 3.6: Weather Plugin Documentation ✅ Ready after Task 3.1
**Time:** 3 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `docs/WEATHER_DATA_INTEGRATION.md`
- Update `README.md`

**Documentation Sections:**
1. NOAA/NWS API Overview
2. Weather Plugin Configuration
3. Feature Engineering Details
4. Normalization Strategy
5. Data Quality Expectations
6. Troubleshooting Guide

**Acceptance Criteria:**
- ✅ Comprehensive weather plugin documentation
- ✅ API examples with real responses
- ✅ Troubleshooting common issues
- ✅ README updated

**Dependencies:** Task 3.1 complete

---

### Task 3.7: Monitor Weather Collection (7 Days) ✅ Ready after Task 3.3
**Time:** 5 hours (spread over 7 days)
**Assignee:** Backend Developer
**Priority:** P0

**Monitoring Plan:**
- Daily: Check data quality metrics
- Daily: Verify data in all 3 storage backends
- Daily: Review error logs
- Day 7: Generate summary report

**Success Metrics:**
- ≥95% data availability
- <5% missing values
- <0.1% API error rate
- All 3 storage backends consistent

**Acceptance Criteria:**
- ✅ 7 days of stable weather collection
- ✅ Data quality report generated
- ✅ No production incidents
- ✅ Ready for Phase 4 (backfill)

**Dependencies:** Task 3.3 complete

---

## Phase 4: Historical Weather Backfill (Days 18-21, 25 hours)

**Goal:** Retrieve historical weather for all existing traffic data periods.

### Task 4.1: Backfill Script Development ✅ Ready after Phase 3
**Time:** 10 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/scripts/backfill_weather_data.py`
- `backend/scripts/backfill_state.json` (progress tracking)

**Implementation:**
```python
#!/usr/bin/env python3
"""
Backfill historical weather data for all traffic data periods.

Usage:
    python scripts/backfill_weather_data.py --start-date 2024-05-01 --end-date 2024-11-21
    python scripts/backfill_weather_data.py --auto  # Auto-detect missing dates
    python scripts/backfill_weather_data.py --resume  # Resume from last state
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple

from app.plugins.noaa_weather_plugin import NOAAWeatherPlugin
from app.services.db_service import insert_weather_observations_batch
from app.services.parquet_storage import ParquetStorage
from app.services.gcs_storage import GCSStorage
from app.core.config import settings

class WeatherBackfillManager:
    def __init__(self, station_id: str, rate_limit_delay: float = 1.0):
        self.station_id = station_id
        self.rate_limit_delay = rate_limit_delay
        self.state_file = Path('backfill_state.json')

        # Initialize plugin
        self.weather_plugin = NOAAWeatherPlugin({
            'station_id': station_id,
            'enabled': True,
            'weight': 0.0
        })

        # Initialize storage backends
        self.parquet_storage = ParquetStorage()
        self.gcs_storage = GCSStorage() if settings.ENABLE_GCS_UPLOAD else None

    def get_missing_date_ranges(self) -> List[Tuple[datetime, datetime]]:
        """
        Identify date ranges where traffic data exists but weather data missing.

        Strategy:
        1. Query safety_indices_realtime for distinct dates
        2. Query weather_observations for distinct dates
        3. Return difference
        """
        # SQL query to find missing dates
        query = """
        SELECT DISTINCT DATE(time_15min) as date
        FROM safety_indices_realtime
        WHERE NOT EXISTS (
            SELECT 1 FROM weather_observations
            WHERE DATE(observation_time) = DATE(safety_indices_realtime.time_15min)
            AND station_id = %s
        )
        ORDER BY date;
        """
        # Execute and return date ranges
        pass

    def backfill_date_range(self, start_date: datetime, end_date: datetime):
        """Backfill weather for date range"""
        current_date = start_date

        while current_date <= end_date:
            try:
                print(f"Backfilling {current_date.date()}...")

                # Collect weather for 24 hours
                day_start = current_date.replace(hour=0, minute=0, second=0)
                day_end = day_start + timedelta(days=1)

                weather_df = self.weather_plugin.collect(day_start, day_end)

                if not weather_df.empty:
                    # Save to all storage backends
                    self._save_to_storage(weather_df, current_date)

                    print(f"  ✓ Saved {len(weather_df)} observations")
                else:
                    print(f"  ⚠ No data available for {current_date.date()}")

                # Save progress
                self._save_state({
                    'last_completed_date': current_date.isoformat(),
                    'processed_dates': self.state.get('processed_dates', 0) + 1
                })

                # Rate limiting
                time.sleep(self.rate_limit_delay)

            except Exception as e:
                print(f"  ✗ Error: {e}")
                # Continue with next date (don't fail entire backfill)

            current_date += timedelta(days=1)

    def _save_to_storage(self, weather_df, date):
        """Save weather data to Parquet, PostgreSQL, and GCS"""
        # 1. PostgreSQL
        insert_weather_observations_batch(weather_df.to_dict('records'))

        # 2. Parquet
        parquet_path = self.parquet_storage.save_weather_observations(
            weather_df.to_dict('records'),
            date
        )

        # 3. GCS (if enabled)
        if self.gcs_storage:
            self.gcs_storage.upload_weather_observations(
                Path(parquet_path),
                date.date()
            )

    def _save_state(self, state: Dict):
        """Save backfill progress to JSON file"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> Dict:
        """Load backfill progress from JSON file"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

def main():
    parser = argparse.ArgumentParser(description='Backfill historical weather data')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--auto', action='store_true', help='Auto-detect missing dates')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state')
    parser.add_argument('--rate-limit', type=float, default=1.0, help='Delay between requests (seconds)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    args = parser.parse_args()

    manager = WeatherBackfillManager(
        station_id=settings.WEATHER_STATION_ID,
        rate_limit_delay=args.rate_limit
    )

    if args.auto:
        date_ranges = manager.get_missing_date_ranges()
        print(f"Found {len(date_ranges)} date ranges to backfill")
        for start, end in date_ranges:
            manager.backfill_date_range(start, end)
    elif args.resume:
        state = manager._load_state()
        last_date = datetime.fromisoformat(state['last_completed_date'])
        end_date = datetime.now()
        manager.backfill_date_range(last_date + timedelta(days=1), end_date)
    else:
        start = datetime.strptime(args.start_date, '%Y-%m-%d')
        end = datetime.strptime(args.end_date, '%Y-%m-%d')
        manager.backfill_date_range(start, end)

if __name__ == '__main__':
    main()
```

**Testing:**
- [  ] Dry-run mode shows correct date ranges
- [  ] Resume capability works after interruption
- [  ] Rate limiting prevents API throttling
- [  ] Progress saved correctly

**Acceptance Criteria:**
- ✅ Script identifies missing date ranges
- ✅ Batch processing with resume capability
- ✅ Rate limiting configurable
- ✅ Progress tracking in JSON file
- ✅ Triple-write to all storage backends

**Dependencies:** Phase 3 complete (7 days of monitoring)

---

### Task 4.2: Backfill Validation Script ✅ Ready with Task 4.1
**Time:** 4 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Create:**
- `backend/scripts/validate_weather_backfill.py`

**Implementation:**
```python
#!/usr/bin/env python3
"""Validate weather backfill data quality and completeness"""

def validate_backfill():
    """Run validation checks on backfilled weather data"""

    checks = [
        check_date_coverage(),
        check_data_completeness(),
        check_storage_consistency(),
        check_data_quality()
    ]

    report = generate_validation_report(checks)
    print(report)

def check_date_coverage():
    """Verify weather data exists for all traffic data dates"""
    query = """
    SELECT
        COUNT(DISTINCT DATE(time_15min)) as traffic_dates,
        COUNT(DISTINCT DATE(observation_time)) as weather_dates
    FROM safety_indices_realtime
    LEFT JOIN weather_observations
        ON DATE(time_15min) = DATE(observation_time);
    """
    # Compare counts
    pass

def check_storage_consistency():
    """Verify same data in Parquet, PostgreSQL, and GCS"""
    # Compare row counts across backends
    pass

def check_data_quality():
    """Check for missing values, outliers, anomalies"""
    # Run quality metrics
    pass
```

**Acceptance Criteria:**
- ✅ Validation script reports coverage %
- ✅ Identifies missing dates
- ✅ Checks storage consistency
- ✅ Reports data quality issues

**Dependencies:** Task 4.1 complete

---

### Task 4.3: Execute Backfill (Staged) ✅ Ready after Task 4.1
**Time:** 8 hours (mostly waiting)
**Assignee:** Backend Developer
**Priority:** P0

**Execution Plan:**

**Stage 1: Test Run (1 week of data)**
```bash
python scripts/backfill_weather_data.py --start-date 2024-11-14 --end-date 2024-11-21 --rate-limit 1.0
```
- Expected: ~7 days × 24 hours = 168 observations
- Time: ~3 minutes
- Validate before proceeding

**Stage 2: Full Backfill (6 months of data)**
```bash
python scripts/backfill_weather_data.py --start-date 2024-05-01 --end-date 2024-11-21 --rate-limit 1.0
```
- Expected: ~180 days × 24 hours = 4,320 observations
- Time: ~72 minutes (at 1 req/sec)
- Run overnight

**Stage 3: Validation**
```bash
python scripts/validate_weather_backfill.py
```

**Monitoring:**
- Watch NOAA API error rate
- Monitor database write performance
- Check GCS upload progress

**Acceptance Criteria:**
- ✅ ≥95% date coverage
- ✅ <5% missing values
- ✅ Storage consistency ≥99%
- ✅ Validation report generated

**Dependencies:** Task 4.1 complete

---

### Task 4.4: Backfill Documentation ✅ Ready with Task 4.1
**Time:** 3 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Update:**
- `docs/WEATHER_DATA_INTEGRATION.md`
- `README.md`

**Documentation:**
- Backfill process overview
- Command-line usage examples
- Troubleshooting guide
- Resume after failure
- Validation procedures

**Acceptance Criteria:**
- ✅ Step-by-step backfill guide
- ✅ Examples with real commands
- ✅ Troubleshooting common issues
- ✅ Validation procedures documented

**Dependencies:** Task 4.1 complete

---

## Phase 5: Safety Index Integration (Days 22-25, 30 hours)

**Goal:** Integrate weather into safety index calculation with configurable weights.

### Task 5.1: Multi-Source Safety Index Calculation ✅ Ready after Phase 4
**Time:** 10 hours
**Assignee:** Backend Developer
**Priority:** P0

**Files to Modify:**
- `backend/app/services/index_computation.py`

**Implementation:**
```python
# backend/app/services/index_computation.py

def compute_safety_indices_multisource(
    features_df: pd.DataFrame,
    plugin_weights: Dict[str, float],
    norm_constants: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Compute safety indices from multiple data source plugins.

    Args:
        features_df: Combined features from all plugins
        plugin_weights: Weight for each plugin (must sum to 1.0)
        norm_constants: Normalization constants for features

    Returns:
        DataFrame with safety_index and plugin contributions
    """
    # Validate weights sum to 1.0
    total_weight = sum(plugin_weights.values())
    if abs(total_weight - 1.0) > 0.01:
        raise ValueError(f"Plugin weights must sum to 1.0, got {total_weight}")

    indices = []

    for idx, row in features_df.iterrows():
        # Compute VCC score (aggregate all VCC features)
        vcc_score = compute_vcc_score(row, norm_constants)

        # Compute weather score (aggregate all weather features)
        weather_score = compute_weather_score(row, norm_constants)

        # Weighted sum
        safety_index = (
            vcc_score * plugin_weights.get('vcc', 0.0) +
            weather_score * plugin_weights.get('noaa_weather', 0.0)
        )

        indices.append({
            'intersection_id': row.get('intersection_id'),
            'time_15min': row.get('timestamp'),
            'safety_index': safety_index,

            # VCC features
            'vcc_conflict_count': row.get('vcc_conflict_count'),
            'vcc_ttc_min': row.get('vcc_ttc_min'),
            'vcc_proximity_score': row.get('vcc_proximity_score'),
            'vcc_contribution': vcc_score * plugin_weights.get('vcc', 0.0),

            # Weather features
            'weather_precipitation_normalized': row.get('weather_precipitation_normalized'),
            'weather_visibility_normalized': row.get('weather_visibility_normalized'),
            'weather_wind_speed_normalized': row.get('weather_wind_speed_normalized'),
            'weather_temperature_normalized': row.get('weather_temperature_normalized'),
            'weather_contribution': weather_score * plugin_weights.get('noaa_weather', 0.0),

            # Metadata
            'formula_version': 'v2.0'
        })

    return pd.DataFrame(indices)


def compute_vcc_score(row: pd.Series, norm_constants: Optional[Dict]) -> float:
    """
    Compute VCC aggregate score from traffic features.

    Aggregation strategy: weighted average of normalized features
    """
    features = {
        'conflict_count': row.get('vcc_conflict_count', 0),
        'ttc_min': row.get('vcc_ttc_min', 10),  # High TTC = safe
        'proximity_score': row.get('vcc_proximity_score', 0)
    }

    # Normalize features (if constants available)
    if norm_constants:
        features = normalize_features(features, norm_constants)

    # Weighted average (adjust these weights based on validation)
    score = (
        features['conflict_count'] * 0.4 +
        (1.0 - features['ttc_min']) * 0.4 +  # Invert: low TTC = high risk
        features['proximity_score'] * 0.2
    )

    return min(max(score, 0.0), 1.0)


def compute_weather_score(row: pd.Series, norm_constants: Optional[Dict]) -> float:
    """
    Compute weather aggregate score.

    Higher score = more hazardous weather
    """
    features = {
        'precipitation': row.get('weather_precipitation_normalized', 0),
        'visibility': row.get('weather_visibility_normalized', 0),
        'wind_speed': row.get('weather_wind_speed_normalized', 0),
        'temperature': row.get('weather_temperature_normalized', 0)
    }

    # Weighted average (adjust based on crash correlation analysis)
    score = (
        features['precipitation'] * 0.40 +  # Rain/snow most important
        features['visibility'] * 0.35 +     # Visibility second
        features['wind_speed'] * 0.15 +     # Wind less critical
        features['temperature'] * 0.10      # Temperature least critical
    )

    return min(max(score, 0.0), 1.0)
```

**Testing:**
- [  ] Safety index changes with weather conditions
- [  ] Weight adjustment affects scores correctly
- [  ] Weights validation enforced (sum = 1.0)
- [  ] Plugin contributions tracked correctly

**Acceptance Criteria:**
- ✅ Multi-source calculation implemented
- ✅ VCC and weather scores computed separately
- ✅ Weighted sum with configurable weights
- ✅ Plugin contributions stored in database

**Dependencies:** Phase 4 complete

---

### Task 5.2: Enable Weather in Safety Index (Gradual) ✅ Ready after Task 5.1
**Time:** 8 hours
**Assignee:** Backend Developer + DevOps
**Priority:** P0

**Rollout Plan:**

**Day 22:** Enable with weight=0.05 (5% weather, 95% VCC)
```bash
WEATHER_PLUGIN_WEIGHT=0.05
VCC_PLUGIN_WEIGHT=0.95
```

**Day 23:** Increase to weight=0.10 (10% weather)
```bash
WEATHER_PLUGIN_WEIGHT=0.10
VCC_PLUGIN_WEIGHT=0.90
```

**Day 24:** Full weight=0.15 (15% weather)
```bash
WEATHER_PLUGIN_WEIGHT=0.15
VCC_PLUGIN_WEIGHT=0.70
# Reserve 15% for future data sources
```

**Monitoring:**
- Safety index value distribution
- API response times
- User feedback on score changes

**Rollback:**
- Set `WEATHER_PLUGIN_WEIGHT=0.0` to disable

**Acceptance Criteria:**
- ✅ Gradual rollout successful
- ✅ No production incidents
- ✅ Safety scores reasonable (not all 0 or 1)
- ✅ Weather impact visible in data

**Dependencies:** Task 5.1 complete

---

### Task 5.3: A/B Comparison (Old vs New Formula) ✅ Ready after Task 5.2
**Time:** 6 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `backend/scripts/compare_formulas.py`

**Implementation:**
```python
#!/usr/bin/env python3
"""Compare old vs new safety index formulas"""

def compare_formulas(start_date, end_date):
    """
    Compute safety index with both formulas and compare.

    Old Formula: VCC only (100%)
    New Formula: VCC (70%) + Weather (15%) + Reserved (15%)
    """
    # Fetch data for date range
    data = fetch_safety_indices(start_date, end_date)

    # Recompute with old formula
    data['safety_index_old'] = compute_old_formula(data)

    # Compare distributions
    comparison = {
        'correlation': data['safety_index'].corr(data['safety_index_old']),
        'mean_old': data['safety_index_old'].mean(),
        'mean_new': data['safety_index'].mean(),
        'std_old': data['safety_index_old'].std(),
        'std_new': data['safety_index'].std(),
        'max_difference': (data['safety_index'] - data['safety_index_old']).abs().max()
    }

    # Plot distributions
    plot_comparison(data)

    return comparison

def plot_comparison(data):
    """Generate comparison plots"""
    # Histogram overlay
    # Scatter plot (old vs new)
    # Time series (both formulas)
    pass
```

**Acceptance Criteria:**
- ✅ Comparison script generates report
- ✅ Correlation ≥0.85 (not too different)
- ✅ Mean difference <0.10
- ✅ Visual comparison plots

**Dependencies:** Task 5.2 complete

---

### Task 5.4: Safety Index Calculation Tests ✅ Ready after Task 5.1
**Time:** 4 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `tests/services/test_index_computation_multisource.py`

**Testing:**
```python
def test_multisource_computation():
    """Test safety index with multiple data sources"""
    pass

def test_weight_validation():
    """Test weights must sum to 1.0"""
    pass

def test_plugin_contribution_tracking():
    """Test VCC and weather contributions calculated correctly"""
    pass

def test_missing_weather_data():
    """Test behavior when weather data unavailable"""
    pass
```

**Acceptance Criteria:**
- ✅ Test coverage ≥85%
- ✅ Edge cases tested
- ✅ All tests passing

**Dependencies:** Task 5.1 complete

---

### Task 5.5: Performance Benchmarking ✅ Ready after Task 5.2
**Time:** 2 hours
**Assignee:** Backend Developer
**Priority:** P1

**Benchmarks:**
```python
# pytest-benchmark
def test_safety_index_calculation_performance(benchmark):
    """Benchmark safety index calculation with weather"""
    # Target: <100ms for 1000 intersections
    pass

def test_plugin_collection_performance(benchmark):
    """Benchmark parallel plugin collection"""
    # Target: <3 seconds total
    pass
```

**Metrics:**
- Collection latency: <3s (target: <5% overhead)
- Calculation time: <100ms per intersection
- API response time: <200ms for current data

**Acceptance Criteria:**
- ✅ Benchmarks meet performance targets
- ✅ <5% overhead from weather integration
- ✅ Performance regression alerts configured

**Dependencies:** Task 5.2 complete

---

## Phase 6: UI Transparency (Days 26-28, 20 hours)

**Goal:** Display safety index formula breakdown in dashboard.

### Task 6.1: Formula Breakdown API Endpoint ✅ Ready after Phase 5
**Time:** 8 hours
**Assignee:** Backend Developer
**Priority:** P1

**Files to Create:**
- `backend/app/api/v1/endpoints/transparency.py`

**API Endpoint:**
```python
# GET /api/v1/safety-index/{intersection_id}/breakdown?timestamp=...

@router.get("/{intersection_id}/breakdown")
async def get_safety_index_breakdown(
    intersection_id: str,
    timestamp: Optional[datetime] = None
) -> SafetyIndexBreakdown:
    """
    Get detailed breakdown of safety index calculation.

    Returns:
        - Overall safety index score
        - Contribution from each plugin (VCC, weather)
        - Raw feature values
        - Normalized feature values
        - Feature weights
        - Calculation formula
    """
    # Fetch safety index record
    index_record = get_safety_index(intersection_id, timestamp)

    # Fetch raw feature data
    vcc_features = get_vcc_features(intersection_id, timestamp)
    weather_features = get_weather_features(intersection_id, timestamp)

    # Build breakdown response
    breakdown = {
        'intersection_id': intersection_id,
        'timestamp': timestamp,
        'safety_index': index_record.safety_index,
        'risk_level': compute_risk_level(index_record.safety_index),

        'breakdown': {
            'vcc': {
                'weight': 0.70,
                'contribution': index_record.vcc_contribution,
                'features': {
                    'vcc_conflict_count': {
                        'raw_value': vcc_features.conflict_count,
                        'normalized': vcc_features.conflict_count_normalized,
                        'description': 'Number of vehicle conflicts detected'
                    },
                    # ... more features
                },
                'aggregated_score': index_record.vcc_contribution / 0.70
            },
            'noaa_weather': {
                'weight': 0.15,
                'contribution': index_record.weather_contribution,
                'features': {
                    'weather_precipitation': {
                        'raw_value': weather_features.precipitation_mm,
                        'normalized': weather_features.precipitation_normalized,
                        'description': 'Precipitation (mm/hour)'
                    },
                    # ... more features
                },
                'aggregated_score': index_record.weather_contribution / 0.15
            }
        },

        'calculation': f"{index_record.safety_index:.2f} = ({index_record.vcc_contribution:.2f} × 0.70) + ({index_record.weather_contribution:.2f} × 0.15)",
        'formula_version': 'v2.0'
    }

    return breakdown
```

**Testing:**
- [  ] API returns correct breakdown structure
- [  ] Feature values match database
- [  ] Calculation formula is accurate
- [  ] Response time <200ms

**Acceptance Criteria:**
- ✅ Breakdown API endpoint implemented
- ✅ Returns all required fields
- ✅ Response schema documented
- ✅ Unit tests passing

**Dependencies:** Phase 5 complete

---

### Task 6.2: Dashboard Formula Transparency Component ✅ Ready after Task 6.1
**Time:** 10 hours
**Assignee:** Frontend Developer
**Priority:** P1

**Files to Create:**
- `frontend/src/components/SafetyIndexBreakdown.tsx`
- `frontend/src/components/FeatureBreakdownTable.tsx`

**Component Design:**
```typescript
interface SafetyIndexBreakdownProps {
  intersectionId: string;
  timestamp: string;
}

function SafetyIndexBreakdown({ intersectionId, timestamp }: SafetyIndexBreakdownProps) {
  const { data, loading } = useSafetyIndexBreakdown(intersectionId, timestamp);

  if (loading) return <Spinner />;

  return (
    <div className="breakdown-panel">
      <h3>Safety Index: {data.safety_index.toFixed(2)} ({data.risk_level})</h3>

      {/* VCC Plugin Section */}
      <PluginSection plugin="vcc" data={data.breakdown.vcc} />

      {/* Weather Plugin Section */}
      <PluginSection plugin="noaa_weather" data={data.breakdown.noaa_weather} />

      {/* Calculation Formula */}
      <FormulaDisplay formula={data.calculation} />
    </div>
  );
}

function PluginSection({ plugin, data }: PluginSectionProps) {
  return (
    <section className="plugin-section">
      <h4>{plugin} (Weight: {data.weight * 100}%)</h4>

      <ProgressBar
        value={data.contribution}
        max={1.0}
        color={getPluginColor(plugin)}
      />

      <table className="feature-table">
        <thead>
          <tr>
            <th>Feature</th>
            <th>Raw Value</th>
            <th>Normalized</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(data.features).map(([feature, info]) => (
            <tr key={feature}>
              <td>{feature}</td>
              <td>{info.raw_value}</td>
              <td>{info.normalized.toFixed(2)}</td>
              <td>{info.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

**Testing:**
- [  ] Component renders correctly
- [  ] Data fetched from API
- [  ] Formula displayed clearly
- [  ] Responsive design

**Acceptance Criteria:**
- ✅ Breakdown component implemented
- ✅ Displays all features and weights
- ✅ Visual breakdown (progress bars/charts)
- ✅ User-friendly design

**Dependencies:** Task 6.1 complete

---

### Task 6.3: Dashboard Integration & Testing ✅ Ready after Task 6.2
**Time:** 2 hours
**Assignee:** Frontend Developer
**Priority:** P1

**Files to Modify:**
- `frontend/src/pages/IntersectionDetailPage.tsx`

**Integration:**
- Add "Formula Breakdown" tab to intersection detail page
- Show breakdown on click/hover
- Link to breakdown from safety index score

**Acceptance Criteria:**
- ✅ Component integrated in dashboard
- ✅ Accessible from intersection detail page
- ✅ End-to-end tests passing
- ✅ User testing completed

**Dependencies:** Task 6.2 complete

---

## Phase 7: Validation & Optimization (Days 29-30, 15 hours)

**Goal:** Validate weather impact and optimize feature weights using crash data.

### Task 7.1: Crash Data Correlation Analysis ✅ Ready after Phase 6
**Time:** 10 hours
**Assignee:** Data Analyst / Backend Developer
**Priority:** P1

**Files to Create:**
- `backend/scripts/crash_correlation_analysis.py`
- `backend/scripts/optimize_feature_weights.py`

**Analysis:**
```python
#!/usr/bin/env python3
"""Correlate safety index with historical crash data"""

def load_crash_data():
    """Load historical crash records"""
    # Query crash database
    pass

def analyze_correlation():
    """
    Compare safety index scores during crash events vs normal periods.

    Metrics:
    - True Positive Rate: High safety index + crash occurred
    - False Positive Rate: High safety index + no crash
    - ROC curve and AUC
    - Precision-Recall curve
    """
    crashes = load_crash_data()
    safety_indices = load_safety_indices()

    # Join on intersection_id and timestamp (within ±15 min window)
    merged = merge_crash_safety_data(crashes, safety_indices)

    # Binary classification: crash (1) vs no crash (0)
    y_true = merged['has_crash']
    y_pred = merged['safety_index']  # Use as probability

    # Compute metrics
    from sklearn.metrics import roc_auc_score, precision_recall_curve, roc_curve

    auc = roc_auc_score(y_true, y_pred)
    fpr, tpr, thresholds = roc_curve(y_true, y_pred)

    # Compare old vs new formula
    auc_old = roc_auc_score(y_true, merged['safety_index_old'])
    improvement = auc - auc_old

    report = {
        'auc_new_formula': auc,
        'auc_old_formula': auc_old,
        'improvement': improvement,
        'improvement_pct': (improvement / auc_old) * 100,
        'optimal_threshold': find_optimal_threshold(fpr, tpr, thresholds)
    }

    return report

def optimize_weights():
    """
    Find optimal feature weights using grid search.

    Search space:
    - VCC weight: 0.60 - 0.80
    - Weather weight: 0.10 - 0.25
    - Constraint: sum = 0.95 (reserve 5% for future)

    Objective: Maximize AUC
    """
    from sklearn.model_selection import GridSearchCV

    param_grid = {
        'vcc_weight': [0.60, 0.65, 0.70, 0.75, 0.80],
        'weather_weight': [0.10, 0.15, 0.20, 0.25]
    }

    # Grid search
    best_params = grid_search(param_grid, objective='max_auc')

    return best_params
```

**Deliverables:**
1. Correlation report (AUC comparison)
2. ROC and Precision-Recall curves
3. Recommended feature weights
4. Statistical significance tests

**Acceptance Criteria:**
- ✅ Crash correlation analysis complete
- ✅ AUC improvement ≥5% (target)
- ✅ Recommended weights based on data
- ✅ Validation report generated

**Dependencies:** Historical crash data available

---

### Task 7.2: Weight Optimization & Update ✅ Ready after Task 7.1
**Time:** 3 hours
**Assignee:** Backend Developer
**Priority:** P1

**Based on correlation analysis:**

**If improvement ≥5%:**
- Update weights to optimized values
- Document decision

**If improvement <5%:**
- Keep current weights (15%)
- Plan for additional weather features (e.g., fog, ice)

**Configuration Update:**
```bash
# Optimized weights (example - actual values from analysis)
VCC_PLUGIN_WEIGHT=0.72
WEATHER_PLUGIN_WEIGHT=0.18
```

**Acceptance Criteria:**
- ✅ Weights updated based on data
- ✅ Decision documented
- ✅ Production configuration updated
- ✅ Monitoring shows improvement

**Dependencies:** Task 7.1 complete

---

### Task 7.3: Final Documentation & Handoff ✅ Ready after Task 7.2
**Time:** 2 hours
**Assignee:** Technical Writer / Backend Developer
**Priority:** P1

**Documentation Updates:**
1. **README.md** - Add weather integration overview
2. **PLUGIN_DEVELOPMENT_GUIDE.md** - Complete guide for future plugins
3. **WEATHER_DATA_INTEGRATION.md** - Weather-specific docs
4. **OPERATIONAL_GUIDE.md** - Update with plugin management
5. **CHANGELOG.md** - Sprint summary

**Handoff Materials:**
- Admin guide for adjusting weights
- Troubleshooting guide
- Monitoring dashboard guide
- Future roadmap (Phase 2: More plugins)

**Acceptance Criteria:**
- ✅ All documentation updated
- ✅ Admin training completed
- ✅ Handoff materials ready
- ✅ Sprint retrospective documented

**Dependencies:** All phases complete

---

## Sprint Retrospective

### Key Achievements
- [ ] Plugin architecture enables adding new data sources without code changes
- [ ] VCC successfully refactored as plugin with zero data loss
- [ ] Weather data integrated with ___% improvement in crash prediction
- [ ] UI transparency shows users how safety scores are calculated
- [ ] Performance overhead: ___% (target: <5%)
- [ ] Historical weather backfilled for all traffic data periods

### Metrics
- **Test Coverage:** ___% (target: ≥80%)
- **Performance:** Collection latency ___ms (target: <3000ms)
- **Reliability:** Plugin uptime ___% (target: ≥99.9%)
- **Data Quality:** Weather data completeness ___% (target: ≥95%)
- **Predictive Accuracy:** AUC improvement ___% (target: ≥5%)

### Lessons Learned
- What went well:
- What could be improved:
- Unexpected challenges:
- Technical debt created:

### Next Steps (Future Sprints)
1. **Additional Weather Features:** Fog, ice, snow accumulation
2. **New Data Sources:** Traffic cameras, social media, crash reports
3. **Admin UI for Weight Adjustment:** No-code weight tuning
4. **A/B Testing Framework:** Compare multiple formulas in production
5. **Machine Learning Models:** Replace hand-crafted weights with ML

---

## Risk Register

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| NOAA API rate limiting during backfill | Medium | High | Exponential backoff, batch processing | Backend Dev |
| Weather doesn't improve predictions | Medium | High | Run correlation early, have exit criteria | Data Analyst |
| Performance degradation | Low | Medium | Benchmark continuously, optimize queries | Backend Dev |
| Plugin complexity too high | Medium | Low | Comprehensive docs, training | Tech Lead |
| PostgreSQL migration delays weather | Low | High | Weather can use Parquet initially | DevOps |
| Scope creep (too many plugins) | High | Medium | Strict Phase 1 scope: VCC + Weather only | PM |

---

## Dependencies & Blockers

### External Dependencies
- [ ] Historical crash data accessible
- [ ] NOAA API stable and accessible
- [ ] PostgreSQL migration Phase 3 complete
- [ ] Frontend team availability (Week 5)

### Internal Dependencies
- [ ] Database schema approved
- [ ] Feature flags implemented
- [ ] Monitoring infrastructure ready
- [ ] Documentation templates available

### Current Blockers
- None (planning phase)

---

## Budget & Resources

### Time Budget
- **Total Estimated Hours:** 180-220 hours
- **Sprint Duration:** 6 weeks (30 working days)
- **Team Size:** 1-2 developers
- **Availability:** 80% (accounting for meetings, interruptions)
- **Buffer:** 20% for unknowns

### Infrastructure Costs
- **PostgreSQL Storage:** +500 GB for weather data (~$50/month)
- **GCS Storage:** Weather Parquet files (~$20/month)
- **NOAA API:** Free (no cost)
- **Compute:** Negligible increase (<5%)

---

## Success Metrics (Revisited)

### Must Have (P0)
- ✅ Plugin architecture implemented
- ✅ VCC refactored as plugin (zero data loss)
- ✅ NOAA weather data integrated
- ✅ Historical backfill complete (≥95% coverage)
- ✅ <5% performance overhead

### Should Have (P1)
- ✅ UI formula transparency
- ✅ Crash correlation analysis
- ✅ AUC improvement ≥5%
- ✅ Admin documentation complete

### Could Have (P2)
- Admin UI for weight adjustment
- Additional weather features (fog, ice)
- Third data source plugin
- Machine learning weight optimization

---

**Sprint Plan Version:** 1.0
**Last Updated:** 2025-11-21
**Status:** Planning - Ready for Kickoff
**Next Review:** Sprint kickoff meeting
