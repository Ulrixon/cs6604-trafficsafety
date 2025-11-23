#!/usr/bin/env python3
"""
Test if the FastAPI app can start without errors.
This simulates Cloud Run startup to identify issues.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("TESTING FASTAPI APP STARTUP")
print("=" * 80)
print()

# Test 1: Import main module
print("1. Testing module imports...")
try:
    from app.main import app
    print("   ✓ Main module imported successfully")
except Exception as e:
    print(f"   ✗ FAILED to import main module:")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 2: Check if app is created
print("2. Testing FastAPI app creation...")
try:
    print(f"   ✓ App created: {app.title}")
    print(f"   Version: {app.version}")
    print(f"   Routes: {len(app.routes)} registered")
except Exception as e:
    print(f"   ✗ FAILED to create app:")
    print(f"   Error: {e}")
    sys.exit(1)

print()

# Test 3: List all routes
print("3. Listing registered routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ','.join(route.methods) if route.methods else 'N/A'
        print(f"   {methods:10} {route.path}")

print()

# Test 4: Try to create a test client
print("4. Testing FastAPI test client...")
try:
    from fastapi.testclient import TestClient
    client = TestClient(app)
    print("   ✓ Test client created")
except Exception as e:
    print(f"   ✗ FAILED to create test client:")
    print(f"   Error: {e}")
    sys.exit(1)

print()

# Test 5: Test health endpoint
print("5. Testing /health endpoint...")
try:
    response = client.get("/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    if response.status_code == 200:
        print("   ✓ Health check passed")
    else:
        print(f"   ✗ Health check failed with status {response.status_code}")
except Exception as e:
    print(f"   ✗ FAILED to test health endpoint:")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 6: Check database connectivity (non-blocking)
print("6. Testing database connection...")
try:
    from app.services.db_client import get_db_client
    db = get_db_client()
    print("   ✓ Database client created (connection will be tested on first query)")
    
    # Try a simple query
    result = db.execute_query("SELECT 1 as test;")
    if result:
        print("   ✓ Database connection works")
    else:
        print("   ⚠ Database query returned no results (might be connection issue)")
except Exception as e:
    print(f"   ⚠ Database connection issue (not critical for startup):")
    print(f"   Error: {e}")

print()
print("=" * 80)
print("STARTUP TEST SUMMARY")
print("=" * 80)

try:
    # Test if app can handle a simple request
    response = client.get("/health")
    if response.status_code == 200:
        print("✓ App can start and respond to requests")
        print("✓ Ready for deployment to Cloud Run")
        print()
        print("To deploy:")
        print("  gcloud run deploy traffic-safety-backend \\")
        print("    --source . \\")
        print("    --region us-east1 \\")
        print("    --port 8080")
    else:
        print("✗ App has issues responding to requests")
        sys.exit(1)
except Exception as e:
    print(f"✗ App cannot start properly: {e}")
    sys.exit(1)
