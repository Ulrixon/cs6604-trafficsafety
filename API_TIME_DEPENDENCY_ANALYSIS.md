# API Endpoint and RT-SI Time Dependency Analysis

## Analysis Results

### ✅ Issue 1: Page 0 API Endpoint Alpha Support

**Question:** Does Page 0's corresponding API endpoint accept alpha for safety score?

**Answer:** **YES, it is correctly configured.**

#### Flow Verification:

1. **Frontend (Dashboard Page 0):**

   ```python
   # pages/0_🏠_Dashboard.py
   alpha = st.slider("RT-SI Weight (α)", 0.0, 1.0, 0.7)
   raw_data, blend_error = fetch_latest_blended_scores(alpha)
   ```

2. **API Client:**

   ```python
   # app/services/api_client.py
   def fetch_latest_blended_scores(alpha: float = 0.7):
       params = {
           "intersection": intersection,
           "time": current_time.isoformat(),
           "bin_minutes": 15,
           "alpha": alpha,  # ✅ Alpha is passed
       }

       score_response = session.get(
           f"{api_base}/time/specific",  # ✅ Calls correct endpoint
           params=params,
           timeout=10
       )
   ```

3. **Backend API Endpoint:**
   ```python
   # backend/app/api/intersection.py
   @router.get("/time/specific", response_model=SafetyScoreTimePoint)
   def get_safety_score_at_time(
       intersection: str = Query(...),
       time: datetime = Query(...),
       bin_minutes: int = Query(15, ge=1, le=60),
       alpha: float = Query(  # ✅ Alpha parameter accepted
           0.7,
           description="Blending coefficient: α*RT-SI + (1-α)*MCDM",
           ge=0.0,
           le=1.0,
       ),
   ):
       # Calculate blended final safety index
       result["final_safety_index"] = (
           alpha * rt_si_result["RT_SI"] + (1 - alpha) * result["mcdm_index"]
       )
   ```

**Conclusion:** ✅ **The alpha parameter flows correctly from Dashboard UI → API Client → Backend Endpoint → Blended Calculation**

---

### ✅ Issue 2: RT-SI Uplift Factor Time Dependency

**Question:** Is RT-SI's uplift factor affected by selected time?

**Answer:** **YES, uplift factors ARE time-dependent and correctly use the selected timestamp.**

#### How RT-SI Uses Time:

1. **Historical Crash Rate (Time-based):**

   ```python
   # rt_si_service.py - calculate_rt_si()
   hour = timestamp.hour  # ✅ Uses selected time's hour
   dow = timestamp.weekday()  # ✅ Uses selected time's day of week

   hist_data = self.get_historical_crash_rate(intersection_id, hour, dow)
   ```

   - Queries crashes for the **specific hour and day of week**
   - Example: 2:00 PM on Wednesday uses crashes from 2:00 PM hour on all Wednesdays (2017-2024)

2. **Real-time Traffic Data (Time-bin specific):**

   ```python
   # rt_si_service.py - get_realtime_data()
   def get_realtime_data(self, intersection_id, timestamp: datetime, bin_minutes: int = 15):
       # Query for the specific 15-minute bin
       end_time = timestamp + timedelta(minutes=bin_minutes)

       # Convert datetime to microseconds
       start_time_us = int(timestamp.timestamp() * 1000000)  # ✅ Uses selected timestamp
       end_time_us = int(end_time.timestamp() * 1000000)

       # Query vehicle count for this specific time window
       vehicle_query = """
       SELECT SUM(count) as vehicle_count
       FROM "vehicle-count"
       WHERE intersection = %(intersection_id)s::text
         AND publish_timestamp >= %(start_time)s  # ✅ Time-filtered
         AND publish_timestamp < %(end_time)s     # ✅ Time-filtered
       """

       # Query speed distribution for this specific time window
       speed_query = """
       SELECT
           SUM(bin_count) as total_count,
           AVG(speed) as avg_speed,
           PERCENTILE_CONT(0.85) as free_flow_speed
       FROM "speed-distribution"
       WHERE intersection = %(intersection_id)s::text
         AND publish_timestamp >= %(start_time)s  # ✅ Time-filtered
         AND publish_timestamp < %(end_time)s     # ✅ Time-filtered
       """
   ```

3. **Uplift Factors (Derived from time-specific data):**
   ```python
   # rt_si_service.py - compute_uplift_factors()
   def compute_uplift_factors(
       self, avg_speed, free_flow_speed, speed_variance, vehicle_count, vru_count
   ):
       # F_speed: Based on congestion at selected time
       speed_reduction = max(0, free_flow_speed - avg_speed)
       F_speed = min(1.0, self.K1_SPEED * (speed_reduction / (free_flow_speed + epsilon)))

       # F_variance: Based on speed variance at selected time
       F_variance = min(1.0, self.K2_VAR * (sqrt(speed_variance) / (avg_speed + epsilon)))

       # F_conflict: Based on traffic at selected time
       turning_vol = vehicle_count * 0.3
       conflict_exposure = turning_vol * vru_count
       F_conflict = min(1.0, self.K3_CONF * (conflict_exposure / 1000.0))

       # Combined uplift
       U = 1.0 + BETA1 * F_speed + BETA2 * F_variance + BETA3 * F_conflict
   ```

**Conclusion:** ✅ **Uplift factors ARE time-dependent because they are calculated from:**

- Real-time vehicle counts at the selected timestamp
- Speed patterns at the selected timestamp
- Speed variance at the selected timestamp
- VRU counts at the selected timestamp

---

## Time Dependency Flow Chart

```
User selects timestamp: 2025-11-20 14:30:00
    ↓
RT-SI Calculation
    ↓
┌─────────────────────────────────────────────────────────┐
│ Historical Component (Hour/DOW based)                   │
│ ─────────────────────────────────────────────────────── │
│ • hour = 14 (2:00 PM)                                   │
│ • dow = 2 (Wednesday)                                   │
│ • Query: Crashes at hour=14, dow=2 (2017-2024)         │
│ • Result: Empirical Bayes rate for this hour/day combo │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Real-time Component (Exact time window)                 │
│ ─────────────────────────────────────────────────────── │
│ • Time window: 14:30:00 to 14:45:00 (15-min bin)       │
│ • Query vehicle-count WHERE timestamp IN [14:30-14:45] │
│ • Query speed-distribution WHERE timestamp IN [...]     │
│ • Extract: vehicle_count, avg_speed, speed_variance    │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ Uplift Factors (Calculated from real-time data)        │
│ ─────────────────────────────────────────────────────── │
│ • F_speed = f(avg_speed, free_flow_speed)              │
│   - Reflects congestion at 14:30-14:45                 │
│ • F_variance = f(speed_variance, avg_speed)            │
│   - Reflects erratic driving at 14:30-14:45            │
│ • F_conflict = f(vehicle_count, vru_count)             │
│   - Reflects traffic exposure at 14:30-14:45           │
│ • U = 1 + β1*F_speed + β2*F_variance + β3*F_conflict   │
└─────────────────────────────────────────────────────────┘
    ↓
Final RT-SI = scale(Combined_Index)
  where Combined_Index = γ * r_hat * U * (G + H)
```

---

## Example: Time Effects on RT-SI

### Scenario: Same intersection, different times

**Morning Rush (8:00 AM):**

```
timestamp = 2025-11-20 08:00:00
├─ Historical: hour=8, dow=2 → r_hat = 3.5 (higher crash history)
├─ Real-time:
│  ├─ vehicle_count = 250 (heavy traffic)
│  ├─ avg_speed = 12 mph (severe congestion)
│  ├─ free_flow_speed = 45 mph
│  └─ speed_variance = 25 (erratic)
├─ Uplift Factors:
│  ├─ F_speed = 0.73 (high - severe congestion)
│  ├─ F_variance = 0.42 (high - erratic driving)
│  └─ U = 1.45 (high uplift)
└─ RT-SI = 45.2 (LOWER safety - more dangerous)
```

**Late Night (2:00 AM):**

```
timestamp = 2025-11-20 02:00:00
├─ Historical: hour=2, dow=2 → r_hat = 1.2 (lower crash history)
├─ Real-time:
│  ├─ vehicle_count = 15 (light traffic)
│  ├─ avg_speed = 42 mph (near free-flow)
│  ├─ free_flow_speed = 45 mph
│  └─ speed_variance = 3 (smooth)
├─ Uplift Factors:
│  ├─ F_speed = 0.07 (low - minimal congestion)
│  ├─ F_variance = 0.04 (low - smooth flow)
│  └─ U = 1.03 (low uplift)
└─ RT-SI = 82.5 (HIGHER safety - less dangerous)
```

---

## Verification Checklist

- [x] ✅ Alpha parameter accepted by `/time/specific` endpoint
- [x] ✅ Alpha parameter flows from Dashboard UI to backend
- [x] ✅ Blended calculation uses alpha: `Final = α*RT-SI + (1-α)*MCDM`
- [x] ✅ RT-SI uses timestamp.hour for historical crash lookup
- [x] ✅ RT-SI uses timestamp.weekday() for day-of-week patterns
- [x] ✅ Real-time data queries filtered by exact timestamp window
- [x] ✅ Uplift factors calculated from time-specific traffic data
- [x] ✅ Different timestamps produce different RT-SI scores

---

## Conclusion

Both systems are **correctly implemented**:

1. **Alpha Support:** Page 0 Dashboard fully supports alpha blending through the `/time/specific` API endpoint
2. **Time Dependency:** RT-SI uplift factors are properly time-dependent, using:
   - Historical patterns by hour/day-of-week
   - Real-time traffic data from the specific time window
   - Dynamically calculated uplift factors based on current conditions

The RT-SI system accurately reflects "real-time" safety by incorporating actual traffic conditions at the selected timestamp, making it suitable for both:

- **Current monitoring** (using `datetime.now()`)
- **Historical analysis** (using past timestamps to understand what safety conditions were like at that time)
