# Design Document: Data Integration & Extensibility

**Feature:** Pluggable Data Source Architecture with Weather Integration
**Version:** 1.0
**Status:** Design Review
**Author:** Development Team
**Date:** 2025-11-21

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Component Design](#component-design)
4. [Database Design](#database-design)
5. [API Design](#api-design)
6. [Integration Points](#integration-points)
7. [Security Design](#security-design)
8. [Performance Design](#performance-design)
9. [Deployment Strategy](#deployment-strategy)
10. [Testing Strategy](#testing-strategy)

---

## Overview

### Problem Statement

The current Traffic Safety Index system has hard-coded VCC API integration and fixed safety index formulas, preventing:
- Adding new data sources without code changes
- Adjusting safety index weights based on validation results
- Domain expert tuning without developer intervention

### Solution Overview

Implement a plugin-based architecture that:
1. Abstracts data source integration behind a common interface
2. Refactors VCC as the first plugin (backward compatible)
3. Adds NOAA/NWS weather as the second plugin
4. Enables configuration-driven feature weights
5. Provides UI transparency into safety index calculation

### Design Principles

1. **Backward Compatibility** - Existing functionality unaffected
2. **Fail Independently** - One plugin failure doesn't crash others
3. **Triple-Write Consistency** - Maintain Parquet + PostgreSQL + GCS
4. **Configuration Over Code** - No code changes to add data sources
5. **Transparency First** - Users see how scores are calculated

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Data Collector Service                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Plugin Registry & Orchestrator              │   │
│  │                                                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │  VCC Plugin  │  │ NOAA Plugin  │  │Future Plugins│  │   │
│  │  │  (Weight:70%)│  │ (Weight:15%) │  │ (Weight:15%) │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │   │
│  │         │                  │                  │           │   │
│  └─────────┼──────────────────┼──────────────────┼──────────┘   │
│            │                  │                  │               │
│  ┌─────────▼──────────────────▼──────────────────▼──────────┐  │
│  │         Feature Aggregation & Normalization               │  │
│  └─────────┬───────────────────────────────────────────────┬─┘  │
│            │                                                 │    │
│  ┌─────────▼──────────────────────────────────────┐        │    │
│  │    Safety Index Computation (Multi-Source)      │        │    │
│  └─────────┬────────────────────────────────────────┘       │    │
│            │                                                 │    │
│  ┌─────────▼────────────┬──────────────┬───────────────────▼┐   │
│  │  Parquet Storage     │ PostgreSQL   │    GCS Archive      │   │
│  │  (Local, Immediate)  │ (Query, Fast)│  (Cloud, Long-term) │   │
│  └──────────────────────┴──────────────┴─────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Backend API                              │
│                                                                   │
│  ┌────────────────────┐  ┌─────────────────────────────────┐   │
│  │  Safety Index API  │  │  Plugin Management API (Admin)  │   │
│  │  - Get scores      │  │  - List plugins                  │   │
│  │  - Get breakdown   │  │  - Update weights                │   │
│  │  - Historical data │  │  - Health checks                 │   │
│  └────────────────────┘  └─────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Dashboard                        │
│                                                                   │
│  ┌────────────────────┐  ┌─────────────────────────────────┐   │
│  │  Safety Index Map  │  │  Formula Transparency Panel      │   │
│  │  (with weather)    │  │  - Feature breakdown             │   │
│  └────────────────────┘  │  - Weight visualization          │   │
│                           │  - Plugin status                 │   │
│                           └─────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### Data Flow

**Current Data Collection (with Weather):**
```
Every 60 seconds:

1. Plugin Registry triggers collection
   ├─> VCC Plugin fetches BSM/PSM/MapData
   └─> NOAA Plugin fetches weather observations

2. Feature Engineering
   ├─> VCC Plugin: Extract traffic features (conflicts, TTC, proximity)
   └─> NOAA Plugin: Extract weather features (precipitation, visibility, wind)

3. Feature Aggregation
   └─> Merge features by timestamp and location

4. Safety Index Calculation
   └─> weighted_sum = (VCC_features × 0.70) + (Weather_features × 0.15)

5. Triple-Write Storage
   ├─> Parquet: Local file /app/data/parquet/indices/YYYY/MM/DD/indices_*.parquet
   ├─> PostgreSQL: safety_indices_realtime table
   └─> GCS: gs://bucket/processed/indices/YYYY/MM/DD/indices_*.parquet
```

---

## Component Design

### 1. Plugin Base Class

**File:** `backend/app/plugins/base.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from pydantic import BaseModel, Field


class PluginMetadata(BaseModel):
    """Plugin metadata"""
    name: str
    version: str = "1.0.0"
    description: str
    author: str
    enabled: bool = True
    weight: float = Field(ge=0.0, le=1.0, default=0.0)


class PluginHealthStatus(BaseModel):
    """Plugin health check result"""
    healthy: bool
    message: str
    last_check: datetime
    latency_ms: Optional[float] = None


class DataSourcePlugin(ABC):
    """
    Abstract base class for all data source plugins.

    All data sources must implement this interface to integrate
    with the Traffic Safety Index system.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plugin with configuration.

        Args:
            config: Plugin-specific configuration dictionary
        """
        self.config = config
        self.metadata = self._init_metadata()
        self._validate_config()

    @abstractmethod
    def _init_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass

    @abstractmethod
    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Collect data for the specified time range.

        Args:
            start_time: Start of collection window
            end_time: End of collection window

        Returns:
            DataFrame with columns: [timestamp, feature1, feature2, ...]

        Raises:
            PluginCollectionError: If data collection fails
        """
        pass

    @abstractmethod
    def get_features(self) -> List[str]:
        """
        Return list of feature names this plugin provides.

        Returns:
            List of feature column names (e.g., ['weather_precipitation', ...])
        """
        pass

    @abstractmethod
    def health_check(self) -> PluginHealthStatus:
        """
        Verify plugin can connect to data source.

        Returns:
            PluginHealthStatus with result and diagnostic info
        """
        pass

    def _validate_config(self):
        """Validate plugin configuration (override if needed)"""
        pass

    def get_weight(self) -> float:
        """Return configured weight for this plugin's features"""
        return self.metadata.weight

    def is_enabled(self) -> bool:
        """Check if plugin is enabled"""
        return self.metadata.enabled
```

**Design Decisions:**
- Pydantic models for type safety and validation
- Health check returns structured status (not just bool)
- Weight stored in metadata for easy access
- Abstract `_validate_config()` for plugin-specific validation

---

### 2. Plugin Registry

**File:** `backend/app/plugins/registry.py`

```python
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.plugins.base import DataSourcePlugin, PluginHealthStatus


logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Centralized registry for managing data source plugins.

    Responsibilities:
    - Register and store plugin instances
    - Orchestrate parallel data collection
    - Aggregate features from multiple plugins
    - Handle plugin failures gracefully
    - Monitor plugin health
    """

    def __init__(self, max_workers: int = 5):
        self.plugins: Dict[str, DataSourcePlugin] = {}
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def register(self, name: str, plugin: DataSourcePlugin):
        """
        Register a plugin instance.

        Args:
            name: Unique plugin identifier
            plugin: Plugin instance

        Raises:
            ValueError: If plugin name already registered
        """
        if name in self.plugins:
            raise ValueError(f"Plugin '{name}' already registered")

        self.plugins[name] = plugin
        logger.info(f"Registered plugin: {name} (weight: {plugin.get_weight():.2f})")

    def get_plugin(self, name: str) -> Optional[DataSourcePlugin]:
        """Get plugin by name"""
        return self.plugins.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins with metadata"""
        return [
            {
                "name": name,
                "enabled": plugin.is_enabled(),
                "weight": plugin.get_weight(),
                "features": plugin.get_features(),
                "metadata": plugin.metadata.dict()
            }
            for name, plugin in self.plugins.items()
        ]

    def collect_all(
        self,
        start_time: datetime,
        end_time: datetime,
        fail_fast: bool = False
    ) -> pd.DataFrame:
        """
        Collect data from all enabled plugins in parallel.

        Args:
            start_time: Start of collection window
            end_time: End of collection window
            fail_fast: If True, raise on first plugin failure

        Returns:
            DataFrame with merged features from all plugins

        Note:
            Individual plugin failures are logged but don't stop other plugins
            unless fail_fast=True.
        """
        futures = {}
        results = {}

        # Submit collection tasks for enabled plugins
        for name, plugin in self.plugins.items():
            if not plugin.is_enabled():
                logger.debug(f"Skipping disabled plugin: {name}")
                continue

            future = self._executor.submit(
                self._collect_with_error_handling,
                name,
                plugin,
                start_time,
                end_time
            )
            futures[future] = name

        # Gather results
        for future in as_completed(futures):
            plugin_name = futures[future]
            try:
                data = future.result()
                if data is not None and not data.empty:
                    results[plugin_name] = data
                    logger.debug(f"Plugin {plugin_name} collected {len(data)} rows")
            except Exception as e:
                logger.error(f"Plugin {plugin_name} collection failed: {e}")
                if fail_fast:
                    raise

        # Merge all plugin data
        if not results:
            logger.warning("No plugin data collected")
            return pd.DataFrame()

        return self._merge_plugin_data(results)

    def _collect_with_error_handling(
        self,
        name: str,
        plugin: DataSourcePlugin,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[pd.DataFrame]:
        """Wrapper for plugin collection with error handling"""
        try:
            return plugin.collect(start_time, end_time)
        except Exception as e:
            logger.error(f"Plugin {name} failed: {e}", exc_info=True)
            return None

    def _merge_plugin_data(self, results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Merge data from multiple plugins.

        Strategy:
        - Outer join on timestamp (keep all timestamps from all plugins)
        - Fill missing values with plugin-specific defaults or NaN
        """
        if len(results) == 1:
            return list(results.values())[0]

        # Merge all DataFrames on timestamp
        merged = None
        for plugin_name, df in results.items():
            if 'timestamp' not in df.columns:
                logger.warning(f"Plugin {plugin_name} missing 'timestamp' column, skipping")
                continue

            if merged is None:
                merged = df
            else:
                merged = pd.merge(
                    merged,
                    df,
                    on='timestamp',
                    how='outer',
                    suffixes=('', f'_{plugin_name}')
                )

        return merged if merged is not None else pd.DataFrame()

    def health_check_all(self) -> Dict[str, PluginHealthStatus]:
        """Run health checks on all plugins"""
        results = {}
        for name, plugin in self.plugins.items():
            try:
                status = plugin.health_check()
                results[name] = status
            except Exception as e:
                results[name] = PluginHealthStatus(
                    healthy=False,
                    message=f"Health check failed: {str(e)}",
                    last_check=datetime.now()
                )
        return results

    def validate_weights(self) -> Dict[str, Any]:
        """
        Validate that enabled plugin weights sum to approximately 1.0.

        Returns:
            Validation result with details
        """
        enabled_plugins = [p for p in self.plugins.values() if p.is_enabled()]
        total_weight = sum(p.get_weight() for p in enabled_plugins)

        is_valid = abs(total_weight - 1.0) < 0.01  # Allow 1% tolerance

        return {
            "valid": is_valid,
            "total_weight": total_weight,
            "expected": 1.0,
            "plugins": {
                name: plugin.get_weight()
                for name, plugin in self.plugins.items()
                if plugin.is_enabled()
            }
        }

    def shutdown(self):
        """Shutdown executor and cleanup resources"""
        self._executor.shutdown(wait=True)
        logger.info("Plugin registry shut down")
```

**Design Decisions:**
- Thread pool for parallel collection (I/O bound operations)
- Fail-safe by default (one plugin failure doesn't stop others)
- Outer join merge strategy (keep all timestamps)
- Weight validation with tolerance (floating point comparison)

---

### 3. VCC Plugin Implementation

**File:** `backend/app/plugins/vcc_plugin.py`

```python
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import time

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from app.services.vcc_client import VCCClient
from app.services.vcc_feature_engineering import (
    extract_bsm_features,
    extract_psm_features,
    detect_vru_vehicle_conflicts,
    detect_vehicle_vehicle_conflicts
)


class VCCPlugin(DataSourcePlugin):
    """
    VCC (Virginia Connected Corridors) data source plugin.

    Collects Basic Safety Messages (BSM), Pedestrian Safety Messages (PSM),
    and MapData from VCC API, then extracts traffic safety features.
    """

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
        """
        Collect VCC data and extract traffic features.

        Returns:
            DataFrame with columns:
            - timestamp
            - intersection_id
            - vcc_conflict_count
            - vcc_ttc_min
            - vcc_proximity_score
            - vcc_speed_variance
            - vcc_acceleration_events
        """
        # Fetch raw messages
        bsm_messages = self.client.fetch_bsm_messages(start_time, end_time)
        psm_messages = self.client.fetch_psm_messages(start_time, end_time)
        mapdata = self.client.fetch_mapdata()

        if not bsm_messages:
            return pd.DataFrame()  # No data available

        # Extract features
        bsm_features = extract_bsm_features(bsm_messages)
        psm_features = extract_psm_features(psm_messages) if psm_messages else pd.DataFrame()

        # Detect conflicts
        vru_conflicts = detect_vru_vehicle_conflicts(bsm_messages, psm_messages, mapdata)
        veh_conflicts = detect_vehicle_vehicle_conflicts(bsm_messages, mapdata)

        # Merge features
        features = self._merge_features(bsm_features, psm_features, vru_conflicts, veh_conflicts)

        # Add timestamp column
        features['timestamp'] = pd.to_datetime(features['time_15min'])

        return features[['timestamp', 'intersection_id', 'vcc_conflict_count',
                        'vcc_ttc_min', 'vcc_proximity_score', 'vcc_speed_variance',
                        'vcc_acceleration_events']]

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
        start = time.time()
        try:
            token = self.client.get_access_token()
            latency = (time.time() - start) * 1000

            if token:
                return PluginHealthStatus(
                    healthy=True,
                    message="VCC API authentication successful",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message="Failed to obtain access token",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"VCC API error: {str(e)}",
                last_check=datetime.now()
            )

    def _merge_features(self, bsm_features, psm_features, vru_conflicts, veh_conflicts):
        """Merge all VCC features into single DataFrame"""
        # Implementation: Join on intersection_id and time window
        # ... (existing logic from current system)
        pass
```

---

### 4. NOAA Weather Plugin Implementation

**File:** `backend/app/plugins/noaa_weather_plugin.py`

```python
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import requests
import time
import logging

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus


logger = logging.getLogger(__name__)


class NOAAWeatherPlugin(DataSourcePlugin):
    """
    NOAA/NWS weather data source plugin.

    Collects weather observations from NOAA API for specified weather station.
    """

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
        self.station_id = config['station_id']  # Required
        self.user_agent = config.get('user_agent', 'TrafficSafetyIndex/1.0 (contact@example.com)')
        self.timeout = config.get('timeout', 10)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 2)

    def _validate_config(self):
        """Validate required configuration"""
        if not self.station_id:
            raise ValueError("NOAA plugin requires 'station_id' in config")

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Collect weather observations for time range.

        Returns:
            DataFrame with columns:
            - timestamp
            - weather_temperature_c
            - weather_precipitation_mm
            - weather_visibility_m
            - weather_wind_speed_ms
            - weather_wind_direction_deg
            - weather_condition
        """
        observations = self._fetch_observations(start_time, end_time)

        if not observations:
            logger.warning(f"No weather observations for {start_time} to {end_time}")
            return pd.DataFrame()

        # Parse observations into DataFrame
        data = []
        for obs in observations:
            props = obs.get('properties', {})

            # Extract values (NOAA uses nested "value" objects)
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

        # Normalize features to 0-1 scale
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
        start = time.time()
        try:
            url = f"{self.api_base}/stations/{self.station_id}"
            response = self._make_request(url)
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                station = response.json()
                return PluginHealthStatus(
                    healthy=True,
                    message=f"Station {self.station_id} ({station.get('properties', {}).get('name', 'Unknown')}) accessible",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message=f"Station returned HTTP {response.status_code}",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
        except Exception as e:
            return PluginHealthStatus(
                healthy=False,
                message=f"NOAA API error: {str(e)}",
                last_check=datetime.now()
            )

    def _fetch_observations(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Fetch observations from NOAA API with retry logic"""
        url = f"{self.api_base}/stations/{self.station_id}/observations"
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat()
        }

        for attempt in range(self.retry_attempts):
            try:
                response = self._make_request(url, params=params)
                response.raise_for_status()

                data = response.json()
                return data.get('features', [])

            except requests.exceptions.RequestException as e:
                logger.warning(f"NOAA API request failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")

                if attempt < self.retry_attempts - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise

    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request with required User-Agent header"""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/geo+json'
        }

        return requests.get(url, params=params, headers=headers, timeout=self.timeout)

    def _extract_value(self, value_obj: Optional[Dict]) -> Optional[float]:
        """Extract numeric value from NOAA value object"""
        if value_obj is None:
            return None

        if isinstance(value_obj, dict):
            return value_obj.get('value')

        return value_obj

    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize weather features to 0-1 scale.

        Normalization strategy:
        - Precipitation: 0 mm = 0.0, 20+ mm/hour = 1.0 (heavy rain)
        - Visibility: 10+ km = 0.0 (good), 0 m = 1.0 (zero visibility)
        - Wind speed: 0 m/s = 0.0, 25+ m/s = 1.0 (high wind)
        - Temperature: -20°C or 45°C = 1.0 (extreme), 15-25°C = 0.0 (optimal)
        """
        df = df.copy()

        # Precipitation (higher = worse)
        if 'weather_precipitation_mm' in df.columns:
            df['weather_precipitation_mm'] = df['weather_precipitation_mm'].fillna(0)
            df['weather_precipitation_normalized'] = (df['weather_precipitation_mm'] / 20.0).clip(0, 1)

        # Visibility (lower = worse, so invert)
        if 'weather_visibility_m' in df.columns:
            df['weather_visibility_m'] = df['weather_visibility_m'].fillna(10000)
            df['weather_visibility_normalized'] = 1.0 - (df['weather_visibility_m'] / 10000.0).clip(0, 1)

        # Wind speed (higher = worse)
        if 'weather_wind_speed_ms' in df.columns:
            df['weather_wind_speed_ms'] = df['weather_wind_speed_ms'].fillna(0)
            df['weather_wind_speed_normalized'] = (df['weather_wind_speed_ms'] / 25.0).clip(0, 1)

        # Temperature (extremes = worse)
        if 'weather_temperature_c' in df.columns:
            df['weather_temperature_c'] = df['weather_temperature_c'].fillna(20)
            # U-shaped risk: 20°C = 0.0 (optimal), <0°C or >35°C = 1.0 (extreme)
            optimal = 20.0
            df['weather_temperature_normalized'] = df['weather_temperature_c'].apply(
                lambda t: min(abs(t - optimal) / 20.0, 1.0)
            )

        return df
```

**Design Decisions:**
- Exponential backoff for API failures
- User-Agent required by NOAA API
- Normalization built into plugin (domain-specific knowledge)
- Missing values filled with reasonable defaults

---

## Database Design

### New Tables

#### 1. weather_observations

```sql
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

    -- Normalized features (0-1 scale for safety index)
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

-- Partitioning (same strategy as safety_indices_realtime)
-- Monthly partitions for efficient time-range queries
CREATE INDEX idx_weather_obs_time ON weather_observations(observation_time);
CREATE INDEX idx_weather_obs_station ON weather_observations(station_id);
CREATE INDEX idx_weather_obs_created ON weather_observations(created_at);
```

#### 2. data_source_plugins

```sql
CREATE TABLE data_source_plugins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- Configuration
    enabled BOOLEAN DEFAULT true,
    weight FLOAT DEFAULT 0.0 CHECK (weight >= 0.0 AND weight <= 1.0),
    config JSONB,  -- Plugin-specific configuration

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Audit
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Example data:
-- INSERT INTO data_source_plugins (name, class_name, enabled, weight, config) VALUES
-- ('vcc', 'VCCPlugin', true, 0.70, '{"base_url": "https://vcc.vtti.vt.edu"}'),
-- ('noaa_weather', 'NOAAWeatherPlugin', true, 0.15, '{"station_id": "KRIC"}');
```

#### 3. feature_weight_history

```sql
CREATE TABLE feature_weight_history (
    id BIGSERIAL PRIMARY KEY,
    plugin_name VARCHAR(50) NOT NULL REFERENCES data_source_plugins(name),
    feature_name VARCHAR(100),

    -- Weight change
    old_weight FLOAT,
    new_weight FLOAT NOT NULL CHECK (new_weight >= 0.0 AND new_weight <= 1.0),

    -- Audit trail
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by VARCHAR(100) NOT NULL,
    reason TEXT,

    -- Impact tracking
    affected_indices_count INT,  -- How many safety indices recalculated
    average_score_change FLOAT   -- Average change in safety scores
);

CREATE INDEX idx_feature_weight_history_time ON feature_weight_history(changed_at DESC);
CREATE INDEX idx_feature_weight_history_plugin ON feature_weight_history(plugin_name);
```

### Schema Updates

#### Extend safety_indices_realtime

```sql
ALTER TABLE safety_indices_realtime
    -- Add weather feature columns
    ADD COLUMN weather_precipitation_normalized FLOAT CHECK (weather_precipitation_normalized >= 0 AND weather_precipitation_normalized <= 1),
    ADD COLUMN weather_visibility_normalized FLOAT CHECK (weather_visibility_normalized >= 0 AND weather_visibility_normalized <= 1),
    ADD COLUMN weather_wind_speed_normalized FLOAT CHECK (weather_wind_speed_normalized >= 0 AND weather_wind_speed_normalized <= 1),
    ADD COLUMN weather_temperature_normalized FLOAT CHECK (weather_temperature_normalized >= 0 AND weather_temperature_normalized <= 1),

    -- Track plugin contributions
    ADD COLUMN vcc_contribution FLOAT,      -- VCC portion of safety_index
    ADD COLUMN weather_contribution FLOAT,  -- Weather portion of safety_index

    -- Formula version for A/B testing
    ADD COLUMN formula_version VARCHAR(20) DEFAULT 'v2.0';
```

---

## API Design

### New Endpoints

#### 1. Plugin Management API

**GET /api/v1/plugins**
```json
{
  "plugins": [
    {
      "name": "vcc",
      "enabled": true,
      "weight": 0.70,
      "features": ["vcc_conflict_count", "vcc_ttc_min", "vcc_proximity_score"],
      "health": {
        "healthy": true,
        "message": "VCC API authentication successful",
        "last_check": "2025-11-21T14:30:00Z",
        "latency_ms": 145
      },
      "metadata": {
        "version": "1.0.0",
        "description": "Virginia Connected Corridors traffic data source"
      }
    },
    {
      "name": "noaa_weather",
      "enabled": true,
      "weight": 0.15,
      "features": ["weather_precipitation", "weather_visibility", "weather_wind_speed"],
      "health": {
        "healthy": true,
        "message": "Station KRIC (Richmond International Airport) accessible",
        "last_check": "2025-11-21T14:30:15Z",
        "latency_ms": 892
      }
    }
  ],
  "total_weight": 0.85,
  "weight_validation": {
    "valid": false,
    "message": "Total weight should be 1.0 (currently 0.85)"
  }
}
```

**POST /api/v1/plugins/{plugin_name}/weight** (Admin only)
```json
Request:
{
  "weight": 0.20,
  "reason": "Increased weather impact based on crash correlation analysis"
}

Response:
{
  "plugin_name": "noaa_weather",
  "old_weight": 0.15,
  "new_weight": 0.20,
  "changed_at": "2025-11-21T14:35:00Z",
  "changed_by": "admin@example.com",
  "validation": {
    "valid": true,
    "total_weight": 0.90
  }
}
```

**GET /api/v1/plugins/health**
```json
{
  "overall_healthy": true,
  "plugins": {
    "vcc": {
      "healthy": true,
      "latency_ms": 145
    },
    "noaa_weather": {
      "healthy": true,
      "latency_ms": 892
    }
  },
  "last_check": "2025-11-21T14:30:00Z"
}
```

#### 2. Safety Index Transparency API

**GET /api/v1/safety-index/{intersection_id}/breakdown**
```json
{
  "intersection_id": "I-001",
  "timestamp": "2025-11-21T14:15:00Z",
  "safety_index": 0.67,
  "risk_level": "MODERATE",

  "breakdown": {
    "vcc": {
      "weight": 0.70,
      "contribution": 0.504,
      "features": {
        "vcc_conflict_count": {
          "raw_value": 12,
          "normalized": 0.72,
          "description": "Number of vehicle conflicts detected"
        },
        "vcc_ttc_min": {
          "raw_value": 1.8,
          "normalized": 0.65,
          "description": "Minimum time-to-collision (seconds)"
        },
        "vcc_proximity_score": {
          "raw_value": 0.58,
          "normalized": 0.58,
          "description": "Proximity hazard score"
        }
      },
      "aggregated_score": 0.72
    },
    "noaa_weather": {
      "weight": 0.15,
      "contribution": 0.128,
      "features": {
        "weather_precipitation": {
          "raw_value": 5.2,
          "normalized": 0.26,
          "description": "Precipitation (mm/hour)"
        },
        "weather_visibility": {
          "raw_value": 200,
          "normalized": 0.98,
          "description": "Visibility (meters)"
        },
        "weather_wind_speed": {
          "raw_value": 8.0,
          "normalized": 0.32,
          "description": "Wind speed (m/s)"
        }
      },
      "aggregated_score": 0.85
    }
  },

  "calculation": "0.67 = (0.72 × 0.70) + (0.85 × 0.15)",
  "formula_version": "v2.0"
}
```

#### 3. Weather Data API

**GET /api/v1/weather/{station_id}/current**
```json
{
  "station_id": "KRIC",
  "observation_time": "2025-11-21T14:00:00Z",
  "temperature_c": 18.5,
  "precipitation_mm": 0.0,
  "visibility_m": 16000,
  "wind_speed_ms": 4.2,
  "wind_direction_deg": 180,
  "weather_condition": "Partly Cloudy"
}
```

**GET /api/v1/weather/{station_id}/history**
```
Query params: start_time, end_time, interval (hourly|daily)
```

---

## Integration Points

### 1. Data Collector Integration

**File:** `backend/data_collector.py`

```python
from app.plugins.registry import PluginRegistry
from app.plugins.vcc_plugin import VCCPlugin
from app.plugins.noaa_weather_plugin import NOAAWeatherPlugin

class DataCollector:
    def __init__(self, ...):
        # ... existing initialization ...

        # Initialize plugin registry
        self.plugin_registry = PluginRegistry()

        # Register VCC plugin
        vcc_config = {
            'base_url': settings.VCC_BASE_URL,
            'client_id': settings.VCC_CLIENT_ID,
            'client_secret': settings.VCC_CLIENT_SECRET,
            'enabled': True,
            'weight': 0.70
        }
        self.plugin_registry.register('vcc', VCCPlugin(vcc_config))

        # Register Weather plugin (if enabled)
        if settings.ENABLE_WEATHER_PLUGIN:
            weather_config = {
                'station_id': settings.WEATHER_STATION_ID,
                'enabled': True,
                'weight': 0.15
            }
            self.plugin_registry.register('noaa_weather', NOAAWeatherPlugin(weather_config))

    def collect_cycle(self) -> bool:
        start_time = datetime.now() - timedelta(minutes=15)
        end_time = datetime.now()

        # Collect from all plugins
        all_features = self.plugin_registry.collect_all(start_time, end_time)

        # Compute safety index with multi-source features
        indices_df = compute_safety_indices_multisource(all_features)

        # Triple-write (Parquet + PostgreSQL + GCS)
        self.save_safety_indices_triple_write(indices_df)
```

### 2. Safety Index Computation Integration

**File:** `backend/app/services/index_computation.py`

```python
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

    # Compute weighted sum
    indices = []
    for idx, row in features_df.iterrows():
        vcc_score = compute_vcc_score(row, norm_constants)
        weather_score = compute_weather_score(row, norm_constants)

        safety_index = (
            vcc_score * plugin_weights.get('vcc', 0.0) +
            weather_score * plugin_weights.get('noaa_weather', 0.0)
        )

        indices.append({
            'intersection_id': row['intersection_id'],
            'time_15min': row['timestamp'],
            'safety_index': safety_index,
            'vcc_contribution': vcc_score * plugin_weights.get('vcc', 0.0),
            'weather_contribution': weather_score * plugin_weights.get('noaa_weather', 0.0),
            'formula_version': 'v2.0'
        })

    return pd.DataFrame(indices)
```

### 3. Frontend Dashboard Integration

**Component:** `frontend/src/components/SafetyIndexBreakdown.tsx`

```typescript
interface FeatureBreakdown {
  plugin_name: string;
  weight: number;
  contribution: number;
  features: {
    [key: string]: {
      raw_value: number;
      normalized: number;
      description: string;
    };
  };
  aggregated_score: number;
}

function SafetyIndexBreakdown({ intersectionId, timestamp }: Props) {
  const { data, loading } = useSafetyIndexBreakdown(intersectionId, timestamp);

  return (
    <div className="breakdown-panel">
      <h3>Safety Index: {data.safety_index.toFixed(2)} ({data.risk_level})</h3>

      {Object.entries(data.breakdown).map(([pluginName, breakdown]) => (
        <PluginSection key={pluginName}>
          <h4>{pluginName} (Weight: {breakdown.weight * 100}%)</h4>
          <ProgressBar
            value={breakdown.contribution}
            max={1.0}
            color={getPluginColor(pluginName)}
          />

          <FeatureTable>
            {Object.entries(breakdown.features).map(([feature, data]) => (
              <FeatureRow key={feature}>
                <td>{data.description}</td>
                <td>{data.raw_value}</td>
                <td>{data.normalized.toFixed(2)}</td>
              </FeatureRow>
            ))}
          </FeatureTable>
        </PluginSection>
      ))}

      <Formula>{data.calculation}</Formula>
    </div>
  );
}
```

---

## Security Design

### Authentication & Authorization

1. **Admin-Only Weight Adjustment**
   - Require JWT authentication
   - Check `admin` role in token claims
   - Log all weight changes with user ID

2. **Plugin Configuration Security**
   - Store credentials in environment variables (not database)
   - Never expose credentials in API responses
   - Redact sensitive config in logs

3. **Data Validation**
   - Sanitize all NOAA API responses
   - Validate numeric ranges before database insertion
   - Prevent SQL injection through parameterized queries

### Rate Limiting

1. **NOAA API Protection**
   - Max 1 request/second for current data
   - Backfill: Max 10 requests/second with exponential backoff
   - Circuit breaker after 5 consecutive failures

2. **Internal API Protection**
   - Weight adjustment: Max 10 requests/hour per user
   - Plugin health checks: Cached for 5 minutes

---

## Performance Design

### Performance Targets

| Metric | Target | Current (VCC only) | With Weather |
|--------|--------|-------------------|--------------|
| Data Collection Latency | <3 seconds | 2.1s | <3.0s |
| Safety Index Calculation | <100ms | 45ms | <100ms |
| API Response Time (current) | <200ms | 120ms | <200ms |
| API Response Time (history) | <2s | 1.8s | <2.0s |
| Database Query Time | <50ms | 35ms | <50ms |

### Optimization Strategies

1. **Parallel Plugin Collection**
   - ThreadPoolExecutor for I/O-bound plugin calls
   - Max 5 concurrent plugin collections
   - Timeout per plugin: 5 seconds

2. **Database Indexing**
   - Index on `weather_observations(observation_time, station_id)`
   - Partitioned tables for time-series data
   - Materialized views for aggregated weather stats

3. **Caching**
   - Redis cache for plugin health checks (5 min TTL)
   - Weather observations cache (15 min TTL)
   - Plugin weight configuration (1 hour TTL, invalidate on update)

4. **Query Optimization**
   - Batch insert for weather backfill (1000 rows/batch)
   - Prepared statements for repeated queries
   - Connection pooling (min: 5, max: 20)

---

## Deployment Strategy

### Phase 1: Plugin Architecture (Week 1-2)

**Feature Flag:** `ENABLE_DATA_PLUGINS=false`

1. Deploy plugin base classes and registry
2. Run unit tests and integration tests
3. No user-facing changes (backend only)

### Phase 2: VCC Plugin Migration (Week 2)

**Feature Flag:** `USE_VCC_PLUGIN=false`

1. Deploy VCC plugin alongside existing VCC client
2. Run both in parallel (dual collection)
3. Compare outputs for 48 hours
4. Gradual rollout: 10% → 50% → 100%

### Phase 3: Weather Plugin (Week 3)

**Feature Flag:** `ENABLE_WEATHER_PLUGIN=false`

1. Deploy NOAA weather plugin
2. Start collecting current weather data
3. DO NOT integrate with safety index yet (weight=0.0)
4. Monitor for 1 week to ensure stability

### Phase 4: Historical Backfill (Week 3-4)

**Script:** `python scripts/backfill_weather.py`

1. Run backfill during low-traffic hours (overnight)
2. Process in batches (1 day at a time)
3. Validate data quality after each batch
4. Monitor database performance

### Phase 5: Safety Index Integration (Week 4)

**Feature Flag:** `USE_WEATHER_IN_INDEX=false`

1. Enable weather in safety index calculation
2. Store both old and new formulas for comparison
3. Dashboard shows side-by-side comparison
4. Gradual rollout: 10% → 50% → 100%

### Phase 6: UI Transparency (Week 5)

1. Deploy formula breakdown API endpoints
2. Deploy dashboard components
3. User documentation and training

### Phase 7: Validation & Tuning (Week 5-6)

1. Run crash correlation analysis
2. Optimize feature weights
3. Generate validation report
4. Adjust weights based on findings

### Rollback Plan

If issues occur at any phase:

1. **Disable feature flag** - Instant rollback
2. **Database rollback** - Restore from backup
3. **Code rollback** - Revert to previous deployment
4. **Monitoring** - Watch error rates, latency, data quality

---

## Testing Strategy

### Unit Tests

**Files:**
- `tests/test_plugin_base.py` - Plugin interface tests
- `tests/test_plugin_registry.py` - Registry logic tests
- `tests/test_vcc_plugin.py` - VCC plugin tests
- `tests/test_noaa_plugin.py` - Weather plugin tests

**Coverage Target:** ≥80% for all plugin code

### Integration Tests

**Test Scenarios:**
1. Plugin collection with mock API responses
2. Multi-plugin aggregation
3. Weight validation
4. Plugin failure handling
5. Triple-write with weather data

### Performance Tests

**Tools:** `pytest-benchmark`, `locust`

**Tests:**
1. Plugin collection latency
2. Safety index calculation with weather
3. API endpoint response times
4. Database query performance
5. Backfill throughput

### End-to-End Tests

**Scenarios:**
1. Full data collection cycle with weather
2. Weight adjustment through UI
3. Formula transparency display
4. Historical backfill (small dataset)
5. Plugin failure recovery

---

## Monitoring & Observability

### Metrics

**Plugin Health:**
- `plugin_health_status{plugin_name}` - 1 (healthy) or 0 (unhealthy)
- `plugin_collection_latency_ms{plugin_name}` - Collection time
- `plugin_failure_count{plugin_name}` - Cumulative failures

**Data Quality:**
- `weather_observations_collected_total` - Counter
- `weather_observations_missing_values` - Gauge
- `weather_api_http_status{status_code}` - Counter

**Performance:**
- `safety_index_calculation_time_ms` - Histogram
- `plugin_registry_collection_time_ms` - Histogram
- `database_write_latency_ms{table}` - Histogram

### Alerts

**Critical:**
- All plugins failing for >5 minutes
- Safety index calculation failing for >3 minutes
- Weather data missing for >2 hours

**Warning:**
- Single plugin failing for >15 minutes
- NOAA API rate limiting detected
- Weather feature values outside expected range

### Dashboards

**Plugin Overview:**
- Plugin health status grid
- Collection latency trends
- Feature contribution over time

**Weather Monitoring:**
- Current weather conditions
- API response time
- Data quality metrics (missing values, outliers)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-21
**Review Status:** Pending Technical Review
