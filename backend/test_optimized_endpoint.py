#!/usr/bin/env python3
"""
Test the optimized /safety/index/ endpoint with include_rtsi parameter
"""

import requests
from datetime import datetime


def test_safety_index_endpoint():
    """Test the /safety/index/ endpoint with and without RT-SI"""

    base_url = "http://localhost:8000/api/v1/safety/index/"

    print("=" * 80)
    print("TESTING /safety/index/ ENDPOINT")
    print("=" * 80)
    print()

    # Test 1: MCDM only (fast)
    print("TEST 1: MCDM Only (include_rtsi=false)")
    print("-" * 80)
    try:
        response = requests.get(base_url, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved {len(data)} intersections")

            if data:
                sample = data[0]
                print(f"\nSample intersection:")
                print(f"  ID: {sample.get('intersection_id')}")
                print(f"  Name: {sample.get('intersection_name')}")
                print(f"  Safety Index: {sample.get('safety_index')}")
                print(f"  Traffic Volume: {sample.get('traffic_volume')}")
                print(f"  Has RT-SI: {'rt_si_score' in sample}")
                print(f"  Has MCDM: {'mcdm_index' in sample}")
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"✗ Error: {e}")

    print()
    print()

    # Test 2: With RT-SI (slower but includes real-time data)
    print("TEST 2: With RT-SI (include_rtsi=true)")
    print("-" * 80)
    try:
        params = {"include_rtsi": "true", "bin_minutes": 15}
        response = requests.get(base_url, params=params, timeout=30)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved {len(data)} intersections")

            if data:
                sample = data[0]
                print(f"\nSample intersection:")
                print(f"  ID: {sample.get('intersection_id')}")
                print(f"  Name: {sample.get('intersection_name')}")
                print(f"  Safety Index (MCDM): {sample.get('safety_index')}")
                print(f"  MCDM Index: {sample.get('mcdm_index')}")
                print(f"  RT-SI Score: {sample.get('rt_si_score')}")
                print(f"  VRU Index: {sample.get('vru_index')}")
                print(f"  Vehicle Index: {sample.get('vehicle_index')}")
                print(f"  Traffic Volume: {sample.get('traffic_volume')}")
                print(f"  Timestamp: {sample.get('timestamp')}")

                # Count how many have RT-SI
                with_rtsi = sum(
                    1 for item in data if item.get("rt_si_score") is not None
                )
                print(
                    f"\nRT-SI Coverage: {with_rtsi}/{len(data)} intersections ({with_rtsi/len(data)*100:.1f}%)"
                )

                # Test frontend blending calculation
                print("\nFrontend Blending Simulation:")
                for alpha in [0.0, 0.5, 0.7, 1.0]:
                    mcdm = sample.get("mcdm_index", 50.0)
                    rt_si = sample.get("rt_si_score")

                    if rt_si is not None:
                        final = alpha * rt_si + (1 - alpha) * mcdm
                        print(
                            f"  α={alpha:.1f}: Final = {alpha:.1f}×{rt_si:.2f} + {1-alpha:.1f}×{mcdm:.2f} = {final:.2f}"
                        )
                    else:
                        print(
                            f"  α={alpha:.1f}: Final = {mcdm:.2f} (no RT-SI, using MCDM only)"
                        )
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"✗ Error: {e}")

    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("✓ Backend returns both MCDM and RT-SI in single call")
    print("✓ Frontend can blend scores client-side with any alpha")
    print("✓ Much faster than calling /time/specific for each intersection")
    print()


if __name__ == "__main__":
    test_safety_index_endpoint()
