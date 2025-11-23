# Requirements: Data Integration & Extensibility

**Feature:** Pluggable Data Source Architecture with Weather Integration
**Priority:** High
**Status:** Planning
**Target Release:** Sprint 2025-Q1

---

## Executive Summary

Enable the Traffic Safety Index system to integrate multiple data sources through a plugin architecture, starting with NOAA/NWS weather data. This allows domain experts to adjust safety index weights without code changes and provides transparency into how safety scores are calculated.

**Key Capabilities:**
- Add new data sources without modifying core application code
- Adjust feature weights through configuration/UI
- Collect weather data for current and historical time periods
- Display safety index formula transparency in dashboard
- Correlate safety predictions with crash data for validation

---

## Business Requirements

### BR-1: Extensibility
**Requirement:** The system shall support adding new data sources without requiring changes to core application code.

**Rationale:** Research teams need to experiment with different data sources (weather, crash data, traffic cameras, social media) without waiting for developers.

**Acceptance Criteria:**
- Adding a new data source requires only implementing a plugin interface
- Plugin can be enabled/disabled through configuration
- System continues operating if a plugin fails

**Priority:** P0 (Must Have)

---

### BR-2: Weather Data Integration
**Requirement:** The system shall collect and integrate weather data from NOAA/NWS API.

**Rationale:** Weather conditions (rain, snow, fog, wind) significantly impact traffic safety and should influence safety index calculations.

**Acceptance Criteria:**
- Weather data collected hourly for all monitored intersections
- Historical weather data backfilled for all existing traffic data periods
- Weather factors integrated into safety index calculation
- Weather data stored in all three backends (Parquet + PostgreSQL + GCS)

**Data Points Required:**
- Temperature (°C)
- Precipitation amount (mm/hour)
- Visibility distance (meters)
- Wind speed (m/s)
- Weather conditions (clear, rain, snow, fog)

**Priority:** P0 (Must Have)

---

### BR-3: Configurable Feature Weights
**Requirement:** Domain experts shall be able to adjust safety index feature weights without developer assistance.

**Rationale:** Safety index formula requires tuning based on validation against crash data. Current hard-coded weights prevent experimentation.

**Acceptance Criteria:**
- Feature weights configurable through environment variables (Phase 1)
- Feature weights adjustable through admin UI (Phase 2)
- Weight changes immediately affect safety index calculations
- Weight change history tracked for auditing
- Weights sum to 1.0 (validated)

**Initial Weights:**
- VCC Traffic Data: 70%
- Weather Data: 15%
- Reserved for future sources: 15%

**Priority:** P0 (Must Have)

---

### BR-4: Safety Index Transparency
**Requirement:** The dashboard shall display how safety index scores are calculated, showing each feature and its weight.

**Rationale:** Users need to understand what factors contribute to safety scores to trust the system and make informed decisions.

**Acceptance Criteria:**
- Dashboard displays safety index formula breakdown
- Each feature shown with its current weight
- Users can see raw feature values contributing to a specific score
- UI updates when weights are changed

**Priority:** P1 (Should Have)

---

### BR-5: Crash Data Correlation
**Requirement:** The system shall provide tools to correlate safety index predictions with historical crash data.

**Rationale:** Validate that weather integration improves predictive accuracy and optimize feature weights based on actual crash outcomes.

**Acceptance Criteria:**
- Import historical crash records
- Compare safety index scores during crash events vs normal periods
- Generate correlation reports showing predictive accuracy
- Identify optimal feature weights through statistical analysis

**Priority:** P1 (Should Have)

---

## Functional Requirements

### FR-1: Plugin Architecture

#### FR-1.1: Abstract Plugin Interface
**Requirement:** Define a standard interface that all data source plugins must implement.

**Interface Methods:**
- `collect(start_time, end_time) -> DataFrame` - Collect data for time range
- `get_features() -> List[str]` - Return feature names this plugin provides
- `health_check() -> bool` - Verify plugin can connect to data source
- `get_metadata() -> Dict` - Return plugin configuration and status

**Priority:** P0

---

#### FR-1.2: Plugin Registry
**Requirement:** Provide a centralized registry for managing data source plugins.

**Capabilities:**
- Register plugins by name
- Enable/disable plugins through configuration
- Collect data from all enabled plugins in parallel
- Aggregate features from multiple plugins
- Handle individual plugin failures gracefully

**Priority:** P0

---

#### FR-1.3: Plugin Configuration
**Requirement:** Support plugin configuration through environment variables and/or database.

**Configuration Format:**
```yaml
plugins:
  vcc:
    enabled: true
    class: VCCPlugin
    weight: 0.70
    config:
      base_url: ${VCC_BASE_URL}
      client_id: ${VCC_CLIENT_ID}
      client_secret: ${VCC_CLIENT_SECRET}

  noaa_weather:
    enabled: true
    class: NOAAWeatherPlugin
    weight: 0.15
    config:
      station_id: KRIC
      api_base: https://api.weather.gov
```

**Priority:** P0

---

### FR-2: VCC Plugin Refactoring

#### FR-2.1: VCC as Plugin
**Requirement:** Refactor existing VCC client as a plugin implementation.

**Acceptance Criteria:**
- VCCPlugin implements DataSourcePlugin interface
- Maintains 100% backward compatibility with current VCC integration
- No data loss during migration
- Feature flag controls plugin vs legacy code path

**Priority:** P0

---

#### FR-2.2: Migration Path
**Requirement:** Provide safe migration from hard-coded VCC client to plugin architecture.

**Migration Strategy:**
1. Plugin architecture deployed with feature flag disabled
2. VCC plugin implemented alongside existing code
3. Compare outputs from plugin vs legacy code (validation)
4. Enable plugin for 10% of traffic (canary deployment)
5. Gradually increase to 100%
6. Remove legacy code after 2 weeks of stable plugin operation

**Priority:** P0

---

### FR-3: NOAA Weather Plugin

#### FR-3.1: Current Weather Collection
**Requirement:** Collect weather observations from NOAA/NWS API every hour.

**API Details:**
- Endpoint: `https://api.weather.gov/stations/{station_id}/observations`
- Authentication: None required (User-Agent header only)
- Rate Limit: Unknown, implement exponential backoff
- Data Format: JSON with GeoJSON structure

**Acceptance Criteria:**
- Weather data collected every 60 minutes (aligned with VCC collection)
- Data written to Parquet, PostgreSQL, and GCS
- Failures logged but don't crash data collector
- Health check verifies station is accessible

**Priority:** P0

---

#### FR-3.2: Historical Weather Backfill
**Requirement:** Retrieve historical weather observations for all dates where traffic data exists.

**Acceptance Criteria:**
- Backfill script identifies date ranges with traffic data but missing weather
- Batch processing with configurable rate limiting
- Resume capability if interrupted
- Progress tracking and status reporting
- Data validation (check for missing values, outliers)

**Estimated Volume:**
- Assume 6 months of historical traffic data
- 24 observations per day × 180 days = 4,320 API calls
- At 1 request/second, ~72 minutes to backfill

**Priority:** P0

---

#### FR-3.3: Weather Feature Engineering
**Requirement:** Transform raw weather observations into features for safety index calculation.

**Features:**
- `weather_precipitation` - Precipitation amount normalized 0-1
- `weather_visibility` - Visibility distance normalized 0-1 (inverted: lower visibility = higher risk)
- `weather_wind_speed` - Wind speed normalized 0-1
- `weather_temperature` - Temperature normalized 0-1 (extreme temps = higher risk)
- `weather_condition_severity` - Categorical: clear (0.0), rain (0.3), snow (0.7), fog (0.5)

**Normalization:**
- Use historical percentiles (P5, P95) for normalization
- Store normalization constants in database
- Update constants monthly as more data accumulates

**Priority:** P0

---

### FR-4: Safety Index Integration

#### FR-4.1: Multi-Source Index Calculation
**Requirement:** Extend safety index computation to incorporate features from multiple data sources with configurable weights.

**Formula:**
```
safety_index = Σ(weight_i × feature_score_i) for all enabled plugins
```

**Constraints:**
- Σ(weight_i) = 1.0 (enforced)
- 0.0 ≤ weight_i ≤ 1.0
- Missing features handled gracefully (use default value or omit)

**Acceptance Criteria:**
- Safety index changes when weather conditions change
- Weight adjustments immediately affect scores
- Formula transparency: can trace score back to raw inputs

**Priority:** P0

---

#### FR-4.2: Backward Compatibility
**Requirement:** Provide ability to calculate safety index using old formula for comparison.

**Acceptance Criteria:**
- Legacy formula available through API parameter: `?formula=legacy`
- Both formulas calculated and stored during transition period
- Dashboard can display old vs new scores side-by-side

**Priority:** P1

---

### FR-5: Dashboard Transparency

#### FR-5.1: Formula Breakdown Display
**Requirement:** Show users how a specific safety index score was calculated.

**UI Components:**
- Table showing each feature, its raw value, normalized value, weight, and contribution
- Visual breakdown (pie chart or stacked bar)
- Timestamp of data used for calculation
- Plugin status indicators (active, failed, disabled)

**Example:**
```
Safety Index: 0.67 (Moderate Risk)

Feature Breakdown:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature                  Raw      Norm   Weight  Score
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VCC Conflict Count       12       0.72   70%     0.504
VCC Min TTC              1.8s     0.65
VCC Proximity Score      0.58     0.58
Weather Precipitation    5.2mm    0.85   15%     0.128
Weather Visibility       200m     0.95
Weather Wind Speed       8 m/s    0.42
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Safety Index:                              0.67
```

**Priority:** P1

---

#### FR-5.2: Weight Adjustment Interface (Admin Only)
**Requirement:** Provide UI for administrators to adjust feature weights.

**Capabilities:**
- Sliders or input fields for each feature weight
- Real-time validation (weights sum to 1.0)
- Preview impact on recent safety scores before saving
- Confirmation prompt before applying changes
- Audit log of all weight changes

**Security:**
- Require admin authentication
- Log user who made changes and timestamp
- Ability to revert to previous weights

**Priority:** P2 (Could Have)

---

### FR-6: Validation & Testing

#### FR-6.1: Crash Data Correlation
**Requirement:** Analyze correlation between safety index scores and historical crash events.

**Analysis Metrics:**
- True Positive Rate: Crashes that occurred during high safety index periods
- False Positive Rate: High safety index periods without crashes
- Receiver Operating Characteristic (ROC) curve
- Area Under Curve (AUC) for old vs new formula

**Deliverables:**
- Correlation report showing statistical significance
- Recommended feature weights based on crash data
- Confidence intervals for predictions

**Priority:** P1

---

#### FR-6.2: Performance Benchmarking
**Requirement:** Measure performance impact of plugin architecture and weather integration.

**Metrics:**
- Data collection latency (target: <5% increase)
- Safety index calculation time (target: <10% increase)
- API response time (target: <100ms increase)
- Database query performance
- Storage overhead (target: <20% increase)

**Acceptance Criteria:**
- Automated benchmark suite
- Performance regression alerts
- Optimization plan if targets exceeded

**Priority:** P1

---

## Non-Functional Requirements

### NFR-1: Reliability
- Weather plugin failures shall not crash data collector
- System shall operate with degraded functionality if weather data unavailable
- Triple-write (Parquet + PostgreSQL + GCS) shall be maintained for weather data
- Uptime target: 99.9% for data collection

**Priority:** P0

---

### NFR-2: Performance
- Weather data collection shall not add more than 5% overhead to collection cycle
- Safety index calculation shall complete within 100ms (95th percentile)
- Historical backfill shall not impact live data collection performance
- Plugin initialization shall not delay startup by more than 2 seconds

**Priority:** P0

---

### NFR-3: Security
- NOAA API responses shall be validated and sanitized
- Weather data shall be validated for SQL injection, XSS before storage
- Admin weight adjustment interface requires authentication
- Plugin configurations shall not expose credentials in logs

**Priority:** P0

---

### NFR-4: Maintainability
- Plugin documentation shall include step-by-step guide for adding new data sources
- Code coverage shall be ≥80% for plugin framework
- Each plugin shall have integration tests
- API changes to plugin interface shall be versioned

**Priority:** P1

---

### NFR-5: Scalability
- Plugin architecture shall support at least 10 concurrent data sources
- Weather data collection shall scale to 100+ monitoring stations
- Historical backfill shall support parallel processing
- Database schema shall accommodate additional feature columns without migration

**Priority:** P1

---

## Data Requirements

### DR-1: Weather Data Schema

**Table: `weather_observations`**
```sql
CREATE TABLE weather_observations (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(10) NOT NULL,
    observation_time TIMESTAMPTZ NOT NULL,
    temperature_c FLOAT,
    precipitation_mm FLOAT,
    visibility_m FLOAT,
    wind_speed_ms FLOAT,
    wind_direction_deg INT,
    weather_condition VARCHAR(50),
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(station_id, observation_time)
);

CREATE INDEX idx_weather_obs_time ON weather_observations(observation_time);
CREATE INDEX idx_weather_obs_station ON weather_observations(station_id);
```

**Partitioning:** Monthly partitions (same as safety_indices_realtime)

**Retention:**
- Raw observations: 2 years (then archive to GCS Coldline)
- Aggregated features: Indefinite

**Priority:** P0

---

### DR-2: Plugin Configuration Schema

**Table: `data_source_plugins`**
```sql
CREATE TABLE data_source_plugins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    weight FLOAT DEFAULT 0.0 CHECK (weight >= 0.0 AND weight <= 1.0),
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Priority:** P1 (Can use environment variables in Phase 1)

---

### DR-3: Feature Weight History

**Table: `feature_weight_history`**
```sql
CREATE TABLE feature_weight_history (
    id BIGSERIAL PRIMARY KEY,
    plugin_name VARCHAR(50) NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    old_weight FLOAT,
    new_weight FLOAT NOT NULL,
    changed_by VARCHAR(100),
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT
);
```

**Purpose:** Audit trail for weight adjustments

**Priority:** P2

---

## Dependencies

### Internal Dependencies
1. **PostgreSQL Migration Sprint** - Must be at Phase 4 (triple-write stable)
2. **Frontend Dashboard** - Must support new transparency components
3. **Database Schema** - Must support weather table and partitioning

### External Dependencies
1. **NOAA/NWS API** - Free, public access (no API key)
2. **Historical Crash Data** - Requires access to crash records database

---

## Out of Scope

The following are explicitly **not** included in this feature:

1. **Real-time Weather Forecasts** - Only historical/current observations
2. **Multiple Weather Stations** - Phase 1 uses single station (KRIC)
3. **Machine Learning Models** - Weight optimization uses statistical correlation, not ML
4. **Mobile App Integration** - Dashboard changes only
5. **Alerting Based on Weather** - Only data collection and index calculation
6. **Weather Radar Imagery** - Text data only, no images
7. **International Weather Sources** - NOAA/NWS is US-only

---

## Success Metrics

### Phase 1 Success Criteria (Weeks 1-3)
- ✅ Plugin architecture implemented and tested
- ✅ VCC refactored as plugin with zero data loss
- ✅ NOAA weather plugin collecting current data
- ✅ Weather data in all three storage backends
- ✅ <5% performance overhead

### Phase 2 Success Criteria (Weeks 4-6)
- ✅ Historical weather backfill complete for all traffic data periods
- ✅ Safety index integrates weather with 15% weight
- ✅ Dashboard displays formula transparency
- ✅ Crash correlation analysis shows improvement (AUC increase ≥5%)

### Long-term Success (3 months post-deployment)
- ✅ 3+ additional data sources integrated as plugins
- ✅ Safety index predictive accuracy improved by ≥10%
- ✅ Domain experts can add new data sources without developer support
- ✅ Zero production incidents caused by plugin failures

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| NOAA API rate limiting during backfill | High | Medium | Implement exponential backoff, batch processing |
| Weather data doesn't improve predictions | High | Medium | Run correlation analysis early, have exit criteria |
| Performance degradation | Medium | Low | Benchmark continuously, optimize queries |
| Plugin complexity too high for maintainers | Medium | Medium | Comprehensive documentation, training |
| PostgreSQL migration delays weather work | High | Low | Weather can use Parquet-only initially |
| Scope creep (too many data sources) | Medium | High | Strict Phase 1 scope: VCC + Weather only |

---

## Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | | | |
| Technical Lead | | | |
| QA Lead | | | |

---

**Document Version:** 1.0
**Last Updated:** 2025-11-21
**Next Review:** Before sprint kickoff
