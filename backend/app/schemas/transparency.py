"""
Pydantic schemas for safety index transparency and formula breakdown.

Used in Phase 6: UI Transparency to expose how safety indices are calculated.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Optional, List


class FeatureBreakdown(BaseModel):
    """Breakdown of a single feature's contribution"""
    raw_value: float = Field(..., description="Original raw value")
    normalized: float = Field(..., ge=0.0, le=1.0, description="Normalized value (0-1 scale)")
    description: str = Field(..., description="Human-readable feature description")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'mm/hr', 'km', '°C')")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "raw_value": 15.5,
                "normalized": 0.775,
                "description": "Precipitation intensity",
                "unit": "mm/hr"
            }]
        }
    }


class PluginBreakdown(BaseModel):
    """Breakdown of a data source plugin's contribution to safety index"""
    plugin_name: str = Field(..., description="Name of the plugin (e.g., 'VCC Traffic', 'NOAA Weather')")
    plugin_weight: float = Field(..., ge=0.0, le=1.0, description="Plugin's weight in formula (0-1)")
    contribution: float = Field(..., ge=0.0, le=100.0, description="Plugin's contribution to safety index (0-100)")
    aggregated_score: float = Field(..., ge=0.0, le=100.0, description="Plugin's internal score before weighting")
    features: Dict[str, FeatureBreakdown] = Field(..., description="Individual feature breakdowns")
    enabled: bool = Field(True, description="Whether plugin is currently enabled")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "plugin_name": "NOAA Weather",
                "plugin_weight": 0.15,
                "contribution": 12.5,
                "aggregated_score": 83.3,
                "enabled": True,
                "features": {
                    "weather_precipitation": {
                        "raw_value": 15.5,
                        "normalized": 0.775,
                        "description": "Precipitation intensity",
                        "unit": "mm/hr"
                    },
                    "weather_visibility": {
                        "raw_value": 5000,
                        "normalized": 0.5,
                        "description": "Visibility distance",
                        "unit": "m"
                    }
                }
            }]
        }
    }


class RiskLevel(BaseModel):
    """Risk level classification for safety index"""
    level: str = Field(..., description="Risk level name (Low, Medium, High, Critical)")
    color: str = Field(..., description="Color code for UI display")
    threshold_min: float = Field(..., ge=0.0, le=100.0)
    threshold_max: float = Field(..., ge=0.0, le=100.0)

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "level": "High",
                "color": "#f59e0b",
                "threshold_min": 60.0,
                "threshold_max": 80.0
            }]
        }
    }


class FormulaComponent(BaseModel):
    """Mathematical component of the safety index formula"""
    component_type: str = Field(..., description="Type: 'weighted_sum', 'normalized', 'raw'")
    expression: str = Field(..., description="Mathematical expression")
    result: float = Field(..., description="Computed result")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "component_type": "weighted_sum",
                "expression": "(70.5 × 0.85) + (83.3 × 0.15)",
                "result": 72.4
            }]
        }
    }


class SafetyIndexBreakdown(BaseModel):
    """
    Complete breakdown of safety index calculation.

    Shows raw features, normalized values, plugin weights, and final formula.
    """
    intersection_id: str = Field(..., description="Intersection identifier")
    intersection_name: Optional[str] = Field(None, description="Human-readable intersection name")
    timestamp: datetime = Field(..., description="Timestamp of this safety index calculation")

    # Overall scores
    safety_index: float = Field(..., ge=0.0, le=100.0, description="Final combined safety index")
    vru_index: Optional[float] = Field(None, ge=0.0, le=100.0, description="VRU safety index component")
    vehicle_index: Optional[float] = Field(None, ge=0.0, le=100.0, description="Vehicle safety index component")
    weather_index: Optional[float] = Field(None, ge=0.0, le=100.0, description="Weather safety index component")
    traffic_index: Optional[float] = Field(None, ge=0.0, le=100.0, description="Combined traffic index (VRU + Vehicle)")

    # Risk classification
    risk_level: RiskLevel = Field(..., description="Risk level classification")

    # Plugin breakdowns
    plugins: List[PluginBreakdown] = Field(..., description="Breakdown by data source plugin")

    # Formula representation
    formula: str = Field(..., description="Human-readable formula representation")
    formula_components: List[FormulaComponent] = Field(..., description="Breakdown of formula calculation")
    formula_version: str = Field("2.0", description="Formula version identifier")

    # Metadata
    calculation_method: str = Field(..., description="Calculation method used (e.g., 'multi_source_weighted')")
    data_quality: Optional[str] = Field(None, description="Data quality indicator (e.g., 'complete', 'partial', 'estimated')")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "intersection_id": "0.0",
                "intersection_name": "Intersection 0.0",
                "timestamp": "2025-11-21T14:30:00Z",
                "safety_index": 72.4,
                "vru_index": 68.5,
                "vehicle_index": 72.0,
                "weather_index": 83.3,
                "traffic_index": 70.5,
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
                        "contribution": 59.9,
                        "aggregated_score": 70.5,
                        "enabled": True,
                        "features": {}
                    },
                    {
                        "plugin_name": "NOAA Weather",
                        "plugin_weight": 0.15,
                        "contribution": 12.5,
                        "aggregated_score": 83.3,
                        "enabled": True,
                        "features": {}
                    }
                ],
                "formula": "72.4 = (70.5 × 0.85) + (83.3 × 0.15)",
                "formula_components": [
                    {
                        "component_type": "weighted_sum",
                        "expression": "(70.5 × 0.85) + (83.3 × 0.15)",
                        "result": 72.4
                    }
                ],
                "formula_version": "2.0",
                "calculation_method": "multi_source_weighted",
                "data_quality": "complete"
            }]
        }
    }
