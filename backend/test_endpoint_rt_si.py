"""
Test the full RT-SI calculation flow for the /safety/index/ endpoint
"""

from app.services.db_client import get_db_client
from app.services.mcdm_service import MCDMSafetyIndexService
from app.services.rt_si_service import RTSIService
from app.services.intersection_service import get_all
from datetime import datetime

print("=" * 80)
print("Testing RT-SI Calculation Flow for Dashboard Endpoint")
print("=" * 80)

# Setup
db_client = get_db_client()
rt_si_service = RTSIService(db_client)
mcdm_service = MCDMSafetyIndexService(db_client)

# Step 1: Get base intersections
print("\n1. Getting base intersections from MCDM service...")
base_intersections = get_all()
print(f"   Found {len(base_intersections)} intersections")
if base_intersections:
    intersection = base_intersections[0]
    print(
        f"   First intersection: {intersection.intersection_name} (ID: {intersection.intersection_id})"
    )

# Step 2: Get available BSM intersections
print("\n2. Getting available BSM intersections...")
bsm_intersections = mcdm_service.get_available_intersections()
print(f"   Found {len(bsm_intersections)} BSM intersections")
for bsm in bsm_intersections:
    print(f"   - {bsm}")

# Step 3: Test name matching
print("\n3. Testing name matching for 'glebe-potomac'...")
intersection = base_intersections[0]
bsm_intersection_name = None

for bsm_name in bsm_intersections:
    normalized_bsm = bsm_name.lower().replace("-", "").replace(" ", "")
    normalized_intersection = (
        intersection.intersection_name.lower().replace("-", "").replace(" ", "")
    )

    print(f"   Comparing:")
    print(f"      BSM: '{bsm_name}' -> normalized: '{normalized_bsm}'")
    print(
        f"      DB:  '{intersection.intersection_name}' -> normalized: '{normalized_intersection}'"
    )
    print(f"      Match? {normalized_bsm == normalized_intersection}")

    if (
        normalized_bsm == normalized_intersection
        or normalized_bsm in normalized_intersection
    ):
        bsm_intersection_name = bsm_name
        print(f"   ✓ Matched! Using BSM intersection: {bsm_intersection_name}")
        break

if not bsm_intersection_name:
    print("   ✗ No match found!")
    exit(1)

# Step 4: Find crash intersection ID using BSM coordinates
print("\n4. Finding crash intersection ID using find_crash_intersection_for_bsm...")
from app.api.intersection import find_crash_intersection_for_bsm

intersection_list = find_crash_intersection_for_bsm(bsm_intersection_name, db_client)
if intersection_list:
    # Use first valid result
    valid_intersection = next(
        (
            item
            for item in intersection_list
            if item["crash_intersection_id"] is not None
        ),
        intersection_list[0] if intersection_list else None,
    )
    if valid_intersection:
        crash_intersection_id = valid_intersection["crash_intersection_id"]
        print(f"   ✓ Found crash intersection ID: {crash_intersection_id}")
        print(
            f"   Source: {valid_intersection['source']}, Name: {valid_intersection['intersection_name']}"
        )
    else:
        crash_intersection_id = None
        print(f"   ✗ No valid crash intersection found")
else:
    crash_intersection_id = None
    print(
        f"   ✗ Could not find crash intersection ID for BSM '{bsm_intersection_name}'"
    )

    # Debug: Check PSM data
    print("\n   Debugging PSM data...")
    psm_query = """
    SELECT 
        AVG(lat) as avg_lat,
        AVG(lon) as avg_lon,
        COUNT(*) as count
    FROM psm
    WHERE intersection = %(int_id)s
    GROUP BY intersection;
    """
    psm_results = db_client.execute_query(psm_query, {"int_id": bsm_intersection_name})
    if psm_results:
        print(
            f"   PSM data found: lat={psm_results[0]['avg_lat']}, lon={psm_results[0]['avg_lon']}, count={psm_results[0]['count']}"
        )
    else:
        print(f"   No PSM data found for '{bsm_intersection_name}'")
    exit(1)

# Step 5: Calculate RT-SI
print("\n5. Calculating RT-SI...")
current_time = datetime.now()
print(f"   Timestamp: {current_time}")
print(f"   Crash Intersection ID: {crash_intersection_id}")
print(f"   BSM Intersection Name: {bsm_intersection_name}")

try:
    rt_si_result = rt_si_service.calculate_rt_si(
        crash_intersection_id,
        current_time,
        bin_minutes=15,
        realtime_intersection=bsm_intersection_name,
        lookback_hours=168,
    )

    if rt_si_result:
        print(f"   ✓ RT-SI calculation succeeded!")
        print(f"      RT-SI: {rt_si_result['RT_SI']:.2f}")
        print(f"      COMB: {rt_si_result['combined_index']:.4f}")
        print(f"      VRU Index: {rt_si_result['VRU_index']:.4f}")
        print(f"      Vehicle Index: {rt_si_result['VEH_index']:.4f}")
        print(f"      Vehicle Count: {rt_si_result['vehicle_count']}")
        print(f"      Avg Speed: {rt_si_result['avg_speed']:.2f} mph")
    else:
        print(f"   ✗ RT-SI calculation returned None")
except Exception as e:
    print(f"   ✗ RT-SI calculation failed with error:")
    print(f"      {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
