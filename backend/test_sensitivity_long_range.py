"""
Test Sensitivity Analysis Endpoint (Long Range)

Tests the sensitivity analysis API with a long date range (2025/11/01 to 2025/11/23)
to reproduce timeout issues.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = (
    "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
)
INTERSECTION = "glebe-potomac"
START_TIME = "2025-11-01T08:00:00"
END_TIME = "2025-11-23T18:00:00"
BIN_MINUTES = 60  # Increased bin size to reduce data points
PERTURBATION_PCT = 0.25  # ±25%
N_SAMPLES = 20  # Reduced samples to try to get a result


def test_sensitivity_analysis_long_range():
    """Test the sensitivity analysis endpoint with long date range."""
    print("=" * 80)
    print("Testing Sensitivity Analysis Endpoint (Long Range)")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Intersection: {INTERSECTION}")
    print(f"Time Range: {START_TIME} to {END_TIME}")
    print(f"Bin Minutes: {BIN_MINUTES}")
    print(f"Perturbation: ±{PERTURBATION_PCT*100}%")
    print(f"Samples: {N_SAMPLES}")
    print()

    # Build URL
    url = f"{BASE_URL}/sensitivity-analysis"
    params = {
        "intersection": INTERSECTION,
        "start_time": START_TIME,
        "end_time": END_TIME,
        "bin_minutes": BIN_MINUTES,
        "perturbation_pct": PERTURBATION_PCT,
        "n_samples": N_SAMPLES,
    }

    print(f"Full URL: {url}")
    print(f"Parameters: {json.dumps(params, indent=2)}")
    print()

    print("Sending request... (this may take several minutes)")
    try:
        # Increased timeout to 300 seconds (5 minutes)
        response = requests.get(url, params=params, timeout=300)
        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print("✅ Request successful!")
            print()

            # Display results
            print("=" * 80)
            print("SENSITIVITY ANALYSIS RESULTS")
            print("=" * 80)

            # Basic info
            print(f"\n📍 Intersection: {data['intersection']}")
            print(
                f"⏱️  Time Range: {data['time_range']['start']} to {data['time_range']['end']}"
            )
            print(
                f"🔧 Perturbation: ±{data['perturbation_settings']['perturbation_pct']*100}%"
            )
            print(f"🎲 Samples: {data['perturbation_settings']['n_samples']}")

            # Baseline
            baseline = data["baseline"]
            print(f"\n📊 Baseline RT-SI Scores:")
            print(f"  Time Points: {len(baseline['timestamps'])}")
            
            if baseline['rt_si_scores']:
                print(
                    f"  Mean Score: {sum(baseline['rt_si_scores'])/len(baseline['rt_si_scores']):.2f}"
                )
                print(f"  Min Score: {min(baseline['rt_si_scores']):.2f}")
                print(f"  Max Score: {max(baseline['rt_si_scores']):.2f}")
            else:
                print("  No scores returned")

            # Stability Metrics
            stability = data["stability_metrics"]
            print(f"\n🔬 Stability Metrics:")
            print(f"  Total Perturbations: {stability['total_perturbations']}")
            print(f"  Total Time Points: {stability['total_time_points']}")

            print()
            print("=" * 80)
            print("✅ SENSITIVITY ANALYSIS COMPLETE")
            print("=" * 80)

        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.Timeout:
        print("❌ Request timed out (exceeded 300 seconds)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    test_sensitivity_analysis_long_range()
