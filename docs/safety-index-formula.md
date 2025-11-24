# Traffic Safety Index Formula Documentation

**Version**: 2.0
**Last Updated**: 2025-11-21
**Status**: Production

---

## Table of Contents

1. [Overview](#overview)
2. [Multi-Source Architecture](#multi-source-architecture)
3. [Overall Formula](#overall-formula)
4. [Traffic Index Components](#traffic-index-components)
5. [Weather Index Components](#weather-index-components)
6. [Feature Normalization](#feature-normalization)
7. [Risk Level Classification](#risk-level-classification)
8. [Example Calculation](#example-calculation)
9. [Configuration](#configuration)
10. [API Access](#api-access)

---

## Overview

The Traffic Safety Index is a **multi-source, weighted scoring system** that combines real-time traffic data from vehicle-to-everything (V2X) communications with environmental weather data to produce a comprehensive safety score for each intersection.

**Key Features:**
- **Multi-source integration**: Combines VCC traffic data (85%) and NOAA weather data (15%)
- **Transparent calculation**: All formulas and weights are visible via API
- **Risk-based scoring**: 0-100 scale where higher values indicate higher risk
- **Real-time updates**: Calculated every 15 minutes
- **Configurable weights**: Plugin weights can be adjusted based on validation

---

## Multi-Source Architecture

The safety index uses a **plugin-based architecture** where different data sources contribute weighted components to the final score.

```
Safety Index (0-100)
    ├── Traffic Index (Weight: 0.85)
    │   ├── VRU Index (Weight: 0.60)
    │   │   ├── Conflict Intensity (40%)
    │   │   ├── Vehicle Volume (20%)
    │   │   ├── Average Speed (20%)
    │   │   └── Speed Variance (20%)
    │   └── Vehicle Index (Weight: 0.40)
    │       ├── Vehicle Conflicts (30%)
    │       ├── Vehicle Volume (30%)
    │       ├── Speed Variance (20%)
    │       └── Hard Braking Events (20%)
    └── Weather Index (Weight: 0.15)
        ├── Precipitation (35%)
        ├── Visibility (30%)
        ├── Wind Speed (20%)
        └── Temperature (15%)
```

---

## Overall Formula

### Combined Safety Index

```
Safety_Index = (Traffic_Index × w_traffic) + (Weather_Index × w_weather)

Where:
  Traffic_Index = Composite score from VCC traffic data (0-100)
  Weather_Index = Composite score from NOAA weather data (0-100)
  w_traffic = 0.85 (default, configurable)
  w_weather = 0.15 (default, configurable)
```

**Example:**
```
Traffic_Index = 70.5
Weather_Index = 83.3
w_traffic = 0.85
w_weather = 0.15

Safety_Index = (70.5 × 0.85) + (83.3 × 0.15)
             = 59.925 + 12.495
             = 72.42
```

---

## Traffic Index Components

### Traffic Index Formula

The Traffic Index combines VRU (Vulnerable Road User) and Vehicle safety indices:

```
Traffic_Index = (0.60 × VRU_Index) + (0.40 × Vehicle_Index)
```

### VRU Safety Index

Focuses on pedestrian and cyclist safety:

```
VRU_Index = 100 × [0.4×(I_VRU/I_max) + 0.2×(V/V_max) + 0.2×(S/S_ref) + 0.2×(σ/σ_max)]

Where:
  I_VRU = VRU conflict intensity (events per 15-min interval)
  I_max = Maximum observed VRU conflict intensity (normalization constant)
  V = Vehicle volume (vehicle count per 15-min interval)
  V_max = Maximum observed vehicle volume
  S = Average vehicle speed (mph)
  S_ref = Reference speed (85th percentile of observed speeds)
  σ = Speed variance (mph²)
  σ_max = Maximum observed speed variance
```

**Feature Weights:**
- **Conflict Intensity (40%)**: Direct indicator of VRU safety risk
- **Vehicle Volume (20%)**: More vehicles = higher exposure
- **Average Speed (20%)**: Higher speeds = higher crash severity
- **Speed Variance (20%)**: Traffic instability indicator

### Vehicle Safety Index

Focuses on vehicle-to-vehicle conflicts and aggressive driving:

```
Vehicle_Index = 100 × [0.3×(I_vehicle/I_max) + 0.3×(V/V_max) + 0.2×(σ/σ_max) + 0.2×(HB/HB_max)]

Where:
  I_vehicle = Vehicle conflict count (events per 15-min)
  HB = Hard braking event count
  HB_max = Maximum observed hard braking count
  (Other variables same as VRU_Index)
```

**Feature Weights:**
- **Vehicle Conflicts (30%)**: Direct measure of crash risk
- **Vehicle Volume (30%)**: Exposure metric
- **Speed Variance (20%)**: Driving instability
- **Hard Braking (20%)**: Aggressive driving indicator

---

## Weather Index Components

### Weather Index Formula

Combines four normalized weather features:

```
Weather_Index = 100 × [0.35×precip + 0.30×vis + 0.20×wind + 0.15×temp]

Where:
  precip = Normalized precipitation (0-1)
  vis = Normalized visibility (0-1, inverted)
  wind = Normalized wind speed (0-1)
  temp = Normalized temperature deviation (0-1)
```

**Feature Weights:**
- **Precipitation (35%)**: Highest impact on crash risk
- **Visibility (30%)**: Critical for driver awareness
- **Wind Speed (20%)**: Affects vehicle control
- **Temperature (15%)**: Impacts road conditions

---

## Feature Normalization

All features are normalized to a **0-1 scale** where:
- **0 = Optimal/Safe conditions**
- **1 = Maximum risk/Dangerous conditions**

### Weather Feature Normalization

#### Precipitation
```
normalized_precip = min(precipitation_mm / 20.0, 1.0)

Examples:
  0 mm/hr   → 0.0 (no rain, safe)
  10 mm/hr  → 0.5 (moderate rain)
  20+ mm/hr → 1.0 (heavy rain, maximum risk)
```

#### Visibility (Inverted Scale)
```
normalized_vis = 1.0 - min(visibility_m / 10000.0, 1.0)

Examples:
  10,000+ m → 0.0 (clear, safe)
  5,000 m   → 0.5 (moderate visibility)
  0 m       → 1.0 (zero visibility, maximum risk)
```

#### Wind Speed
```
normalized_wind = min(wind_speed_ms / 25.0, 1.0)

Examples:
  0 m/s   → 0.0 (calm, safe)
  12.5 m/s → 0.5 (moderate wind)
  25+ m/s → 1.0 (high wind, maximum risk)
```

#### Temperature (U-Shaped Curve)
```
optimal_temp = 20°C
normalized_temp = min(|temperature_c - optimal_temp| / 20.0, 1.0)

Examples:
  20°C  → 0.0 (optimal temperature, safe)
  10°C  → 0.5 (10° deviation)
  30°C  → 0.5 (10° deviation)
  0°C   → 1.0 (20° deviation, icy conditions)
  40°C  → 1.0 (20° deviation, extreme heat)
```

### Traffic Feature Normalization

Traffic features are normalized using **dynamic normalization constants** computed from the dataset:

```
normalized_value = raw_value / max_value

Where max_value is computed from the current dataset:
  I_max: Maximum VRU conflict intensity observed
  V_max: Maximum vehicle volume observed
  σ_max: Maximum speed variance observed
  S_ref: 85th percentile of average speeds
  HB_max: Maximum hard braking count observed
```

This approach ensures normalization adapts to local traffic patterns.

---

## Risk Level Classification

Safety indices are classified into four risk levels for UI display:

| Risk Level | Range   | Color Code | Description |
|------------|---------|------------|-------------|
| **Low**    | 0-40    | `#10b981` (Green) | Safe conditions, minimal risk |
| **Medium** | 40-60   | `#3b82f6` (Blue) | Moderate risk, normal conditions |
| **High**   | 60-80   | `#f59e0b` (Amber) | Elevated risk, caution advised |
| **Critical** | 80-100 | `#ef4444` (Red) | Dangerous conditions, high crash risk |

**Thresholds chosen based on:**
- Historical crash data correlation
- Traffic engineering best practices
- Visual distinctiveness for quick assessment

---

## Example Calculation

### Scenario: Rainy Evening Rush Hour

**Raw Data:**
```
Time: 2025-11-21 17:30 (evening rush hour)
Intersection: Glebe & Potomac

Traffic Data:
  VRU conflicts: 5 events/15min
  Vehicle volume: 150 vehicles/15min
  Average speed: 35 mph
  Speed variance: 12 mph²
  Hard braking: 8 events/15min

Weather Data:
  Precipitation: 15.5 mm/hr (moderate rain)
  Visibility: 5,000 m (reduced)
  Wind speed: 8 m/s (light breeze)
  Temperature: 15°C (slightly cool)

Normalization Constants:
  I_max = 8.0 (from dataset)
  V_max = 200.0
  σ_max = 20.0
  S_ref = 40.0
  HB_max = 15.0
```

### Step 1: Normalize Features

**Weather Features:**
```
precip = 15.5 / 20.0 = 0.775
vis = 1.0 - (5000 / 10000) = 0.5
wind = 8 / 25.0 = 0.32
temp = |15 - 20| / 20.0 = 0.25
```

**Traffic Features:**
```
I_VRU_norm = 5.0 / 8.0 = 0.625
V_norm = 150 / 200 = 0.75
S_norm = 35 / 40 = 0.875
σ_norm = 12 / 20 = 0.6
HB_norm = 8 / 15 = 0.533
I_vehicle_norm = 3.0 / 8.0 = 0.375  (assuming 3 vehicle conflicts)
```

### Step 2: Calculate Component Indices

**VRU Index:**
```
VRU_Index = 100 × [0.4×0.625 + 0.2×0.75 + 0.2×0.875 + 0.2×0.6]
          = 100 × [0.25 + 0.15 + 0.175 + 0.12]
          = 100 × 0.695
          = 69.5
```

**Vehicle Index:**
```
Vehicle_Index = 100 × [0.3×0.375 + 0.3×0.75 + 0.2×0.6 + 0.2×0.533]
              = 100 × [0.1125 + 0.225 + 0.12 + 0.1066]
              = 100 × 0.5641
              = 56.4
```

**Weather Index:**
```
Weather_Index = 100 × [0.35×0.775 + 0.30×0.5 + 0.20×0.32 + 0.15×0.25]
              = 100 × [0.271 + 0.15 + 0.064 + 0.0375]
              = 100 × 0.5225
              = 52.3
```

### Step 3: Calculate Traffic Index

```
Traffic_Index = (0.60 × 69.5) + (0.40 × 56.4)
              = 41.7 + 22.56
              = 64.3
```

### Step 4: Calculate Final Safety Index

```
Safety_Index = (64.3 × 0.85) + (52.3 × 0.15)
             = 54.66 + 7.85
             = 62.5
```

### Step 5: Classify Risk Level

```
Safety_Index = 62.5
Risk Level = High (60-80 range)
Color = Amber (#f59e0b)
```

**Interpretation:**
- **High risk** due to combination of moderate rain (reduced traction) and rush hour traffic
- **VRU Index (69.5)** is elevated due to 5 VRU conflicts in 15 minutes
- **Weather Index (52.3)** is moderate due to rain and reduced visibility
- **Recommendation**: Drivers should reduce speed and increase following distance

---

## Configuration

### Plugin Weights

Plugin weights are configurable via environment variables:

```bash
# Traffic data weight (default: 0.70 for VCC plugin alone, 0.85 for combined traffic)
VCC_PLUGIN_WEIGHT=0.70

# Weather data weight (default: 0.15)
WEATHER_PLUGIN_WEIGHT=0.15

# Enable/disable plugins
USE_VCC_PLUGIN=true
ENABLE_WEATHER_PLUGIN=true
```

### Weight Validation

The system validates that enabled plugin weights sum to approximately 1.0 (with 1% tolerance):

```python
total_weight = VCC_PLUGIN_WEIGHT + WEATHER_PLUGIN_WEIGHT + OTHER_WEIGHTS
assert 0.99 <= total_weight <= 1.01, "Plugin weights must sum to 1.0"
```

### Tuning Recommendations

Based on crash data validation, recommended weight adjustments:

1. **Increase weather weight** if crash correlation shows strong weather impact
2. **Increase VRU weight** in pedestrian-heavy urban areas
3. **Increase vehicle weight** on high-speed corridors

See [Phase 7 Validation Results](../construction/validation/phase7-results.md) for data-driven weight recommendations.

---

## API Access

### Get Safety Index Breakdown

Retrieve detailed formula breakdown for any intersection:

```bash
GET /api/v1/safety/transparency/{intersection_id}/breakdown?timestamp=2025-11-21T17:30:00Z
```

**Response:**
```json
{
  "intersection_id": "glebe-potomac",
  "timestamp": "2025-11-21T17:30:00Z",
  "safety_index": 62.5,
  "vru_index": 69.5,
  "vehicle_index": 56.4,
  "weather_index": 52.3,
  "traffic_index": 64.3,
  "risk_level": {
    "level": "High",
    "color": "#f59e0b",
    "threshold_min": 60.0,
    "threshold_max": 80.0
  },
  "plugins": [
    {
      "plugin_name": "VCC Traffic",
      "plugin_weight": 0.85,
      "contribution": 54.66,
      "aggregated_score": 64.3,
      "features": {
        "vru_conflict_intensity": {
          "raw_value": 5.0,
          "normalized": 0.625,
          "description": "VRU conflict intensity (events per 15min)",
          "unit": "events"
        },
        ...
      }
    },
    {
      "plugin_name": "NOAA Weather",
      "plugin_weight": 0.15,
      "contribution": 7.85,
      "aggregated_score": 52.3,
      "features": {
        "weather_precipitation": {
          "raw_value": 15.5,
          "normalized": 0.775,
          "description": "Precipitation intensity",
          "unit": "mm/hr"
        },
        ...
      }
    }
  ],
  "formula": "62.5 = (64.3 × 0.85) + (52.3 × 0.15)",
  "formula_version": "2.0",
  "calculation_method": "multi_source_weighted"
}
```

### Get Formula Documentation

Retrieve complete formula documentation:

```bash
GET /api/v1/safety/transparency/formula/documentation
```

---

## References

- [Data Integration Roadmap](../memory-bank/data-integration-roadmap.md)
- [Plugin Architecture Documentation](../backend/app/plugins/README.md)
- [NOAA Weather Plugin](../backend/app/plugins/noaa_weather_plugin.py)
- [VCC Plugin](../backend/app/plugins/vcc_plugin.py)
- [Safety Index Computation](../backend/app/services/index_computation.py)
- [Transparency API](../backend/app/api/transparency.py)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-11-21 | Multi-source integration with weather data, plugin architecture |
| 1.0 | 2025-11-01 | Initial VCC-only safety index |

---

**Questions or feedback?** Contact the development team or file an issue on GitHub.
