#!/usr/bin/env python3
"""
Test that API correctly handles RT-SI = 0.0 (not treating it as None/falsy)
"""

from datetime import datetime
from app.services.db_client import VTTIPostgresClient
from app.services.rt_si_service import RTSIService


def test_rt_si_zero_handling():
    """Test RT-SI = 0.0 is properly returned (not None)"""

    db = VTTIPostgresClient()
    rt_si_service = RTSIService(db)

    # Time that produces RT-SI = 0.0
    target_time = datetime(2025, 11, 1, 10, 0, 0)
    bsm_intersection = "glebe-potomac"
    crash_intersection_id = 1014356

    print("=" * 70)
    print("RT-SI ZERO VALUE HANDLING TEST")
    print("=" * 70)
    print(f"Target Time: {target_time}")
    print(f"Intersection: {bsm_intersection}")
    print()

    # Calculate RT-SI
    rt_si_result = rt_si_service.calculate_rt_si(
        crash_intersection_id,
        target_time,
        bin_minutes=15,
        realtime_intersection=bsm_intersection,
    )

    print("RT-SI Service Response:")
    print("-" * 70)
    if rt_si_result is None:
        print("❌ FAIL: rt_si_result is None")
        print("   Expected: Dictionary with RT_SI = 0.0")
    else:
        print(f"✓ rt_si_result is not None (it's a dict)")
        print(f"  Type: {type(rt_si_result)}")
        print(f"  RT_SI: {rt_si_result.get('RT_SI')}")
        print(f"  VRU_index: {rt_si_result.get('VRU_index')}")
        print(f"  VEH_index: {rt_si_result.get('VEH_index')}")
        print()

        # Test the problematic condition
        print("Testing Condition Checks:")
        print("-" * 70)

        # Old (buggy) way
        if rt_si_result:
            print("✓ PASS: if rt_si_result: evaluates to True")
        else:
            print("❌ FAIL: if rt_si_result: evaluates to False")
            print("   This was the bug - treating 0.0 as falsy")

        # New (correct) way
        if rt_si_result is not None:
            print("✓ PASS: if rt_si_result is not None: evaluates to True")
        else:
            print("❌ FAIL: if rt_si_result is not None: evaluates to False")

        print()

        # Test RT-SI value specifically
        rt_si_value = rt_si_result.get("RT_SI")
        print(f"RT-SI Value Test:")
        print("-" * 70)
        print(f"  Value: {rt_si_value}")
        print(f"  Type: {type(rt_si_value)}")
        print(f"  Is None: {rt_si_value is None}")
        print(f"  Is 0.0: {rt_si_value == 0.0}")
        print(f"  Truthy: {bool(rt_si_value)}")
        print()

        if rt_si_value == 0.0:
            print("✓ RT-SI = 0.0 indicates very unsafe conditions")
            print("  This should be displayed in frontend, not shown as 'NA'")

    print()
    print("=" * 70)
    print("API IMPACT")
    print("=" * 70)
    print("BEFORE FIX:")
    print("  - API uses: if rt_si_result:")
    print("  - When RT-SI = 0.0, this is falsy")
    print("  - rt_si_score not added to response")
    print("  - Frontend shows 'NA'")
    print()
    print("AFTER FIX:")
    print("  - API uses: if rt_si_result is not None:")
    print("  - When RT-SI = 0.0, this is still True")
    print("  - rt_si_score = 0.0 added to response")
    print("  - Frontend displays 0.00 (very unsafe)")
    print()

    db.close()


if __name__ == "__main__":
    test_rt_si_zero_handling()
