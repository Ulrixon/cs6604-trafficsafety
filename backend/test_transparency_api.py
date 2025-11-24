"""
Test script for Safety Index Transparency API (Phase 6).

Tests the formula breakdown endpoints to ensure they return correct data structure.

Usage:
    python test_transparency_api.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.api.transparency import (
    compute_risk_level,
    extract_plugin_breakdowns,
    get_formula_documentation
)
from app.schemas.transparency import RiskLevel
import pandas as pd


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_risk_level_classification():
    """Test 1: Risk level classification."""
    print_section("TEST 1: Risk Level Classification")

    test_cases = [
        (20.0, "Low"),
        (50.0, "Medium"),
        (70.0, "High"),
        (90.0, "Critical")
    ]

    passed = 0
    for safety_index, expected_level in test_cases:
        risk = compute_risk_level(safety_index)
        status = "PASS" if risk.level == expected_level else "FAIL"
        print(f"{status}: Index={safety_index} -> {risk.level} (color: {risk.color})")
        if risk.level == expected_level:
            passed += 1

    print(f"\n{passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)


def test_plugin_breakdown_extraction():
    """Test 2: Plugin breakdown extraction from indices dataframe."""
    print_section("TEST 2: Plugin Breakdown Extraction")

    # Create mock indices row
    mock_data = {
        'timestamp': datetime(2025, 11, 21, 14, 30),
        'Combined_Index': 72.4,
        'VRU_Index': 68.5,
        'Vehicle_Index': 72.0,
        'Weather_Index': 83.3,
        'Traffic_Index': 70.5,
        'I_VRU': 5.0,
        'I_VRU_norm': 0.625,
        'vehicle_count': 150,
        'V_norm': 0.75,
        'avg_speed': 35.0,
        'S_norm': 0.88,
        'speed_variance': 12.0,
        'sigma_norm': 0.60,
        'weather_precipitation': 0.775,
        'weather_visibility': 0.5,
        'weather_wind_speed': 0.2,
        'weather_temperature': 0.1
    }

    row = pd.Series(mock_data)

    plugin_weights = {
        'weather': 0.15,
        'traffic': 0.85
    }

    plugins = extract_plugin_breakdowns(row, plugin_weights)

    print(f"Extracted {len(plugins)} plugin breakdowns:")
    for plugin in plugins:
        print(f"\n  Plugin: {plugin.plugin_name}")
        print(f"    Weight: {plugin.plugin_weight}")
        print(f"    Aggregated Score: {plugin.aggregated_score:.2f}")
        print(f"    Contribution: {plugin.contribution:.2f}")
        print(f"    Features: {len(plugin.features)}")
        print(f"    Enabled: {plugin.enabled}")

    # Verify we got both plugins
    plugin_names = [p.plugin_name for p in plugins]
    has_weather = "NOAA Weather" in plugin_names
    has_traffic = "VCC Traffic" in plugin_names

    print(f"\nValidation:")
    print(f"  Has Weather Plugin: {'PASS' if has_weather else 'FAIL'}")
    print(f"  Has Traffic Plugin: {'PASS' if has_traffic else 'FAIL'}")

    return has_weather and has_traffic


async def test_formula_documentation():
    """Test 3: Formula documentation endpoint."""
    print_section("TEST 3: Formula Documentation")

    doc = await get_formula_documentation()

    print("Formula Documentation:")
    print(f"  Version: {doc['formula_version']}")
    print(f"  Description: {doc['description']}")

    print(f"\n  Overall Formula:")
    print(f"    Expression: {doc['overall_formula']['expression']}")
    print(f"    Default Weights: {doc['overall_formula']['default_weights']}")

    print(f"\n  Traffic Index:")
    print(f"    Expression: {doc['traffic_index']['expression']}")

    print(f"\n  Weather Index:")
    print(f"    Expression: {doc['weather_index']['expression']}")

    print(f"\n  Risk Levels:")
    for level, info in doc['risk_levels'].items():
        print(f"    {level}: {info['range']} (color: {info['color']})")

    print(f"\n  Data Sources: {len(doc['data_sources'])}")
    for source in doc['data_sources']:
        print(f"    - {source['name']}: {len(source['features'])} features")

    return True


def test_breakdown_schema_validation():
    """Test 4: Validate SafetyIndexBreakdown schema."""
    print_section("TEST 4: Schema Validation")

    from app.schemas.transparency import SafetyIndexBreakdown, PluginBreakdown, FeatureBreakdown

    # Create a valid breakdown instance
    try:
        feature = FeatureBreakdown(
            raw_value=15.5,
            normalized=0.775,
            description="Test feature",
            unit="mm/hr"
        )
        print("Feature Breakdown: PASS")

        plugin = PluginBreakdown(
            plugin_name="Test Plugin",
            plugin_weight=0.5,
            contribution=35.0,
            aggregated_score=70.0,
            features={"test_feature": feature},
            enabled=True
        )
        print("Plugin Breakdown: PASS")

        breakdown = SafetyIndexBreakdown(
            intersection_id="test_001",
            intersection_name="Test Intersection",
            timestamp=datetime.now(),
            safety_index=72.4,
            vru_index=68.5,
            vehicle_index=72.0,
            weather_index=83.3,
            traffic_index=70.5,
            risk_level=compute_risk_level(72.4),
            plugins=[plugin],
            formula="72.4 = (70.5 × 0.85) + (83.3 × 0.15)",
            formula_components=[],
            formula_version="2.0",
            calculation_method="multi_source_weighted",
            data_quality="complete"
        )
        print("Safety Index Breakdown: PASS")

        # Validate the schema can be serialized
        json_data = breakdown.model_dump()
        print(f"\nSerialization: PASS ({len(json_data)} fields)")

        return True

    except Exception as e:
        print(f"Schema Validation: FAIL - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print(f"\n{'#'*80}")
    print(f"#  TRANSPARENCY API TEST SUITE (Phase 6)")
    print(f"#  Date: {datetime.now()}")
    print(f"{'#'*80}")

    results = []

    # Run tests
    results.append(("Risk Level Classification", test_risk_level_classification()))
    results.append(("Plugin Breakdown Extraction", test_plugin_breakdown_extraction()))

    # Run async test
    import asyncio
    results.append(("Formula Documentation", asyncio.run(test_formula_documentation())))

    results.append(("Schema Validation", test_breakdown_schema_validation()))

    # Summary
    print_section("TEST SUMMARY")

    tests_passed = sum(1 for _, passed in results if passed)
    tests_total = len(results)

    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n{'='*80}")
    print(f"Tests passed: {tests_passed}/{tests_total}")
    print(f"{'='*80}\n")

    return tests_passed == tests_total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
