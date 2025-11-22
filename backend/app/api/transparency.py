"""
Safety Index Transparency API

Provides detailed breakdown of safety index calculations for UI display.
Shows how features, weights, and formulas combine to produce the final safety index.

Phase 6: UI Transparency
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
import logging
import pandas as pd

from app.schemas.transparency import (
    SafetyIndexBreakdown,
    PluginBreakdown,
    FeatureBreakdown,
    RiskLevel,
    FormulaComponent
)
from app.services.multi_source_collector import multi_source_collector
from app.services.index_computation import compute_multi_source_safety_indices
from app.core.config import settings

router = APIRouter(prefix="/safety/transparency", tags=["Safety Index Transparency"])
logger = logging.getLogger(__name__)


def compute_risk_level(safety_index: float) -> RiskLevel:
    """
    Classify safety index into risk levels.

    Thresholds:
    - Low: 0-40
    - Medium: 40-60
    - High: 60-80
    - Critical: 80-100
    """
    if safety_index < 40:
        return RiskLevel(
            level="Low",
            color="#10b981",  # Green
            threshold_min=0.0,
            threshold_max=40.0
        )
    elif safety_index < 60:
        return RiskLevel(
            level="Medium",
            color="#3b82f6",  # Blue
            threshold_min=40.0,
            threshold_max=60.0
        )
    elif safety_index < 80:
        return RiskLevel(
            level="High",
            color="#f59e0b",  # Amber/Orange
            threshold_min=60.0,
            threshold_max=80.0
        )
    else:
        return RiskLevel(
            level="Critical",
            color="#ef4444",  # Red
            threshold_min=80.0,
            threshold_max=100.0
        )


def extract_plugin_breakdowns(
    indices_row: pd.Series,
    plugin_weights: dict
) -> list[PluginBreakdown]:
    """
    Extract plugin-level breakdowns from indices dataframe row.

    Args:
        indices_row: Single row from indices dataframe with all index columns
        plugin_weights: Dictionary of plugin weights

    Returns:
        List of PluginBreakdown objects
    """
    plugins = []

    # Weather plugin breakdown
    if 'Weather_Index' in indices_row.index and indices_row.get('Weather_Index') is not None:
        weather_weight = plugin_weights.get('weather', 0.15)
        weather_score = float(indices_row['Weather_Index'])

        # Extract weather features
        weather_features = {}
        weather_feature_names = {
            'weather_precipitation': ('Precipitation intensity', 'mm/hr'),
            'weather_visibility': ('Visibility distance', 'm'),
            'weather_wind_speed': ('Wind speed', 'm/s'),
            'weather_temperature': ('Temperature deviation from optimal', '°C')
        }

        for feat_name, (description, unit) in weather_feature_names.items():
            if feat_name in indices_row.index:
                raw_val = indices_row.get(feat_name, 0.0)
                weather_features[feat_name] = FeatureBreakdown(
                    raw_value=float(raw_val) if pd.notna(raw_val) else 0.0,
                    normalized=float(raw_val) if pd.notna(raw_val) else 0.0,  # Already normalized by plugin
                    description=description,
                    unit=unit
                )

        plugins.append(PluginBreakdown(
            plugin_name="NOAA Weather",
            plugin_weight=weather_weight,
            contribution=weather_score * weather_weight,
            aggregated_score=weather_score,
            features=weather_features,
            enabled=settings.ENABLE_WEATHER_PLUGIN
        ))

    # Traffic plugin breakdown (VCC)
    if 'Traffic_Index' in indices_row.index and indices_row.get('Traffic_Index') is not None:
        traffic_weight = plugin_weights.get('traffic', 0.85)
        traffic_score = float(indices_row['Traffic_Index'])

        # Extract traffic sub-components
        traffic_features = {}

        # VRU features
        if 'I_VRU' in indices_row.index:
            traffic_features['vru_conflict_intensity'] = FeatureBreakdown(
                raw_value=float(indices_row.get('I_VRU', 0.0)),
                normalized=float(indices_row.get('I_VRU_norm', 0.0)) if 'I_VRU_norm' in indices_row.index else 0.0,
                description="VRU conflict intensity (events per 15min)",
                unit="events"
            )

        # Vehicle features
        if 'vehicle_count' in indices_row.index:
            traffic_features['vehicle_volume'] = FeatureBreakdown(
                raw_value=float(indices_row.get('vehicle_count', 0.0)),
                normalized=float(indices_row.get('V_norm', 0.0)) if 'V_norm' in indices_row.index else 0.0,
                description="Vehicle volume",
                unit="vehicles"
            )

        if 'avg_speed' in indices_row.index:
            traffic_features['average_speed'] = FeatureBreakdown(
                raw_value=float(indices_row.get('avg_speed', 0.0)),
                normalized=float(indices_row.get('S_norm', 0.0)) if 'S_norm' in indices_row.index else 0.0,
                description="Average vehicle speed",
                unit="mph"
            )

        if 'speed_variance' in indices_row.index:
            traffic_features['speed_variance'] = FeatureBreakdown(
                raw_value=float(indices_row.get('speed_variance', 0.0)),
                normalized=float(indices_row.get('sigma_norm', 0.0)) if 'sigma_norm' in indices_row.index else 0.0,
                description="Speed variance",
                unit="mph²"
            )

        plugins.append(PluginBreakdown(
            plugin_name="VCC Traffic",
            plugin_weight=traffic_weight,
            contribution=traffic_score * traffic_weight,
            aggregated_score=traffic_score,
            features=traffic_features,
            enabled=settings.USE_VCC_PLUGIN
        ))

    return plugins


@router.get("/{intersection_id}/breakdown", response_model=SafetyIndexBreakdown)
async def get_safety_index_breakdown(
    intersection_id: str,
    timestamp: Optional[datetime] = Query(
        None,
        description="Timestamp for safety index (ISO 8601). If not provided, uses latest available."
    )
) -> SafetyIndexBreakdown:
    """
    Get detailed breakdown of safety index calculation for a specific intersection.

    **Returns:**
    - Overall safety index score and risk level
    - Contribution from each data source plugin (VCC, Weather, etc.)
    - Raw feature values and normalized values
    - Feature weights and calculation formula
    - Human-readable formula breakdown

    **Example:**
    ```
    GET /api/v1/safety/transparency/0.0/breakdown?timestamp=2025-11-21T14:30:00Z
    ```

    **Response shows:**
    1. How VCC traffic features combine into Traffic Index
    2. How NOAA weather features combine into Weather Index
    3. How Traffic and Weather indices are weighted to produce final Safety Index
    4. Risk level classification (Low/Medium/High/Critical)
    """
    try:
        # Use latest timestamp if not provided
        if timestamp is None:
            timestamp = datetime.now()

        # Calculate safety indices for a 15-minute window around the timestamp
        start_time = timestamp - timedelta(minutes=7)
        end_time = timestamp + timedelta(minutes=8)

        logger.info(f"Computing safety index breakdown for {intersection_id} at {timestamp}")

        # Collect data and compute indices
        indices_df = compute_multi_source_safety_indices(
            start_time=start_time,
            end_time=end_time,
            baseline_events=None,
            apply_eb=False
        )

        if indices_df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for intersection '{intersection_id}' at {timestamp}"
            )

        # Get the row closest to the requested timestamp
        # TODO: Filter by intersection_id once MultiSourceDataCollector supports it
        # For now, we'll use the first row
        row = indices_df.iloc[0]

        # Extract indices
        safety_index = float(row.get('Combined_Index', 0.0))
        vru_index = float(row.get('VRU_Index')) if 'VRU_Index' in row.index else None
        vehicle_index = float(row.get('Vehicle_Index')) if 'Vehicle_Index' in row.index else None
        weather_index = float(row.get('Weather_Index')) if 'Weather_Index' in row.index else None
        traffic_index = float(row.get('Traffic_Index')) if 'Traffic_Index' in row.index else None

        # Get plugin weights
        weather_weight = settings.WEATHER_PLUGIN_WEIGHT
        traffic_weight = 1.0 - weather_weight

        # Extract plugin breakdowns
        plugins = extract_plugin_breakdowns(row, {
            'weather': weather_weight,
            'traffic': traffic_weight
        })

        # Build formula string
        if traffic_index is not None and weather_index is not None:
            formula = f"{safety_index:.1f} = ({traffic_index:.1f} × {traffic_weight:.2f}) + ({weather_index:.1f} × {weather_weight:.2f})"
        else:
            formula = f"{safety_index:.1f} = Combined Safety Index"

        # Build formula components
        formula_components = []
        if traffic_index is not None and weather_index is not None:
            formula_components.append(FormulaComponent(
                component_type="weighted_sum",
                expression=f"({traffic_index:.1f} × {traffic_weight:.2f}) + ({weather_index:.1f} × {weather_weight:.2f})",
                result=safety_index
            ))

            if vru_index is not None and vehicle_index is not None:
                formula_components.append(FormulaComponent(
                    component_type="traffic_composite",
                    expression=f"Traffic = (0.60 × VRU_Index) + (0.40 × Vehicle_Index) = (0.60 × {vru_index:.1f}) + (0.40 × {vehicle_index:.1f})",
                    result=traffic_index
                ))

        # Build response
        breakdown = SafetyIndexBreakdown(
            intersection_id=intersection_id,
            intersection_name=f"Intersection {intersection_id}",
            timestamp=row.get('timestamp', timestamp),
            safety_index=safety_index,
            vru_index=vru_index,
            vehicle_index=vehicle_index,
            weather_index=weather_index,
            traffic_index=traffic_index,
            risk_level=compute_risk_level(safety_index),
            plugins=plugins,
            formula=formula,
            formula_components=formula_components,
            formula_version="2.0",
            calculation_method="multi_source_weighted",
            data_quality="complete" if len(plugins) > 0 else "partial"
        )

        return breakdown

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing safety index breakdown: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error computing safety index breakdown: {str(e)}"
        )


@router.get("/formula/documentation")
async def get_formula_documentation():
    """
    Get documentation for the safety index formula.

    Returns detailed explanation of:
    - How each feature is normalized (0-1 scale)
    - How features are weighted within each plugin
    - How plugin scores are combined
    - Risk level thresholds
    """
    return {
        "formula_version": "2.0",
        "description": "Multi-source weighted safety index combining traffic and weather data",

        "overall_formula": {
            "expression": "Safety_Index = (Traffic_Index × w_traffic) + (Weather_Index × w_weather)",
            "default_weights": {
                "w_traffic": 0.85,
                "w_weather": 0.15
            },
            "note": "Weights are configurable via plugin settings"
        },

        "traffic_index": {
            "expression": "Traffic_Index = (0.60 × VRU_Index) + (0.40 × Vehicle_Index)",
            "vru_formula": "VRU_Index = 100 × [0.4×(I_VRU/I_max) + 0.2×(V/V_max) + 0.2×(S/S_ref) + 0.2×(σ/σ_max)]",
            "vehicle_formula": "Vehicle_Index = 100 × [0.3×(I_vehicle/I_max) + 0.3×(V/V_max) + 0.2×(σ/σ_max) + 0.2×(hard_braking)]"
        },

        "weather_index": {
            "expression": "Weather_Index = 100 × [0.35×precip + 0.30×visibility + 0.20×wind + 0.15×temp]",
            "feature_normalization": {
                "precipitation": "0=no rain, 1=heavy rain (≥20mm/hr)",
                "visibility": "0=clear (10km+), 1=zero visibility (inverted scale)",
                "wind_speed": "0=calm, 1=high wind (≥25 m/s)",
                "temperature": "0=optimal (20°C), 1=extreme hot/cold (U-shaped curve)"
            }
        },

        "risk_levels": {
            "Low": {"range": "0-40", "color": "#10b981"},
            "Medium": {"range": "40-60", "color": "#3b82f6"},
            "High": {"range": "60-80", "color": "#f59e0b"},
            "Critical": {"range": "80-100", "color": "#ef4444"}
        },

        "data_sources": [
            {
                "name": "VCC Traffic",
                "description": "Vehicle-to-everything communication data providing real-time traffic metrics",
                "features": ["conflict_count", "ttc_min", "proximity_score", "speed_variance", "acceleration_events"]
            },
            {
                "name": "NOAA Weather",
                "description": "National Weather Service observations from local weather stations",
                "features": ["precipitation", "visibility", "wind_speed", "temperature"]
            }
        ]
    }
