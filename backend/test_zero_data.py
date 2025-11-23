"""
Test RT-SI with Zero Data

Tests that RT-SI now returns values for all time bins in a range,
even for dates like 11/13-11/16 where there's no traffic data.
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
INTERSECTION = "glebe-potomac"

# Test date range with likely no data (11/13-11/16)
START_TIME = "2024-11-13T08:00:00"
END_TIME = "2024-11-16T18:00:00"
BIN_MINUTES = 60  # Use 1-hour bins for faster testing


def test_zero_data_handling():
    """Test RT-SI handling of time periods with no traffic data."""
    print("=" * 80)
    print("Testing RT-SI Zero Data Handling (11/13-11/16)")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Intersection: {INTERSECTION}")
    print(f"Time Range: {START_TIME} to {END_TIME}")
    print(f"Bin Minutes: {BIN_MINUTES}")
    print()

    # Build URL
    url = f"{BASE_URL}/time/range"
    params = {
        "intersection": INTERSECTION,
        "start_time": START_TIME,
        "end_time": END_TIME,
        "bin_minutes": BIN_MINUTES,
        "include_correlations": False,  # Faster without correlations
    }

    print(f"Full URL: {url}")
    print(f"Parameters: {json.dumps(params, indent=2)}")
    print()

    print("Sending request...")
    try:
        response = requests.get(url, params=params, timeout=60)
        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print("✅ Request successful!")
            print()

            # Check response structure
            if isinstance(data, dict):
                time_series = data.get("time_series", [])
                metadata = data.get("metadata", {})
                
                print(f"📊 Response Structure: New format (with time_series)")
                print(f"   Metadata: {metadata}")
            else:
                time_series = data
                print(f"📊 Response Structure: Old format (list)")
            
            print()
            print(f"📈 Total Data Points: {len(time_series)}")
            
            if len(time_series) == 0:
                print("❌ NO DATA RETURNED - Issue not fixed!")
                print("   Expected: All time bins should be present even with zero traffic")
                return
            
            # Calculate expected number of bins
            start = datetime.fromisoformat(START_TIME)
            end = datetime.fromisoformat(END_TIME)
            expected_bins = int((end - start).total_seconds() / (BIN_MINUTES * 60))
            
            print(f"📊 Expected Time Bins: {expected_bins}")
            print(f"📊 Actual Time Bins: {len(time_series)}")
            
            if len(time_series) >= expected_bins:
                print("✅ All time bins present!")
            else:
                print(f"⚠️  Missing {expected_bins - len(time_series)} time bins")
            
            print()
            
            # Analyze RT-SI data
            rt_si_points = [p for p in time_series if p.get("rt_si_score") is not None]
            zero_traffic_points = [p for p in time_series if p.get("vehicle_count", 0) == 0 and p.get("vru_count", 0) == 0]
            
            print(f"🎯 RT-SI Available: {len(rt_si_points)} / {len(time_series)} points")
            print(f"🚦 Zero Traffic Points: {len(zero_traffic_points)} / {len(time_series)} points")
            
            if len(zero_traffic_points) > 0:
                print()
                print("📋 Sample Zero Traffic Points:")
                for i, point in enumerate(zero_traffic_points[:5], 1):
                    print(f"\n  {i}. Time: {point.get('time_bin')}")
                    print(f"     Vehicle Count: {point.get('vehicle_count', 'N/A')}")
                    print(f"     VRU Count: {point.get('vru_count', 'N/A')}")
                    print(f"     RT-SI Score: {point.get('rt_si_score', 'N/A')}")
                    
                    if point.get('rt_si_score') is not None:
                        print(f"     ✅ RT-SI computed with zero traffic!")
                    else:
                        print(f"     ❌ RT-SI missing for zero traffic")
            
            # Check if all points have RT-SI
            all_have_rtsi = all(p.get("rt_si_score") is not None for p in time_series)
            
            print()
            print("=" * 80)
            if all_have_rtsi and len(time_series) >= expected_bins:
                print("✅✅✅ SUCCESS: All time bins have RT-SI values!")
                print("   Zero traffic data is now handled correctly.")
            elif len(rt_si_points) > 0:
                print("⚠️  PARTIAL: Some time bins have RT-SI, but not all")
                print(f"   {len(rt_si_points)} / {expected_bins} bins have RT-SI")
            else:
                print("❌ FAILED: No RT-SI data returned")
            print("=" * 80)

        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.Timeout:
        print("❌ Request timed out (exceeded 60 seconds)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_zero_data_handling()
