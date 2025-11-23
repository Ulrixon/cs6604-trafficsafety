#!/usr/bin/env python3
"""
Test RT-SI API endpoints with blended final safety index.
"""

import requests
from datetime import datetime, timedelta
import json

# API base URL
API_BASE_URL = "http://localhost:8000/api/v1/safety/index"


def test_specific_time():
    """Test /time/specific endpoint with RT-SI and blended index."""
    print("\n" + "=" * 80)
    print("Testing /time/specific endpoint")
    print("=" * 80)

    # Test parameters
    intersection = "glebe-potomac"
    time = datetime(2025, 11, 20, 20, 0, 0)
    bin_minutes = 15
    alpha_values = [0.0, 0.3, 0.5, 0.7, 1.0]

    for alpha in alpha_values:
        print(f"\n📊 Testing with α={alpha:.1f}")
        print("-" * 80)

        params = {
            "intersection": intersection,
            "time": time.isoformat(),
            "bin_minutes": bin_minutes,
            "alpha": alpha,
        }

        try:
            response = requests.get(f"{API_BASE_URL}/time/specific", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            print(f"✅ Request successful!")
            print(f"   Intersection: {data['intersection']}")
            print(f"   Time: {data['time_bin']}")
            print()
            print(f"   MCDM Index:          {data['mcdm_index']:.2f}")
            
            if data.get('rt_si_score') is not None:
                print(f"   RT-SI Score:         {data['rt_si_score']:.2f}")
                print(f"   - VRU Index:         {data.get('vru_index', 0):.6f}")
                print(f"   - Vehicle Index:     {data.get('vehicle_index', 0):.6f}")
            else:
                print(f"   RT-SI Score:         N/A (no data)")
            
            if data.get('final_safety_index') is not None:
                print(f"   Final Safety Index:  {data['final_safety_index']:.2f}")
                print(f"   Formula: {alpha:.1f}×{data.get('rt_si_score', 'N/A')} + {1-alpha:.1f}×{data['mcdm_index']:.2f}")
            else:
                print(f"   Final Safety Index:  N/A")

        except requests.HTTPError as e:
            print(f"❌ HTTP Error: {e.response.status_code}")
            print(f"   {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")


def test_time_range():
    """Test /time/range endpoint with RT-SI trend."""
    print("\n" + "=" * 80)
    print("Testing /time/range endpoint")
    print("=" * 80)

    # Test parameters
    intersection = "glebe-potomac"
    end_time = datetime(2025, 11, 20, 20, 0, 0)
    start_time = end_time - timedelta(hours=2)
    bin_minutes = 15
    alpha = 0.7

    print(f"\n📊 Testing trend from {start_time} to {end_time}")
    print(f"   α={alpha:.1f}")
    print("-" * 80)

    params = {
        "intersection": intersection,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "bin_minutes": bin_minutes,
        "alpha": alpha,
    }

    try:
        response = requests.get(f"{API_BASE_URL}/time/range", params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        print(f"✅ Request successful!")
        print(f"   Found {len(data)} time points")
        print()

        # Show first 3 and last 3 time points
        display_count = min(3, len(data))
        
        print(f"   First {display_count} time points:")
        for item in data[:display_count]:
            rt_si = item.get('rt_si_score')
            rt_si_str = f"{rt_si:.2f}" if rt_si is not None else "N/A"
            final = item.get('final_safety_index')
            final_str = f"{final:.2f}" if final is not None else "N/A"
            
            print(f"   - {item['time_bin']}: Final={final_str}, RT-SI={rt_si_str}, MCDM={item['mcdm_index']:.2f}")

        if len(data) > 6:
            print(f"   ... ({len(data) - 6} more) ...")
            
            print(f"   Last {display_count} time points:")
            for item in data[-display_count:]:
                rt_si = item.get('rt_si_score')
                rt_si_str = f"{rt_si:.2f}" if rt_si is not None else "N/A"
                final = item.get('final_safety_index')
                final_str = f"{final:.2f}" if final is not None else "N/A"
                
                print(f"   - {item['time_bin']}: Final={final_str}, RT-SI={rt_si_str}, MCDM={item['mcdm_index']:.2f}")

        # Calculate statistics
        rt_si_values = [item['rt_si_score'] for item in data if item.get('rt_si_score') is not None]
        final_values = [item['final_safety_index'] for item in data if item.get('final_safety_index') is not None]
        
        print()
        print(f"   Statistics:")
        print(f"   - Time points with RT-SI: {len(rt_si_values)}/{len(data)}")
        if rt_si_values:
            print(f"   - Avg RT-SI: {sum(rt_si_values)/len(rt_si_values):.2f}")
        if final_values:
            print(f"   - Avg Final Index: {sum(final_values)/len(final_values):.2f}")

    except requests.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main test function."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  RT-SI API Endpoint Testing".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)

    print("\n🔧 Testing blended safety index API endpoints")
    print("   Formula: Final Index = α×RT-SI + (1-α)×MCDM")

    test_specific_time()
    test_time_range()

    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  ✅ Testing Complete".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80 + "\n")


if __name__ == "__main__":
    main()
