"""
Test script for /time/range endpoint
Tests RT-SI trend calculation for a time range from 2025/11/01 8am to 2025/11/23 18:00
"""

import requests
from datetime import datetime
import json

# Configuration
BASE_URL = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index"
INTERSECTION = "glebe-potomac"
START_TIME = "2025-11-01T08:00:00"
END_TIME = "2025-11-01T18:00:00"  # Just 10 hours for faster testing
BIN_MINUTES = 15

def test_range_endpoint():
    """Test the /time/range endpoint"""
    
    print("=" * 80)
    print("Testing /time/range Endpoint")
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
            print(f"Total time points returned: {len(data)}")
            print()

            # Count time points with RT-SI data
            rt_si_count = sum(1 for point in data if point.get("rt_si_score") is not None)
            mcdm_count = len(data)
            
            print(f"Time points with MCDM data: {mcdm_count}")
            print(f"Time points with RT-SI data: {rt_si_count}")
            print(f"Time points missing RT-SI: {mcdm_count - rt_si_count}")
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
                print(f"  VRU Count: {first_point.get('vru_count')}")
                print()

                # Show last time point
                print("Last Time Point:")
                print("-" * 80)
                last_point = data[-1]
                print(f"  Time: {last_point.get('time_bin')}")
                print(f"  MCDM Index: {last_point.get('mcdm_index'):.2f}" if last_point.get('mcdm_index') else "  MCDM Index: N/A")
                print(f"  RT-SI Score: {last_point.get('rt_si_score'):.2f}" if last_point.get('rt_si_score') else "  RT-SI Score: N/A")
                print(f"  Vehicle Count: {last_point.get('vehicle_count')}")
                print(f"  VRU Count: {last_point.get('vru_count')}")
                print()

                # Show sample points with RT-SI data
                rt_si_points = [p for p in data if p.get("rt_si_score") is not None]
                if rt_si_points:
                    print(f"Sample Time Points with RT-SI (showing up to 5):")
                    print("-" * 80)
                    for i, point in enumerate(rt_si_points[:5]):
                        print(f"\n  Point {i+1}:")
                        print(f"    Time: {point.get('time_bin')}")
                        print(f"    MCDM Index: {point.get('mcdm_index'):.2f}")
                        print(f"    RT-SI Score: {point.get('rt_si_score'):.2f}")
                        # Check if vru_index exists in the response
                        vru_idx = point.get('vru_index')
                        if vru_idx is not None:
                            print(f"    VRU Index: {vru_idx:.4f}")
                        else:
                            print(f"    VRU Index: N/A (field not in response)")
                        
                        veh_idx = point.get('vehicle_index')
                        if veh_idx is not None:
                            print(f"    Vehicle Index: {veh_idx:.4f}")
                        else:
                            print(f"    Vehicle Index: N/A (field not in response)")
                        
                        print(f"    Vehicle Count: {point.get('vehicle_count')}")
                        print(f"    VRU Count: {point.get('vru_count')}")
                    print()

                # Calculate statistics
                mcdm_values = [p.get('mcdm_index') for p in data if p.get('mcdm_index')]
                rt_si_values = [p.get('rt_si_score') for p in data if p.get('rt_si_score')]
                
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

        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 120 seconds")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    print("=" * 80)


if __name__ == "__main__":
    test_range_endpoint()
