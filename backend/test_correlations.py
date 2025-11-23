"""
Test script for correlation analysis in range query endpoint.

Tests the /time/range endpoint with correlation analysis to validate
that each safety index component corresponds to real safety mechanisms.
"""

import requests
from datetime import datetime
import json

# Configuration
BASE_URL = (
    "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
)
INTERSECTION = "glebe-potomac"
START_TIME = "2025-11-01T08:00:00"
END_TIME = "2025-11-01T18:00:00"  # 10-hour range for testing
BIN_MINUTES = 15


def test_correlation_analysis():
    """Test the /time/range endpoint with correlation analysis"""

    print("=" * 80)
    print("Testing Correlation Analysis in /time/range Endpoint")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Intersection: {INTERSECTION}")
    print(f"Start Time: {START_TIME}")
    print(f"End Time: {END_TIME}")
    print(f"Bin Minutes: {BIN_MINUTES}")
    print()

    # Build the URL
    url = f"{BASE_URL}/time/range"
    params = {
        "intersection": INTERSECTION,
        "start_time": START_TIME,
        "end_time": END_TIME,
        "bin_minutes": BIN_MINUTES,
        "include_correlations": True,
    }

    print(f"Full URL: {url}")
    print(f"Parameters: {json.dumps(params, indent=2)}")
    print()

    try:
        print("Sending request...")
        response = requests.get(url, params=params, timeout=120)

        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print(f"✅ Request successful!")
            print()

            # Check response structure
            if "time_series" in data:
                print(f"Time series data points: {len(data['time_series'])}")
            else:
                print("⚠️  No time_series field in response")

            if "metadata" in data:
                meta = data["metadata"]
                print(f"Metadata:")
                print(f"  Intersection: {meta.get('intersection')}")
                print(f"  Data points: {meta.get('data_points')}")
                print()

            if "correlation_analysis" in data and data["correlation_analysis"]:
                corr = data["correlation_analysis"]

                if "error" in corr:
                    print(f"❌ Correlation analysis error: {corr['error']}")
                else:
                    print("📊 CORRELATION ANALYSIS RESULTS")
                    print("=" * 80)
                    print()

                    # Summary
                    if "summary" in corr:
                        summary = corr["summary"]
                        print("Summary:")
                        print(
                            f"  Total observations: {summary.get('total_observations')}"
                        )
                        print(
                            f"  Variables analyzed: {len(summary.get('variables_analyzed', []))}"
                        )
                        print()

                    # Traffic to Safety Indices
                    if "traffic_to_safety" in corr:
                        print("🚗 Traffic Variables → Safety Indices")
                        print("-" * 80)
                        traffic_safety = corr["traffic_to_safety"]

                        for target, predictors in traffic_safety.items():
                            print(f"\nTarget: {target}")
                            for pred, stats in predictors.items():
                                if stats.get("pearson_significant") or stats.get(
                                    "spearman_significant"
                                ):
                                    print(f"  {pred}:")
                                    print(
                                        f"    Pearson r: {stats['pearson_r']:.3f} (p={stats['pearson_p']:.4f})"
                                    )
                                    print(
                                        f"    Spearman r: {stats['spearman_r']:.3f} (p={stats['spearman_p']:.4f})"
                                    )
                                    print(
                                        f"    Relationship: {stats.get('relationship', 'N/A')}"
                                    )
                        print()

                    # RT-SI Components to RT-SI
                    if "rtsi_components_to_rtsi" in corr:
                        print("⚡ RT-SI Components → RT-SI Score")
                        print("-" * 80)
                        rtsi_comps = corr["rtsi_components_to_rtsi"]

                        for target, predictors in rtsi_comps.items():
                            print(f"\nTarget: {target}")
                            for pred, stats in predictors.items():
                                if stats.get("spearman_significant"):
                                    print(f"  {pred}:")
                                    print(
                                        f"    Spearman r: {stats['spearman_r']:.3f} (p={stats['spearman_p']:.4f})"
                                    )
                                    print(
                                        f"    Relationship: {stats.get('relationship', 'N/A')}"
                                    )
                        print()

                    # Monotonic Trends (Safety Mechanism Validation)
                    if "monotonic_trends" in corr:
                        print(
                            "📈 Monotonic Trend Analysis (Safety Mechanism Validation)"
                        )
                        print("-" * 80)
                        trends = corr["monotonic_trends"]

                        validated = 0
                        total = 0

                        for trend_name, trend_data in trends.items():
                            total += 1
                            if trend_data.get("validated"):
                                validated += 1
                                status = "✅ VALIDATED"
                            elif trend_data.get("matches_expectation"):
                                status = "⚠️  Matches but not significant"
                            else:
                                status = "❌ Does not match expectation"

                            print(f"\n{status}")
                            print(f"  Mechanism: {trend_data.get('mechanism')}")
                            print(
                                f"  {trend_data.get('predictor')} → {trend_data.get('target')}"
                            )
                            print(
                                f"  Expected: {trend_data.get('expected_direction')} | Observed: {trend_data.get('observed_direction')}"
                            )

                            # Handle None values in spearman_r and p_value
                            spearman_r = trend_data.get("spearman_r")
                            p_value = trend_data.get("p_value")
                            if spearman_r is not None and p_value is not None:
                                print(
                                    f"  Spearman r: {spearman_r:.3f} (p={p_value:.4f})"
                                )
                            else:
                                print(f"  Spearman r: N/A (insufficient data)")

                            print(f"  N samples: {trend_data.get('n_samples')}")

                        print()
                        print(
                            f"Summary: {validated}/{total} safety mechanisms validated ({validated/total*100:.1f}%)"
                        )
                        print()

                    # Partial Correlations (Independent Contributions)
                    if "partial_correlations" in corr:
                        print("🔬 Partial Correlations (Independent Contributions)")
                        print("-" * 80)
                        partial = corr["partial_correlations"]

                        for name, data in partial.items():
                            print(f"\n{name}:")
                            print(
                                f"  {data.get('x_variable')} → {data.get('y_variable')}"
                            )
                            print(
                                f"  Controlling for: {', '.join(data.get('control_variables', []))}"
                            )
                            print(
                                f"  Partial correlation: {data.get('partial_correlation'):.3f}"
                            )
                            print(f"  {data.get('interpretation')}")
                        print()

            else:
                print("⚠️  No correlation analysis in response")

        elif response.status_code == 400:
            print(f"❌ Bad Request (400)")
            try:
                error_data = response.json()
                print(f"Error: {error_data.get('detail', response.text)}")
            except:
                print(f"Response: {response.text}")
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 120 seconds")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()

    print("=" * 80)


if __name__ == "__main__":
    test_correlation_analysis()
