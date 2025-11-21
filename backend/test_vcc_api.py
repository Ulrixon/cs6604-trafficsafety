"""
Test script for VCC API endpoints.

Tests all VCC API functionality including:
- Connection and authentication
- Historical data collection
- Real-time streaming status
- MapData retrieval

Run this after starting the server to verify VCC integration works.
"""

import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
API_PREFIX = f"{BASE_URL}/api/v1/vcc"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_vcc_status():
    """Test VCC API connection status"""
    print_section("1. Testing VCC API Status")
    
    try:
        response = requests.get(f"{API_PREFIX}/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Connection Status: {data.get('status')}")
            print(f"  Authentication: {data.get('authentication')}")
            print(f"  Base URL: {data.get('base_url')}")
            print(f"  Data Source: {data.get('data_source')}")
            print(f"  Real-time Enabled: {data.get('realtime_enabled')}")
            print(f"  MapData Available: {data.get('mapdata_available')}")
            print(f"  Streaming Active: {data.get('streaming_active')}")
            return data
        else:
            print(f"✗ Error: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  Make sure the server is running and VCC credentials are configured")
        return None


def test_connection():
    """Test VCC API connection and authentication"""
    print_section("2. Testing VCC API Connection")
    
    try:
        response = requests.get(f"{API_PREFIX}/test/connection", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            print(f"Authenticated: {data.get('authenticated')}")
            
            if data.get('endpoints'):
                print("\nEndpoints:")
                for endpoint, info in data['endpoints'].items():
                    available = "✓" if info.get('available') else "✗"
                    count = info.get('message_count', 0)
                    print(f"  {available} {endpoint.upper()}: {count} messages")
            
            return data.get('authenticated', False)
        else:
            print(f"✗ Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False


def test_mapdata():
    """Test MapData retrieval"""
    print_section("3. Testing MapData Retrieval")
    
    try:
        response = requests.get(f"{API_PREFIX}/mapdata", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            print(f"MapData Count: {data.get('count', 0)}")
            
            if data.get('count', 0) > 0:
                print(f"\n✓ Successfully retrieved {data['count']} MapData messages")
                # Show first intersection if available
                mapdata_list = data.get('mapdata', [])
                if mapdata_list:
                    first = mapdata_list[0]
                    if 'intersections' in first:
                        int_list = first['intersections']
                        if int_list:
                            print(f"  First intersection ID: {int_list[0].get('id', {}).get('id', 'unknown')}")
            else:
                print("⚠ No MapData available")
            
            return data.get('count', 0) > 0
        else:
            print(f"✗ Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ MapData test failed: {e}")
        return False


def test_historical_collection():
    """Test starting historical data collection"""
    print_section("4. Testing Historical Data Collection")
    
    # Use last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    payload = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "save_to_parquet": True
    }
    
    print(f"Requesting collection for:")
    print(f"  Start: {start_date.date()}")
    print(f"  End: {end_date.date()}")
    print("\nNote: This starts a background job. Check server logs for progress.")
    
    try:
        response = requests.post(
            f"{API_PREFIX}/historical/collect",
            json=payload,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Status: {data.get('status')}")
            print(f"  Message: {data.get('message')}")
            print(f"  Save to Parquet: {data.get('save_to_parquet')}")
            return True
        else:
            print(f"✗ Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Collection request failed: {e}")
        return False


def test_realtime_status():
    """Test real-time streaming status"""
    print_section("5. Testing Real-Time Streaming Status")
    
    try:
        response = requests.get(f"{API_PREFIX}/realtime/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Running: {data.get('running', False)}")
            print(f"BSM Buffer Size: {data.get('buffer_size_bsm', 0)}")
            print(f"PSM Buffer Size: {data.get('buffer_size_psm', 0)}")
            print(f"Window Size: {data.get('window_size', 0)} / {data.get('window_capacity', 15)}")
            
            if data.get('current_interval_start'):
                print(f"Current Interval: {data.get('current_interval_start')}")
            
            if not data.get('running'):
                print("\n⚠ Real-time streaming is not active")
                print("  Use POST /api/v1/vcc/realtime/start to start streaming")
            
            return data
        else:
            print(f"✗ Error: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Status check failed: {e}")
        return None


def test_realtime_start():
    """Test starting real-time streaming (optional - will run indefinitely)"""
    print_section("6. Testing Real-Time Streaming Start")
    
    print("⚠ WARNING: This will start real-time streaming which runs continuously")
    print("⚠ Press Ctrl+C in server logs to stop, or use POST /realtime/stop")
    print("\nSkipping this test by default...")
    print("To test manually, run:")
    print(f"  curl -X POST {API_PREFIX}/realtime/start -H 'Content-Type: application/json' -d '{{\"intersection_id\": \"all\"}}'")
    
    return None


def main():
    """Run all tests"""
    print("=" * 70)
    print("  VCC API Integration Test Suite")
    print("=" * 70)
    print(f"\nTesting API at: {BASE_URL}")
    print(f"VCC endpoints at: {API_PREFIX}")
    print("\nMake sure:")
    print("  1. Server is running (uvicorn or Docker)")
    print("  2. VCC_CLIENT_ID and VCC_CLIENT_SECRET are set in .env")
    print("  3. VCC API is accessible from your network")
    
    results = {}
    
    # Test 1: Status
    status_data = test_vcc_status()
    results['status'] = status_data is not None
    
    # Test 2: Connection
    if status_data:
        results['connection'] = test_connection()
    else:
        print("\n⚠ Skipping connection test (status check failed)")
        results['connection'] = False
    
    # Test 3: MapData
    if results.get('connection'):
        results['mapdata'] = test_mapdata()
    else:
        print("\n⚠ Skipping MapData test (connection failed)")
        results['mapdata'] = False
    
    # Test 4: Historical Collection
    if results.get('connection'):
        results['historical'] = test_historical_collection()
    else:
        print("\n⚠ Skipping historical collection test (connection failed)")
        results['historical'] = False
    
    # Test 5: Real-time Status
    results['realtime_status'] = test_realtime_status() is not None
    
    # Test 6: Real-time Start (skipped by default)
    results['realtime_start'] = None
    
    # Summary
    print_section("Test Summary")
    
    passed = sum(1 for v in results.values() if v is True)
    total = sum(1 for v in results.values() if v is not None)
    
    for test_name, result in results.items():
        if result is None:
            status = "SKIPPED"
        elif result:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"  {test_name:20} {status}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! VCC API integration is working.")
    elif passed > 0:
        print("\n⚠ Some tests failed. Check VCC credentials and network connectivity.")
    else:
        print("\n✗ All tests failed. Check server configuration and VCC credentials.")
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("  1. Check server logs for detailed error messages")
    print("  2. Verify VCC_CLIENT_ID and VCC_CLIENT_SECRET in .env")
    print("  3. Test VCC API directly from notebook: data/vcc-api-exploration.ipynb")
    print("  4. Check Parquet storage at: backend/data/parquet/")
    print("=" * 70)


if __name__ == "__main__":
    main()

