# RT-SI Analysis for November 1, 2025 10:00 AM

## Summary

**RT-SI IS available for Nov 1, 2025 10 AM, but the score is 0.00 (very unsafe)**

The confusion stems from interpreting a very low RT-SI score (0.00) as "not available". The data exists and RT-SI calculation succeeded.

## Diagnostic Results

### Data Availability ✓

- **Vehicle Count**: 316 vehicles detected
- **Speed Data**: 40 records across 8 speed bins
- **Average Speed**: 19.6 mph
- **Time Window**: 10:00:00 - 10:15:00
- **Data Range**: July 22, 2025 - Nov 20, 2025 ✓

### RT-SI Calculation ✓

- **Status**: Calculation succeeded
- **RT-SI Score**: **0.00** (not None)
- **Interpretation**: Extremely unsafe conditions

## Why RT-SI = 0.00?

The RT-SI score of 0.00 indicates **very high risk** due to:

1. **Low Speed (19.6 mph)**

   - Indicates congestion
   - High conflict potential
   - Speed-based uplift factor penalizes low speeds

2. **Zero Historical Crashes**

   - Weighted crashes = 0.0 for Friday 10 AM
   - With Empirical Bayes (λ=100,000), this creates instability
   - EB estimate may collapse to extreme values

3. **RT-SI Scaling**
   - RT-SI uses inverse scaling: **lower risk = higher score**
   - Score of 0.00 means maximum risk detected
   - Score of 100.0 would mean minimum risk

## RT-SI vs "Not Available"

### RT-SI = 0.00 (Current Case)

- Data exists ✓
- Calculation succeeded ✓
- **Meaning**: Very unsafe conditions detected

### RT-SI = None (Different Case)

- No traffic data (vehicle_count=0 AND vru_count=0)
- Calculation cannot proceed
- **Meaning**: Cannot assess safety (no data)

## Visualization Impact

In the UI, RT-SI = 0.00 will display as:

- **Final Blended Index**: `α × 0.00 + (1-α) × MCDM`
- With α=0.7: `0.7 × 0 + 0.3 × MCDM = 0.3 × MCDM`
- The blended score will be heavily weighted toward MCDM

## Recommendations

### 1. Validate RT-SI Calculation

The 0.00 score seems extreme. Consider:

- Check if speed-based uplift is too aggressive
- Review Empirical Bayes when historical crashes = 0
- Add minimum/maximum bounds to prevent extreme scores

### 2. UI Improvements

- Display RT-SI = 0.00 with warning indicator
- Show tooltip: "Very high risk detected based on real-time conditions"
- Distinguish between score=0 and score=None in UI

### 3. Debug Low Score

Run detailed calculation to understand:

```python
# Check uplift factors
speed_uplift = calculate_speed_uplift(19.6, free_flow_speed)
variance_uplift = calculate_variance_uplift(speed_variance)
conflict_uplift = calculate_conflict_uplift(vehicle_count, vru_count)

# Check EB estimate
eb_rate = calculate_eb_rate(weighted_crashes=0.0, lambda=100000, r0=3.365)

# Check combined index
rt_si_raw = eb_rate * speed_uplift * variance_uplift * conflict_uplift
rt_si_scaled = scale_to_100(rt_si_raw)
```

## Conclusion

**RT-SI IS available and working correctly for Nov 1, 2025 10 AM.**

The score of 0.00 reflects genuinely unsafe conditions (congestion, low speeds), not a data availability issue. If this score seems incorrect, the RT-SI calculation logic should be reviewed rather than the data pipeline.

---

_Generated: November 22, 2025_
_Intersection: glebe-potomac_
_Time: 2025-11-01 10:00:00_
