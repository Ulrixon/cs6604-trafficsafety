"""
Test script for MCDM integration in backend API

Tests the full pipeline:
1. Database connection
2. MCDM safety score calculation
3. Intersection endpoint
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.db_client import get_db_client, close_db_client
from app.services.mcdm_service import MCDMSafetyIndexService
from app.services.intersection_service import get_all
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_db_connection():
    """Test database connection."""
    print("\n" + "=" * 80)
    print("TEST 1: Database Connection")
    print("=" * 80)

    try:
        client = get_db_client()

        # Test query
        tables = client.execute_query(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 5;
        """
        )

        print(f"✓ Connected to database")
        print(f"✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['table_name']}")

        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def test_mcdm_calculation():
    """Test MCDM safety score calculation."""
    print("\n" + "=" * 80)
    print("TEST 2: MCDM Safety Score Calculation")
    print("=" * 80)

    try:
        client = get_db_client()
        mcdm_service = MCDMSafetyIndexService(client)

        # Calculate safety scores
        scores = mcdm_service.calculate_latest_safety_scores(
            bin_minutes=15, lookback_hours=24
        )

        if not scores:
            print("✗ No safety scores calculated (might be no data available)")
            return False

        print(f"✓ Calculated safety scores for {len(scores)} intersections:")
        for score in scores[:5]:  # Show first 5
            print(
                f"  - {score['intersection']}: {score['safety_score']:.2f} "
                f"(vehicles: {score['vehicle_count']}, VRUs: {score['vru_count']})"
            )

        if len(scores) > 5:
            print(f"  ... and {len(scores) - 5} more")

        return True
    except Exception as e:
        print(f"✗ MCDM calculation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_intersection_endpoint():
    """Test intersection service (what the API endpoint calls)."""
    print("\n" + "=" * 80)
    print("TEST 3: Intersection Service (API Endpoint)")
    print("=" * 80)

    try:
        intersections = get_all()

        if not intersections:
            print("✗ No intersections returned")
            return False

        print(f"✓ Retrieved {len(intersections)} intersections:")
        for intersection in intersections[:5]:  # Show first 5
            print(
                f"  - ID {intersection.intersection_id}: {intersection.intersection_name}"
            )
            print(f"    Safety Score: {intersection.safety_index:.2f}")
            print(f"    Traffic Volume: {intersection.traffic_volume}")

        if len(intersections) > 5:
            print(f"  ... and {len(intersections) - 5} more")

        return True
    except Exception as e:
        print(f"✗ Intersection endpoint test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("BACKEND MCDM INTEGRATION TEST")
    print("=" * 80)
    print("\nThis test verifies:")
    print("  1. Database connection works")
    print("  2. MCDM service can calculate safety scores")
    print("  3. Intersection endpoint returns data")
    print("=" * 80)

    results = []

    # Test 1: Database connection
    results.append(("Database Connection", test_db_connection()))

    # Test 2: MCDM calculation
    results.append(("MCDM Calculation", test_mcdm_calculation()))

    # Test 3: Intersection endpoint
    results.append(("Intersection Endpoint", test_intersection_endpoint()))

    # Cleanup
    close_db_client()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED - Backend is ready!")
    else:
        print("✗ SOME TESTS FAILED - Check errors above")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
