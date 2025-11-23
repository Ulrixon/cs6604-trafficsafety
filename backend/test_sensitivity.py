"""
Test Sensitivity Analysis Endpoint

Tests the sensitivity analysis API which validates RT-SI robustness
by perturbing parameters and measuring stability.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
INTERSECTION = "glebe-potomac"
START_TIME = "2025-11-01T08:00:00"
END_TIME = "2025-11-01T18:00:00"
BIN_MINUTES = 15
PERTURBATION_PCT = 0.25  # ±25%
N_SAMPLES = 50  # Reduced for faster testing


def test_sensitivity_analysis():
    """Test the sensitivity analysis endpoint."""
    print("=" * 80)
    print("Testing Sensitivity Analysis Endpoint")
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

    print("Sending request... (this may take 30-60 seconds)")
    try:
        response = requests.get(url, params=params, timeout=120)
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
            print(f"⏱️  Time Range: {data['time_range']['start']} to {data['time_range']['end']}")
            print(f"🔧 Perturbation: ±{data['perturbation_settings']['perturbation_pct']*100}%")
            print(f"🎲 Samples: {data['perturbation_settings']['n_samples']}")

            # Baseline
            baseline = data["baseline"]
            print(f"\n📊 Baseline RT-SI Scores:")
            print(f"  Time Points: {len(baseline['timestamps'])}")
            print(f"  Mean Score: {sum(baseline['rt_si_scores'])/len(baseline['rt_si_scores']):.2f}")
            print(f"  Min Score: {min(baseline['rt_si_scores']):.2f}")
            print(f"  Max Score: {max(baseline['rt_si_scores']):.2f}")

            # Stability Metrics
            stability = data["stability_metrics"]
            print(f"\n🔬 Stability Metrics:")
            print(f"  Total Perturbations: {stability['total_perturbations']}")
            print(f"  Total Time Points: {stability['total_time_points']}")

            # Spearman Correlations
            spearman = stability["spearman_correlations"]
            print(f"\n  📈 Spearman Rank Correlations (higher = more stable):")
            print(f"     Mean: {spearman['mean']:.4f}")
            print(f"     Std:  {spearman['std']:.4f}")
            print(f"     Min:  {spearman['min']:.4f}")
            print(f"     Max:  {spearman['max']:.4f}")

            # Interpretation
            if spearman["mean"] > 0.9:
                print("     ✅ Excellent stability - rankings highly preserved")
            elif spearman["mean"] > 0.7:
                print("     ✅ Good stability - rankings generally preserved")
            elif spearman["mean"] > 0.5:
                print("     ⚠️  Moderate stability - some ranking changes")
            else:
                print("     ❌ Poor stability - significant ranking changes")

            # Score Changes
            score_changes = stability["score_changes"]
            print(f"\n  📊 Score Changes:")
            print(f"     Mean Absolute Difference: {score_changes['mean']:.2f}")
            print(f"     Std Deviation: {score_changes['std']:.2f}")
            print(f"     Maximum Change: {score_changes['max']:.2f}")
            print(f"     95th Percentile: {score_changes['percentile_95']:.2f}")

            # Tier Changes
            tier_changes = stability["tier_changes"]
            print(f"\n  🎯 Risk Tier Changes (Low→High reclassifications):")
            print(f"     Mean Changes: {tier_changes['mean']:.2f}")
            print(f"     Max Changes: {tier_changes['max']}")
            print(f"     No Change %: {tier_changes['percentage_no_change']:.1f}%")

            # Parameter Importance
            importance = data["parameter_importance"]
            print(f"\n🔍 Parameter Importance (sorted by impact):")
            print(f"{'Parameter':<20} {'Correlation':<15} {'Impact'}")
            print("-" * 55)
            for param, info in importance.items():
                corr = info["correlation"]
                impact = info["interpretation"]
                print(f"{param:<20} {corr:>10.4f}     {impact}")

            # Find most impactful parameters
            high_impact = [
                p for p, info in importance.items() if info["interpretation"] == "High Impact"
            ]
            if high_impact:
                print(f"\n⚠️  Most Sensitive Parameters: {', '.join(high_impact)}")

            # Sample Results
            if "perturbed_samples" in data and data["perturbed_samples"]:
                print(f"\n📝 Sample Perturbed Results (showing first 3):")
                for i, sample in enumerate(data["perturbed_samples"][:3], 1):
                    print(f"\n  Sample {i} ({sample['label']}):")
                    params = sample["params"]
                    print(f"    LAMBDA: {params['LAMBDA']:.0f}")
                    print(
                        f"    BETA: [{params['BETA1']:.3f}, {params['BETA2']:.3f}, {params['BETA3']:.3f}]"
                    )
                    print(
                        f"    K: [{params['K1_SPEED']:.2f}, {params['K2_VAR']:.2f}, {params['K3_CONF']:.2f}]"
                    )
                    print(
                        f"    OMEGA: [VRU:{params['OMEGA_VRU']:.3f}, VEH:{params['OMEGA_VEH']:.3f}]"
                    )
                    scores = sample["scores"]
                    print(f"    RT-SI Mean: {sum(scores)/len(scores):.2f}")

            print()
            print("=" * 80)
            print("✅ SENSITIVITY ANALYSIS COMPLETE")
            print("=" * 80)

            # Conclusion
            print("\n📋 Summary:")
            if spearman["mean"] > 0.8 and tier_changes["percentage_no_change"] > 70:
                print("✅ RT-SI demonstrates ROBUST performance")
                print("   - Rankings are highly stable under parameter perturbation")
                print("   - Most intersections maintain their risk tier classification")
                print("   - Index is not overly sensitive to parameter tuning")
            elif spearman["mean"] > 0.6:
                print("⚠️  RT-SI shows MODERATE robustness")
                print("   - Some stability in rankings but some sensitivity exists")
                print("   - Consider refining parameters or using ensemble approaches")
            else:
                print("❌ RT-SI shows SENSITIVITY to parameter choices")
                print("   - Significant changes in rankings and classifications")
                print("   - Parameter calibration may need review")

        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.Timeout:
        print("❌ Request timed out (exceeded 120 seconds)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    test_sensitivity_analysis()
