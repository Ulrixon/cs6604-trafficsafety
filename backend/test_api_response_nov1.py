#!/usr/bin/env python3
"""
Test API response for Nov 1, 2025 10:00 AM to see what frontend receives
"""

import requests
from datetime import datetime


def test_api_response():
    """Test what the API actually returns"""

    base_url = "http://localhost:8000"
    intersection = "glebe-potomac"
    timestamp = "2025-11-01T10:00:00"
    alpha = 0.7

    print("=" * 70)
    print("API RESPONSE TEST")
    print("=" * 70)
    print(f"Endpoint: {base_url}/intersections/{intersection}/time/specific")
    print(f"Timestamp: {timestamp}")
    print(f"Alpha: {alpha}")
    print()

    try:
        url = f"{base_url}/intersections/{intersection}/time/specific"
        params = {"timestamp": timestamp, "alpha": alpha}

        response = requests.get(url, params=params, timeout=30)

        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print("RESPONSE DATA:")
            print("-" * 70)
            print(f"Intersection: {data.get('intersection')}")
            print(f"Timestamp: {data.get('timestamp')}")
            print()

            print("SAFETY SCORES:")
            print(f"  rt_si_score: {data.get('rt_si_score')}")
            print(f"  mcdm_score: {data.get('mcdm_score')}")
            print(f"  final_safety_index: {data.get('final_safety_index')}")
            print()

            print("RT-SI COMPONENTS:")
            print(f"  vru_index: {data.get('vru_index')}")
            print(f"  vehicle_index: {data.get('vehicle_index')}")
            print()

            print("RAW JSON:")
            print("-" * 70)
            import json

            print(json.dumps(data, indent=2))

            print()
            print("=" * 70)
            print("DIAGNOSIS")
            print("=" * 70)

            rt_si = data.get("rt_si_score")
            if rt_si is None:
                print("❌ rt_si_score is NULL/None in API response")
                print("   This is why frontend shows 'NA'")
                print()
                print("   Possible causes:")
                print("   1. API returns None when RT-SI calculation fails")
                print("   2. API doesn't include rt_si_score in response")
                print("   3. Database query returns NULL")
            elif rt_si == 0.0:
                print("✓ rt_si_score is 0.0 in API response")
                print("   Frontend should display this as 0.00, not NA")
                print()
                print("   Check frontend logic:")
                print("   - Does it treat 0.0 as falsy and show 'NA'?")
                print("   - Look for: if rt_si_score: ... else: 'NA'")
            else:
                print(f"✓ rt_si_score = {rt_si}")

        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API")
        print("   Make sure backend is running: uvicorn app.main:app")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_api_response()
