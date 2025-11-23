"""
Test script for /time/range endpoint - FULL RANGE
Tests RT-SI trend calculation for the full requested range: 2025/11/01 8am to 2025/11/23 18:00
This is a 22+ day range and may take a long time or timeout.
"""

import requests
from datetime import datetime
import json

# Configuration
BASE_URL = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
INTERSECTION = "glebe-potomac"
START_TIME = "2025-11-01T08:00:00"
END_TIME = "2025-11-23T18:00:00"
BIN_MINUTES = 15

def test_full_range_endpoint():
    """Test the /time/range endpoint with full 22-day range"""
    
    # Calculate expected number of time points
    start_dt = datetime.fromisoformat(START_TIME)
    end_dt = datetime.fromisoformat(END_TIME)
    hours = (end_dt - start_dt).total_seconds() / 3600
    expected_points = int(hours * (60 / BIN_MINUTES))
    
    print("=" * 80)
    print("Testing /time/range Endpoint - FULL RANGE")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Intersection: {INTERSECTION}")
    print(f"Start Time: {START_TIME}")
    print(f"End Time: {END_TIME}")
    print(f"Bin Minutes: {BIN_MINUTES}")
    print(f"Duration: {hours:.1f} hours ({hours/24:.1f} days)")
    print(f"Expected time points: ~{expected_points}")
    print()
    print("⚠️  WARNING: This is a large range and may take several minutes or timeout!")
    print()

    # Build the URL
    url = f"{BASE_URL}/time/range"
    params = {
        "intersection": INTERSECTION,
        "start_time": START_TIME,
        "end_time": END_TIME,
        "bin_minutes": BIN_MINUTES,
    }

    print(f"Full URL: {url}")
    print(f"Parameters: {json.dumps(params, indent=2)}")
    print()

    try:
        print("Sending request... (timeout=300 seconds)")
        response = requests.get(url, params=params, timeout=300)
        
        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Request successful!")
            print(f"Total time points returned: {len(data)}")
            print()

            # Count time points with RT-SI data
            rt_si_count = sum(1 for point in data if point.get("rt_si_score") is not None)
            mcdm_count = len(data)
            
            print(f"Time points with MCDM data: {mcdm_count}")
            print(f"Time points with RT-SI data: {rt_si_count}")
            print(f"Time points missing RT-SI: {mcdm_count - rt_si_count}")
            print(f"RT-SI coverage: {(rt_si_count/mcdm_count*100):.1f}%")
            print()

            if data:
                # Show first time point
                print("First Time Point:")
                print("-" * 80)
                first_point = data[0]
                print(f"  Time: {first_point.get('time_bin')}")
                print(f"  MCDM Index: {first_point.get('mcdm_index'):.2f}" if first_point.get('mcdm_index') else "  MCDM Index: N/A")
                print(f"  RT-SI Score: {first_point.get('rt_si_score'):.2f}" if first_point.get('rt_si_score') else "  RT-SI Score: N/A")
                print(f"  Vehicle Count: {first_point.get('vehicle_count')}")
                print()

                # Show last time point
                print("Last Time Point:")
                print("-" * 80)
                last_point = data[-1]
                print(f"  Time: {last_point.get('time_bin')}")
                print(f"  MCDM Index: {last_point.get('mcdm_index'):.2f}" if last_point.get('mcdm_index') else "  MCDM Index: N/A")
                print(f"  RT-SI Score: {last_point.get('rt_si_score'):.2f}" if last_point.get('rt_si_score') else "  RT-SI Score: N/A")
                print(f"  Vehicle Count: {last_point.get('vehicle_count')}")
                print()

                # Calculate statistics
                mcdm_values = [p.get('mcdm_index') for p in data if p.get('mcdm_index')]
                rt_si_values = [p.get('rt_si_score') for p in data if p.get('rt_si_score')]
                vehicle_counts = [p.get('vehicle_count', 0) for p in data]
                
                if mcdm_values:
                    print("MCDM Statistics:")
                    print(f"  Average: {sum(mcdm_values)/len(mcdm_values):.2f}")
                    print(f"  Min: {min(mcdm_values):.2f}")
                    print(f"  Max: {max(mcdm_values):.2f}")
                    print()

                if rt_si_values:
                    print("RT-SI Statistics:")
                    print(f"  Average: {sum(rt_si_values)/len(rt_si_values):.2f}")
                    print(f"  Min: {min(rt_si_values):.2f}")
                    print(f"  Max: {max(rt_si_values):.2f}")
                    print()

                print("Traffic Statistics:")
                print(f"  Total Vehicles: {sum(vehicle_counts):,}")
                print(f"  Avg Vehicles per bin: {sum(vehicle_counts)/len(vehicle_counts):.1f}")
                print()

                # Show daily breakdown
                print("Daily RT-SI Data Availability:")
                print("-" * 80)
                from collections import defaultdict
                daily_counts = defaultdict(lambda: {"total": 0, "with_rtsi": 0})
                
                for point in data:
                    date = point.get('time_bin', '').split('T')[0]
                    daily_counts[date]["total"] += 1
                    if point.get("rt_si_score") is not None:
                        daily_counts[date]["with_rtsi"] += 1
                
                for date in sorted(daily_counts.keys()):
                    counts = daily_counts[date]
                    coverage = (counts["with_rtsi"] / counts["total"] * 100) if counts["total"] > 0 else 0
                    print(f"  {date}: {counts['with_rtsi']:3d}/{counts['total']:3d} points ({coverage:5.1f}%)")
                print()

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
        print("❌ Request timed out after 300 seconds")
        print("   The time range is too large for the current backend implementation.")
        print("   Consider using a shorter time range or implementing pagination.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 80)


if __name__ == "__main__":
    test_full_range_endpoint()
