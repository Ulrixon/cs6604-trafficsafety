#!/usr/bin/env python3
"""
Diagnose why RT-SI is not available for November 1, 2025 10:00 AM
"""

from datetime import datetime
from app.services.db_client import VTTIPostgresClient
from app.services.rt_si_service import RTSIService


def check_rt_si_availability():
    """Check data availability for RT-SI calculation"""

    db = VTTIPostgresClient()
    rt_si_service = RTSIService(db)

    # Target time
    target_time = datetime(2025, 11, 1, 10, 0, 0)
    bsm_intersection = "glebe-potomac"
    crash_intersection_id = 1014356  # From previous tests

    print("=" * 70)
    print("RT-SI AVAILABILITY DIAGNOSTIC")
    print("=" * 70)
    print(f"Target Time: {target_time}")
    print(f"BSM Intersection: {bsm_intersection}")
    print(f"Crash Intersection ID: {crash_intersection_id}")
    print()

    # Check 1: Historical crash data
    print("1. HISTORICAL CRASH DATA")
    print("-" * 70)
    hour = target_time.hour
    dow = target_time.weekday()
    print(f"   Hour: {hour}, Day of Week: {dow} (0=Mon)")

    hist_data = rt_si_service.get_historical_crash_rate(
        crash_intersection_id, hour, dow
    )
    print(f"   Weighted crashes: {hist_data['weighted_crashes']}")
    print(f"   Raw crash rate: {hist_data['raw_rate']:.6f}")
    print(f"   ✓ Historical data available")
    print()

    # Check 2: Real-time traffic data
    print("2. REAL-TIME TRAFFIC DATA")
    print("-" * 70)

    # Convert to microseconds
    start_us = int(target_time.timestamp() * 1000000)
    end_us = int(
        (target_time.replace(hour=target_time.hour, minute=15)).timestamp() * 1000000
    )

    print(f"   Time window: {target_time} to {target_time.replace(minute=15)}")
    print(f"   Timestamp (μs): {start_us} to {end_us}")
    print()

    # Check vehicle-count
    print("   a) Vehicle Count:")
    vc_query = """
    SELECT 
        COUNT(*) as record_count,
        SUM(count) as total_vehicles
    FROM "vehicle-count"
    WHERE intersection = %s
      AND publish_timestamp >= %s
      AND publish_timestamp < %s;
    """
    vc_result = db.execute_query(vc_query, (bsm_intersection, start_us, end_us))

    if vc_result and vc_result[0]["record_count"]:
        print(f"      Records: {vc_result[0]['record_count']}")
        print(f"      Total vehicles: {vc_result[0]['total_vehicles']}")
        print(f"      ✓ Vehicle count data available")
    else:
        print(f"      ✗ NO vehicle count data found!")
        print(f"      This is why RT-SI fails!")
    print()

    # Check speed-distribution
    print("   b) Speed Distribution:")
    sd_query = """
    SELECT 
        COUNT(*) as record_count,
        COUNT(DISTINCT speed_interval) as speed_bins
    FROM "speed-distribution"
    WHERE intersection = %s
      AND publish_timestamp >= %s
      AND publish_timestamp < %s;
    """
    sd_result = db.execute_query(sd_query, (bsm_intersection, start_us, end_us))

    if sd_result and sd_result[0]["record_count"]:
        print(f"      Records: {sd_result[0]['record_count']}")
        print(f"      Speed bins: {sd_result[0]['speed_bins']}")
        print(f"      ✓ Speed data available")
    else:
        print(f"      ✗ NO speed distribution data found!")
    print()

    # Check 3: Try actual RT-SI calculation
    print("3. RT-SI CALCULATION TEST")
    print("-" * 70)

    try:
        result = rt_si_service.calculate_rt_si(
            crash_intersection_id,
            target_time,
            bin_minutes=15,
            realtime_intersection=bsm_intersection,
        )

        if result:
            print(f"   ✓ RT-SI calculated successfully!")
            print(f"   RT-SI Score: {result['RT_SI']:.2f}")
            print(f"   Vehicle count: {result['vehicle_count']}")
            print(f"   Avg speed: {result['avg_speed']:.1f} mph")
        else:
            print(f"   ✗ RT-SI returned None")
            print(f"   Reason: No traffic data (vehicle_count=0 and vru_count=0)")
    except Exception as e:
        print(f"   ✗ RT-SI calculation failed!")
        print(f"   Error: {str(e)}")
    print()

    # Check 4: Find available data range
    print("4. AVAILABLE DATA RANGE")
    print("-" * 70)

    range_query = """
    SELECT 
        MIN(publish_timestamp) as min_ts,
        MAX(publish_timestamp) as max_ts
    FROM "vehicle-count"
    WHERE intersection = %s;
    """
    range_result = db.execute_query(range_query, (bsm_intersection,))

    if range_result and range_result[0]["min_ts"]:
        min_dt = datetime.fromtimestamp(range_result[0]["min_ts"] / 1000000)
        max_dt = datetime.fromtimestamp(range_result[0]["max_ts"] / 1000000)
        print(f"   Data range: {min_dt} to {max_dt}")
        print()

        # Check if target time is in range
        if target_time < min_dt:
            print(f"   ⚠️  Target time is BEFORE data range starts!")
            print(f"   Target: {target_time}")
            print(f"   Earliest data: {min_dt}")
            print(f"   Difference: {(min_dt - target_time).days} days")
        elif target_time > max_dt:
            print(f"   ⚠️  Target time is AFTER data range ends!")
            print(f"   Target: {target_time}")
            print(f"   Latest data: {max_dt}")
            print(f"   Difference: {(target_time - max_dt).days} days")
        else:
            print(f"   ✓ Target time is within data range")
            print(f"   But no data found for this specific time window!")
    else:
        print(f"   ✗ No data found for intersection {bsm_intersection}")

    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if vc_result and vc_result[0]["record_count"]:
        print("RT-SI should be available - data exists for this time.")
    else:
        print("RT-SI NOT AVAILABLE - No real-time traffic data for this time window.")
        print("\nPossible reasons:")
        print("1. Data hasn't been collected yet for Nov 1, 2025")
        print("2. Data collection started after this date")
        print("3. Gap in data collection during this period")
        print("\nSuggestion: Use a time within the available data range")

    db.close()


if __name__ == "__main__":
    check_rt_si_availability()
