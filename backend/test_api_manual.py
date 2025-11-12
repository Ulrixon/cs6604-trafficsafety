"""
Manual test script for the Safety Index API

Run this after starting the server to verify it returns real data.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_list_intersections():
    """Test listing all intersections with safety indices"""
    print("Testing /api/v1/safety/index/ endpoint...")
    print("(This will query Trino and compute real safety indices)")
    print("Please wait...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/safety/index/", timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Returned {len(data)} intersections")
            print("\nFirst intersection:")
            print(json.dumps(data[0], indent=2))
            
            print("\nAll intersections summary:")
            for item in data:
                print(f"  - {item['intersection_name']}: Safety Index = {item['safety_index']:.1f}, Traffic = {item['traffic_volume']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_get_single_intersection():
    """Test getting a single intersection by ID"""
    print("Testing /api/v1/safety/index/101 endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/safety/index/101", timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()

if __name__ == "__main__":
    print("=" * 70)
    print("Safety Index API Manual Test")
    print("=" * 70)
    print()
    
    test_health()
    test_list_intersections()
    test_get_single_intersection()
    
    print("=" * 70)
    print("Test complete!")
    print("=" * 70)
