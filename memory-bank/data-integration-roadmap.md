# Data Integration & Extensibility Roadmap

**Created**: 2025-11-20
**Status**: IN PROGRESS (Phases 1-5 Complete)
**Priority**: HIGH - Next Major Feature Set
**Last Updated**: 2025-11-21

---

## Progress Summary

### ✅ Completed Phases (Days 1-25 of Sprint)

**Phase 1: Plugin Architecture Foundation** ✓ DONE
- Created base plugin classes (`DataSourcePlugin`, `PluginMetadata`, `PluginHealthStatus`)
- Implemented `PluginRegistry` with parallel collection and failure isolation
- Added Pydantic-based configuration management
- Database schema for weather and plugin tracking
- **Commit**: `86c1f14` + `669a7b4` (tests/docs)

**Phase 2: VCC Plugin Wrapper** ✓ DONE
- Migrated VCC traffic data collection to plugin architecture
- 5 normalized features (conflict_count, ttc_min, proximity_score, speed_variance, acceleration_events)
- Factory function for settings-based initialization
- 30+ unit tests with mocked VCC client
- **Commit**: `cb7eb7b`

**Phase 3: NOAA Weather Plugin** ✓ DONE
- Integrated NOAA/NWS API for weather observations
- 4 normalized features (precipitation, visibility, wind_speed, temperature)
- Exponential backoff retry logic for API resilience
- U-shaped temperature risk curve
- 32 unit tests with mocked NOAA API
- **Commit**: `3a9f34d`

**Phase 4: Storage Integration** ✓ DONE
- Extended `db_service.py` with weather observation functions
- Added weather support to Parquet storage (date-partitioned)
- GCS archiving for weather data (cloud backup)
- Triple-write architecture: PostgreSQL + Parquet + GCS
- **Commit**: `b72ae83`

**Phase 5: Multi-Source Safety Index Integration** ✓ DONE
- Created `MultiSourceDataCollector` service for orchestrating plugin data collection
- Implemented `compute_weather_index()` function (4 features: precip, vis, wind, temp)
- Updated `compute_safety_indices()` to include Weather Index in Combined Index
- Weighted formula: `Combined = 0.85×Traffic + 0.15×Weather` (configurable)
- Added `compute_multi_source_safety_indices()` convenience function
- Infrastructure updates: `IntersectionSafetyIndex` schema, optional GCS imports
- Comprehensive test suite (`test_multi_source_indices.py`) with 6 test cases
- **Commit**: `4296974` + `35de486`

### 🚧 Current Phase

**Phase 6: UI Transparency** (STARTING)
- Goal: Display safety index formula breakdown in dashboard
- Next tasks: Create API endpoint for formula breakdown and transparency

---

## Executive Summary

Transform the current VCC-only safety index system into a flexible, multi-source data platform with a configuration-driven architecture that allows:
- Easy integration of new data sources without code changes
- Dynamic adjustment of safety index features and weights
- Admin UI for data analysis and index tuning
- Team collaboration on index optimization

---

## Vision

**Current State**: Hard-coded VCC API integration with fixed safety index formula

**Target State**: Pluggable data integration platform where:
- Data sources are modular plugins configured via UI
- Safety index features and weights are adjustable in real-time
- Team members can analyze data and tune the index without touching code
- Multiple index formulas can be tested and compared

---

## Architecture Components

### 1. Pluggable Data Source Framework

#### 1.1 Abstract Data Source Interface

Create a standardized interface that all data sources must implement:

```python
# app/core/data_sources/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

class DataSourcePlugin(ABC):
    """Base class for all data source plugins"""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this data source"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name"""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type: 'api', 'database', 'file', 'stream'"""
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the data source with settings"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration is correct"""
        pass

    @abstractmethod
    def collect(self, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Collect data for time range, return standardized DataFrame"""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, str]:
        """Return expected output schema"""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check if data source is accessible"""
        pass
```

#### 1.2 Data Source Registry

```python
# app/core/data_sources/registry.py

class DataSourceRegistry:
    """Registry for all available data source plugins"""

    def __init__(self):
        self._sources: Dict[str, Type[DataSourcePlugin]] = {}

    def register(self, source_class: Type[DataSourcePlugin]):
        """Register a new data source plugin"""
        source = source_class()
        self._sources[source.source_id] = source_class

    def get(self, source_id: str) -> Optional[DataSourcePlugin]:
        """Get a data source by ID"""
        if source_id in self._sources:
            return self._sources[source_id]()
        return None

    def list_available(self) -> List[str]:
        """List all registered source IDs"""
        return list(self._sources.keys())

# Global registry
registry = DataSourceRegistry()
```

#### 1.3 Example Data Source Implementations

**VCC API Plugin** (migrate existing code):
```python
# app/core/data_sources/plugins/vcc_plugin.py

class VCCDataSource(DataSourcePlugin):
    source_id = "vcc_api"
    source_name = "Virginia Connected Corridor API"
    source_type = "api"

    def configure(self, config: Dict[str, Any]):
        self.base_url = config.get('base_url')
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')

    def collect(self, start_dt, end_dt) -> pd.DataFrame:
        # Existing VCC collection logic
        pass
```

**Weather Data Plugin** (new):
```python
# app/core/data_sources/plugins/weather_plugin.py

class WeatherDataSource(DataSourcePlugin):
    source_id = "weather_api"
    source_name = "Weather API (OpenWeatherMap)"
    source_type = "api"

    def configure(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.locations = config.get('locations', [])

    def collect(self, start_dt, end_dt) -> pd.DataFrame:
        # Fetch precipitation, visibility, temperature
        # Return standardized format:
        # [timestamp, location, precipitation_mm, visibility_km, temperature_c, conditions]
        pass
```

**VDOT Crash Data Plugin** (new):
```python
# app/core/data_sources/plugins/vdot_crash_plugin.py

class VDOTCrashDataSource(DataSourcePlugin):
    source_id = "vdot_crash"
    source_name = "VDOT Historical Crash Data"
    source_type = "database"

    def configure(self, config: Dict[str, Any]):
        self.db_connection_string = config.get('connection_string')

    def collect(self, start_dt, end_dt) -> pd.DataFrame:
        # Query VDOT crash database
        # Return: [timestamp, location, crash_severity, crash_type, injuries, fatalities]
        pass
```

**Traffic Camera Plugin** (new):
```python
# app/core/data_sources/plugins/traffic_camera_plugin.py

class TrafficCameraDataSource(DataSourcePlugin):
    source_id = "traffic_cameras"
    source_name = "Traffic Camera Feeds"
    source_type = "stream"

    def configure(self, config: Dict[str, Any]):
        self.camera_urls = config.get('camera_urls', [])

    def collect(self, start_dt, end_dt) -> pd.DataFrame:
        # Analyze camera feeds for traffic volume, congestion
        # Return: [timestamp, camera_id, vehicle_count, congestion_level]
        pass
```

#### 1.4 Data Source Configuration Schema

Store configurations in database or config files:

```yaml
# config/data_sources.yaml

data_sources:
  - id: vcc_api
    enabled: true
    priority: 1
    collection_interval: 60  # seconds
    config:
      base_url: "https://vcc.vtti.vt.edu"
      client_id: "${VCC_CLIENT_ID}"
      client_secret: "${VCC_CLIENT_SECRET}"
      message_types: ["bsm", "psm", "mapdata", "spat"]

  - id: weather_api
    enabled: true
    priority: 2
    collection_interval: 300  # 5 minutes
    config:
      api_key: "${WEATHER_API_KEY}"
      locations:
        - lat: 38.856
          lon: -77.053
          name: "Arlington, VA"

  - id: vdot_crash
    enabled: true
    priority: 3
    collection_interval: 3600  # hourly
    config:
      connection_string: "${VDOT_DB_CONNECTION}"
      table: "crash_data"
      lookback_days: 7
```

---

### 2. Configurable Safety Index Framework

#### 2.1 Feature Definition Schema

Define all features in a configuration file:

```yaml
# config/safety_features.yaml

feature_groups:

  # VRU Features
  vru_features:
    enabled: true
    source: vcc_api
    features:
      - name: vru_conflict_rate
        description: "VRU-vehicle conflict incidents per hour"
        calculation: "count(vru_conflicts) / time_window_hours"
        normalization: "divide_by_max"
        weight: 0.30

      - name: vru_volume
        description: "Number of VRUs (pedestrians, cyclists) present"
        calculation: "count(distinct vru_ids)"
        normalization: "divide_by_max"
        weight: 0.15

      - name: vru_speed_variance
        description: "Variance in VRU speeds (unpredictability)"
        calculation: "stddev(vru_speeds)"
        normalization: "divide_by_max"
        weight: 0.10

  # Vehicle Features
  vehicle_features:
    enabled: true
    source: vcc_api
    features:
      - name: vehicle_conflict_rate
        description: "Vehicle-vehicle conflict incidents per hour"
        calculation: "count(vehicle_conflicts) / time_window_hours"
        normalization: "divide_by_max"
        weight: 0.25

      - name: vehicle_volume
        description: "Number of vehicles present"
        calculation: "count(distinct vehicle_ids)"
        normalization: "divide_by_max"
        weight: 0.10

      - name: speed_variance
        description: "Variance in vehicle speeds"
        calculation: "stddev(vehicle_speeds)"
        normalization: "divide_by_max"
        weight: 0.05

      - name: heading_change_rate
        description: "Rate of heading changes (erratic behavior)"
        calculation: "count(heading_changes > threshold) / vehicle_count"
        normalization: "divide_by_max"
        weight: 0.05

  # Weather Features (new)
  weather_features:
    enabled: false  # Disabled until weather plugin configured
    source: weather_api
    features:
      - name: precipitation_factor
        description: "Impact of precipitation on safety"
        calculation: "precipitation_mm * severity_multiplier"
        normalization: "divide_by_max"
        weight: 0.00  # Will tune after data collection

      - name: visibility_factor
        description: "Impact of reduced visibility"
        calculation: "max_visibility - current_visibility"
        normalization: "divide_by_max"
        weight: 0.00

  # Temporal Features
  temporal_features:
    enabled: true
    source: computed
    features:
      - name: rush_hour_factor
        description: "Increased risk during rush hours"
        calculation: "1.2 if hour in [7,8,9,16,17,18] else 1.0"
        normalization: "none"
        weight: 0.00  # Multiplier, not additive

      - name: weekend_factor
        description: "Different patterns on weekends"
        calculation: "0.9 if day_of_week in [5,6] else 1.0"
        normalization: "none"
        weight: 0.00

# Index Formulas
safety_indices:

  # VRU Safety Index
  vru_index:
    name: "VRU Safety Index"
    formula: "weighted_sum(vru_features) + weather_adjustment"
    components:
      - vru_conflict_rate
      - vru_volume
      - vru_speed_variance
      - precipitation_factor  # if enabled
      - visibility_factor     # if enabled

  # Vehicle Safety Index
  vehicle_index:
    name: "Vehicle Safety Index"
    formula: "weighted_sum(vehicle_features) + weather_adjustment"
    components:
      - vehicle_conflict_rate
      - vehicle_volume
      - speed_variance
      - heading_change_rate
      - precipitation_factor  # if enabled

  # Combined Safety Index
  combined_index:
    name: "Combined Safety Index"
    formula: "vru_index + vehicle_index"
    temporal_adjustments:
      - rush_hour_factor
      - weekend_factor
```

#### 2.2 Dynamic Feature Engine

```python
# app/core/features/dynamic_engine.py

class DynamicFeatureEngine:
    """Compute features based on configuration"""

    def __init__(self, config_path: str = "config/safety_features.yaml"):
        self.config = self._load_config(config_path)
        self.feature_groups = self._parse_feature_groups()

    def compute_features(
        self,
        data: Dict[str, pd.DataFrame],  # Data from all sources
        time_window: str = "15min"
    ) -> pd.DataFrame:
        """Compute all enabled features dynamically"""

        features = []

        for group_name, group_config in self.feature_groups.items():
            if not group_config['enabled']:
                continue

            source_data = data.get(group_config['source'])
            if source_data is None:
                continue

            for feature_def in group_config['features']:
                feature_values = self._compute_feature(
                    source_data,
                    feature_def,
                    time_window
                )
                features.append(feature_values)

        return pd.concat(features, axis=1)

    def compute_index(
        self,
        features_df: pd.DataFrame,
        index_name: str = "combined_index"
    ) -> pd.Series:
        """Compute safety index from features"""

        index_config = self.config['safety_indices'][index_name]
        components = index_config['components']

        # Weighted sum of components
        index_values = 0
        for component in components:
            if component in features_df.columns:
                weight = self._get_feature_weight(component)
                index_values += features_df[component] * weight

        # Apply temporal adjustments
        for adjustment in index_config.get('temporal_adjustments', []):
            if adjustment in features_df.columns:
                index_values *= features_df[adjustment]

        return index_values

    def update_weights(self, weight_updates: Dict[str, float]):
        """Update feature weights dynamically"""
        # Update config and persist
        pass
```

---

### 3. Admin UI / Configuration Dashboard

#### 3.1 Architecture

**Technology Stack**:
- **Frontend**: React + TypeScript (or Streamlit for rapid prototyping)
- **Backend**: FastAPI with admin endpoints
- **Visualization**: Plotly/Recharts for interactive charts
- **State Management**: React Context or Zustand

**Key Pages**:

1. **Data Sources Management**
   - List all registered data sources
   - Enable/disable sources
   - Configure source settings
   - View collection status and health
   - Test connections

2. **Feature Configuration**
   - List all feature groups
   - Enable/disable features
   - Adjust feature weights with sliders
   - Preview index changes in real-time
   - Export/import configurations

3. **Index Analysis Dashboard**
   - Side-by-side comparison of different index formulas
   - Historical index values with overlays
   - Correlation analysis between features
   - Feature importance visualization
   - A/B testing results

4. **Data Exploration**
   - Time-series visualizations for all data sources
   - Filter by intersection, time range, conditions
   - Export data for external analysis
   - Anomaly detection and highlighting

5. **Configuration History**
   - Track all configuration changes
   - Rollback to previous configurations
   - Compare configurations
   - Audit trail

#### 3.2 API Endpoints

```python
# app/api/admin/data_sources.py

@router.get("/admin/data-sources")
async def list_data_sources():
    """List all registered data sources with status"""
    pass

@router.post("/admin/data-sources/{source_id}/enable")
async def enable_data_source(source_id: str):
    """Enable a data source"""
    pass

@router.put("/admin/data-sources/{source_id}/config")
async def update_data_source_config(source_id: str, config: dict):
    """Update data source configuration"""
    pass

@router.get("/admin/data-sources/{source_id}/health")
async def check_data_source_health(source_id: str):
    """Check data source health"""
    pass

# app/api/admin/features.py

@router.get("/admin/features")
async def list_features():
    """List all features with current weights"""
    pass

@router.put("/admin/features/{feature_name}/weight")
async def update_feature_weight(feature_name: str, weight: float):
    """Update a feature weight"""
    pass

@router.post("/admin/features/preview")
async def preview_index_with_weights(weights: Dict[str, float]):
    """Preview what index would look like with new weights"""
    pass

@router.post("/admin/features/export")
async def export_feature_config():
    """Export current feature configuration"""
    pass

@router.post("/admin/features/import")
async def import_feature_config(config: UploadFile):
    """Import feature configuration"""
    pass

# app/api/admin/analysis.py

@router.get("/admin/analysis/correlation")
async def feature_correlation_matrix():
    """Get correlation matrix between features"""
    pass

@router.get("/admin/analysis/importance")
async def feature_importance():
    """Analyze feature importance for index prediction"""
    pass

@router.post("/admin/analysis/compare")
async def compare_index_formulas(formula_ids: List[str]):
    """Compare multiple index formulas side-by-side"""
    pass
```

#### 3.3 UI Wireframes (Key Screens)

**Feature Weight Tuning Screen**:
```
┌─────────────────────────────────────────────────────────────┐
│  Safety Index Configuration                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  VRU Features                                    [Enabled ✓] │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ VRU Conflict Rate          [====●======] 0.30         │  │
│  │ VRU Volume                 [===●=======] 0.15         │  │
│  │ VRU Speed Variance         [==●========] 0.10         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  Vehicle Features                                [Enabled ✓] │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Vehicle Conflict Rate      [=====●=====] 0.25         │  │
│  │ Vehicle Volume             [==●========] 0.10         │  │
│  │ Speed Variance             [=●=========] 0.05         │  │
│  │ Heading Change Rate        [=●=========] 0.05         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  Weather Features                                [Disabled ] │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Precipitation Factor       [●==========] 0.00         │  │
│  │ Visibility Factor          [●==========] 0.00         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  Real-time Preview:                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Current Index: 33.44                                  │  │
│  │  With New Weights: 35.21  (+1.77, +5.3%)             │  │
│  │                                                         │  │
│  │  [Show Historical Impact] [Apply Changes] [Reset]     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Data Source Management Screen**:
```
┌─────────────────────────────────────────────────────────────┐
│  Data Sources                              [+ Add New Source]│
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─ VCC API ──────────────────────────── [Enabled ✓] [⚙️]──┐│
│  │  Status: ● Healthy                    Last: 2 min ago    ││
│  │  Collection: Every 60s                Messages: 1,702    ││
│  │  Endpoint: https://vcc.vtti.vt.edu                       ││
│  │  [View Logs] [Test Connection] [Configure]              ││
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ Weather API ────────────────────────  [Enabled ✓] [⚙️]─┐│
│  │  Status: ● Healthy                    Last: 4 min ago    ││
│  │  Collection: Every 300s               Records: 284       ││
│  │  Provider: OpenWeatherMap                                ││
│  │  [View Logs] [Test Connection] [Configure]              ││
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ VDOT Crash Data ─────────────────────  [Disabled ] [⚙️]─┐│
│  │  Status: ⚠ Not Configured                                ││
│  │  Collection: Every 3600s              Records: 0         ││
│  │  Database: Not connected                                 ││
│  │  [Configure] [Enable]                                    ││
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Plugin Architecture (2-3 weeks)

**Objectives**:
- Implement base data source plugin framework
- Migrate existing VCC code to plugin architecture
- Create data source registry and configuration system
- Add basic admin API endpoints

**Deliverables**:
- `app/core/data_sources/` - Plugin framework
- `VCCDataSource` plugin (refactored from existing code)
- Configuration file support (YAML)
- Admin API endpoints for listing/managing sources

**Success Criteria**:
- Existing VCC functionality works through new plugin system
- Can enable/disable VCC plugin via config
- No regression in data collection

---

### Phase 2: Dynamic Feature Engine (2-3 weeks)

**Objectives**:
- Implement configurable feature definitions
- Create dynamic feature computation engine
- Migrate existing features to configuration format
- Add weight adjustment capability

**Deliverables**:
- `app/core/features/dynamic_engine.py` - Feature engine
- `config/safety_features.yaml` - Feature definitions
- Admin API endpoints for feature management
- Weight update persistence

**Success Criteria**:
- All existing features work through new engine
- Can adjust weights without code changes
- Index computation matches existing values

---

### Phase 3: New Data Source Integration (3-4 weeks)

**Objectives**:
- Implement 2-3 new data source plugins
- Test multi-source data collection
- Integrate new data into feature computations
- Validate data quality

**Recommended First Sources**:
1. **Weather API** (OpenWeatherMap, Weather Underground)
   - Impact: Precipitation, visibility, temperature
   - Relatively easy API integration

2. **VDOT Crash Data** (if accessible)
   - Validate indices against real crash history
   - Compute baseline event rates for Empirical Bayes

3. **Traffic Volume API** (VDOT Traffic Data, HERE, TomTom)
   - Additional traffic volume metrics
   - Validate BSM volume counts

**Deliverables**:
- Weather, VDOT, and Traffic plugins
- Configuration for each source
- Integration tests
- Documentation

**Success Criteria**:
- Multiple sources collecting simultaneously
- No performance degradation
- New features added to index computation

---

### Phase 4: Admin UI - Basic Features (3-4 weeks)

**Objectives**:
- Build core admin dashboard
- Implement data source management UI
- Create feature weight tuning interface
- Add real-time index preview

**Deliverables**:
- React admin dashboard
- Data source management page
- Feature configuration page
- Real-time preview functionality

**Success Criteria**:
- Can enable/disable data sources from UI
- Can adjust weights and see immediate preview
- Changes persist correctly

---

### Phase 5: Admin UI - Analysis Tools (2-3 weeks)

**Objectives**:
- Add data exploration and visualization
- Implement index comparison tools
- Create correlation and importance analysis
- Build configuration history/rollback

**Deliverables**:
- Data exploration dashboard
- Index comparison views
- Feature analysis tools
- Configuration versioning

**Success Criteria**:
- Can compare different index formulas
- Can identify which features matter most
- Can rollback to previous configurations

---

### Phase 6: A/B Testing Framework (2-3 weeks)

**Objectives**:
- Implement multiple index formula support
- Run parallel index computations
- Compare formulas against validation data
- Select optimal formula based on metrics

**Deliverables**:
- Multi-formula computation engine
- A/B testing framework
- Performance metrics computation
- Formula selection tools

**Success Criteria**:
- Can run 2+ index formulas simultaneously
- Can compare against crash data
- Can select best-performing formula

---

## Technical Specifications

### Database Schema Extensions

```sql
-- Data source configurations
CREATE TABLE data_source_configs (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) UNIQUE NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 10,
    collection_interval INTEGER,  -- seconds
    config JSONB,  -- Source-specific configuration
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Feature configurations
CREATE TABLE feature_configs (
    id SERIAL PRIMARY KEY,
    feature_name VARCHAR(100) UNIQUE NOT NULL,
    feature_group VARCHAR(100),
    description TEXT,
    weight DECIMAL(5, 4) DEFAULT 0.0,
    enabled BOOLEAN DEFAULT true,
    calculation_formula TEXT,
    normalization_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Configuration history (audit trail)
CREATE TABLE config_history (
    id SERIAL PRIMARY KEY,
    config_type VARCHAR(50),  -- 'data_source', 'feature', 'index'
    config_id INTEGER,
    changed_by VARCHAR(100),
    change_description TEXT,
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index formula definitions
CREATE TABLE index_formulas (
    id SERIAL PRIMARY KEY,
    formula_name VARCHAR(100) UNIQUE NOT NULL,
    formula_description TEXT,
    formula_definition JSONB,  -- Components, weights, adjustments
    active BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- A/B test results
CREATE TABLE index_test_results (
    id SERIAL PRIMARY KEY,
    formula_id INTEGER REFERENCES index_formulas(id),
    test_period_start TIMESTAMP,
    test_period_end TIMESTAMP,
    metrics JSONB,  -- Performance metrics
    validation_score DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Configuration File Structure

```
config/
├── data_sources.yaml          # Data source configurations
├── safety_features.yaml       # Feature definitions
├── index_formulas.yaml        # Index formula definitions
└── plugins/
    ├── vcc_plugin.yaml        # VCC-specific settings
    ├── weather_plugin.yaml    # Weather API settings
    └── vdot_plugin.yaml       # VDOT settings
```

### Performance Considerations

**Scalability**:
- **Multi-source Collection**: Use asyncio for parallel data collection
- **Feature Computation**: Cache intermediate results
- **Real-time Preview**: Compute only on affected subset
- **Database Queries**: Index all timestamp and intersection columns

**Optimization Strategies**:
1. **Lazy Loading**: Only load enabled plugins
2. **Caching**: Redis cache for feature computations
3. **Batch Processing**: Aggregate updates before writing
4. **Incremental Updates**: Only recompute changed features

---

## Success Metrics

### Technical Metrics
- Plugin load time: < 100ms per plugin
- Feature computation time: < 5s for 1 hour of data
- Admin UI response time: < 500ms for all operations
- Multi-source data collection: No degradation with 5+ sources

### User Experience Metrics
- Time to add new data source: < 30 minutes (from API key to collection)
- Time to adjust weights: < 5 minutes (from UI to deployed)
- Configuration rollback time: < 2 minutes
- Team member onboarding: < 1 hour to make first adjustment

### Business Metrics
- Index accuracy improvement: 10-20% with multi-source data
- False positive reduction: 15-25% with weather integration
- Team iteration speed: 5x faster with UI vs code changes

---

## Risk Assessment

### High Risk
1. **Performance Degradation**: Multiple data sources may slow system
   - **Mitigation**: Async collection, caching, monitoring

2. **Configuration Complexity**: Too many options may confuse users
   - **Mitigation**: Sensible defaults, presets, documentation

### Medium Risk
3. **Data Quality Issues**: New sources may have bad data
   - **Mitigation**: Validation layer, quality checks, alerting

4. **API Rate Limits**: External APIs may throttle requests
   - **Mitigation**: Respect rate limits, caching, fallbacks

### Low Risk
5. **UI Complexity**: Admin UI may be difficult to use
   - **Mitigation**: User testing, iteration, help tooltips

---

## Open Questions

1. **Configuration Storage**: Database vs. files vs. both?
   - **Recommendation**: Hybrid - files for defaults, database for runtime changes

2. **Multi-tenancy**: Should different teams have separate configurations?
   - **Discussion Needed**: Depends on deployment model

3. **Real-time vs. Batch**: Should weight changes apply to historical data?
   - **Recommendation**: Historical data keeps original weights, new data uses new weights

4. **Access Control**: Who can change configurations?
   - **Recommendation**: Role-based access (admin, analyst, viewer)

5. **Validation Data**: How to validate index improvements?
   - **Recommendation**: Integrate VDOT crash data, compute correlation with crashes

---

## Next Immediate Actions

1. **Review and Approve Roadmap** (User decision)
   - Confirm architecture approach
   - Prioritize phases
   - Identify must-have vs. nice-to-have features

2. **Prototype Plugin System** (1 week spike)
   - Build minimal plugin framework
   - Migrate VCC to plugin
   - Validate approach

3. **Design Admin UI Mockups** (1 week)
   - Create detailed wireframes
   - Get user feedback
   - Finalize screen designs

4. **Research Data Sources** (Ongoing)
   - Identify available APIs
   - Get API keys/credentials
   - Test data quality

5. **Set Up Project Tracking** (Immediate)
   - Create issues for each phase
   - Estimate effort
   - Assign priorities

---

## Resources Required

### Development
- **Backend Developer**: 0.5-1 FTE for 3-4 months
- **Frontend Developer**: 0.5 FTE for 2-3 months (Phase 4-5)
- **Data Engineer**: 0.25 FTE for data source integration

### Infrastructure
- **External APIs**: Budget for weather, traffic data subscriptions
- **Database**: PostgreSQL storage for configurations
- **Hosting**: Additional resources for admin UI

### Documentation
- **Technical Docs**: Plugin development guide
- **User Docs**: Admin UI user guide, video tutorials
- **API Docs**: Extended OpenAPI documentation

---

## References

- [Current Active Context](./active-context.md)
- [Operational Guide](./operational-guide.md)
- [Troubleshooting Guide](./troubleshooting.md)
- [Sprint Plan](../construction/sprint-plan.md)

---

**Status**: ✅ READY FOR REVIEW
**Next Step**: User approval and prioritization
**Estimated Timeline**: 4-6 months for full implementation
**Estimated Effort**: 15-20 weeks of development time
