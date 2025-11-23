# RT-SI (Real-Time Safety Index) Implementation

## Overview

This implementation creates a Real-Time Safety Index (RT-SI) based on the research methodology that combines:

- Historical severity-weighted crash rates
- Empirical Bayes stabilization
- Real-time operating factors (speed, variance, conflicts)
- VRU (Vulnerable Road Users) and vehicle sub-indices

## Files Created

### 1. `/backend/app/services/find_lambda.py`

**Purpose**: Find optimal λ (lambda) for Empirical Bayes shrinkage using cross-validation.

**What it does**:

- Uses crash data from 2017-2024 as training set
- Uses 2025 data as test set
- Evaluates λ values: [0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000]
- Computes Poisson negative log-likelihood for each λ
- Returns the optimal λ that minimizes prediction error

**How to run**:

```bash
cd /Users/ryan/PycharmProjects/cs6604-trafficsafety/backend
python3 -m app.services.find_lambda
```

### 2. `/backend/app/services/rt_si_service.py`

**Purpose**: Calculate RT-SI for intersections at specific times.

**Main Components**:

#### RT-SI Calculation Steps:

1. **Historical Crash Rate** with severity weights (Fatal=10, Injury=3, PDO=1)
2. **Empirical Bayes Stabilization** using optimal λ
3. **Real-Time Uplift Factors**:
   - F_speed: Speed reduction (congestion) factor
   - F_variance: Speed variance (inconsistency) factor
   - F_conflict: VRU-vehicle conflict factor
4. **Sub-Indices**:
   - VRU_index: Safety risk for vulnerable road users
   - VEH_index: Safety risk for vehicles
5. **Combined Index**: Weighted combination (60% VRU, 40% Vehicle)
6. **Scaled to 0-100**: Higher score = safer intersection

#### Key Parameters (configurable):

```python
# Severity weights
W_FATAL = 10.0
W_INJURY = 3.0
W_PDO = 1.0

# Scaling constants for uplift factors
K1_SPEED = 1.5     # Speed reduction factor
K2_VAR = 1.0       # Speed variance factor
K3_CONF = 0.5      # Conflict factor
K4_VRU_RATIO = 1.0 # VRU ratio factor
K5_VOL_CAPACITY = 1.0  # Volume/capacity factor

# Beta coefficients for uplift combination
BETA1 = 0.3  # Speed uplift weight
BETA2 = 0.3  # Variance uplift weight
BETA3 = 0.4  # Conflict uplift weight

# Omega: VRU vs Vehicle blend
OMEGA_VRU = 0.6  # VRU weight (policy-driven)
OMEGA_VEH = 0.4  # Vehicle weight

# Lambda and R0 (updated from find_lambda.py)
LAMBDA = 10.0  # Shrinkage parameter
R0 = 0.001     # Pooled mean rate
```

### 3. `/backend/app/services/test_rt_si.py`

**Purpose**: Test script to run both lambda optimization and RT-SI calculation.

**What it does**:

1. Runs lambda optimization
2. Updates RTSIService with optimal λ and r0
3. Tests RT-SI calculation on sample intersections
4. Displays detailed results

**How to run**:

```bash
cd /Users/ryan/PycharmProjects/cs6604-trafficsafety/backend
python3 -m app.services.test_rt_si
```

## Mathematical Formulas Implemented

### 1. Historical Severity-Weighted Crash Rate

```
r_i = Σ(w_s * C_{i,s}) / E_i
```

Where:

- C\_{i,s} = crash counts by severity s
- w_s = severity weights (Fatal=10, Injury=3, PDO=1)
- E_i = exposure (vehicle volume)

### 2. Empirical Bayes Stabilization

```
r_hat_i = α_i * r_i + (1 - α_i) * r_0
α_i = E_i / (E_i + λ)
```

Where:

- r_0 = pooled mean rate
- λ = shrinkage parameter (optimized via cross-validation)

### 3. Real-Time Uplift Factors

```
F_speed = min(1, k1 * (v_FF - v_avg) / v_FF)
F_variance = min(1, k2 * σ_v / (v_avg + ε))
F_conflict = min(1, k3 * turningVol * VRU / scale)

U = 1 + β1*F_speed + β2*F_variance + β3*F_conflict
```

### 4. Sub-Indices

```
G = min(1, k4 * VRU / (vehicles + ε))
VRU_index = γ * r_hat * U * G

H = min(1, k5 * vehicles / capacity)
VEH_index = γ * r_hat * U * H
```

### 5. Combined and Scaled Index

```
COMB = ω_vru * VRU_index + ω_veh * VEH_index
RT-SI = 100 * (COMB - min) / (max - min)
```

Note: Scale is inverted so higher RT-SI = safer

## Data Sources

### From Database Tables:

1. **vdot_crashes**: Historical crash data (2017-2025)

   - matched_intersection_id
   - crash_date, crash_time
   - severity (K=Fatal, A/B=Injury, etc.)

2. **speed_distribution**: Real-time traffic data
   - intersection_id
   - timestamp
   - volume (vehicle count)
   - vru_count (pedestrians, cyclists)
   - speed_avg
   - speed distribution percentiles

## Usage Examples

### Calculate RT-SI for a specific intersection and time:

```python
from app.services.db_client import VTTIPostgresClient
from app.services.rt_si_service import RTSIService
from datetime import datetime

db_client = VTTIPostgresClient()
service = RTSIService(db_client)

result = service.calculate_rt_si(
    intersection_id=123,
    timestamp=datetime(2024, 11, 15, 10, 0),
    bin_minutes=15
)

print(f"RT-SI Score: {result['RT_SI']:.2f}")
print(f"VRU Index: {result['VRU_index']:.6f}")
print(f"Vehicle Index: {result['VEH_index']:.6f}")
```

### Calculate RT-SI trend over time:

```python
from datetime import datetime, timedelta

start = datetime(2024, 11, 15, 8, 0)
end = datetime(2024, 11, 15, 18, 0)

results = service.calculate_rt_si_trend(
    intersection_id=123,
    start_time=start,
    end_time=end,
    bin_minutes=15
)

for r in results:
    print(f"{r['timestamp']}: RT-SI = {r['RT_SI']:.2f}")
```

## Next Steps

### 1. Run Lambda Optimization

First, ensure you have database access configured, then run:

```bash
export VTTI_DB_PASSWORD="your_password"
cd /Users/ryan/PycharmProjects/cs6604-trafficsafety/backend
python3 -m app.services.find_lambda
```

This will output the optimal λ value. Update `RTSIService.LAMBDA` and `RTSIService.R0` with the results.

### 2. Test RT-SI Calculation

```bash
python3 -m app.services.test_rt_si
```

### 3. Integrate with API

Create API endpoints in `/backend/app/api/` to expose RT-SI calculations:

- `/api/v1/rt-si/intersection/{id}` - Single time point
- `/api/v1/rt-si/trend` - Time range trend

### 4. Fine-Tune Parameters

Based on validation with actual crash/incident data:

- Adjust K1-K5 scaling constants
- Tune Beta coefficients
- Modify Omega blend ratios for different areas

### 5. Compute Proper Min/Max for Scaling

Currently using placeholder values (0.0, 0.1). Should compute from historical data distribution:

```sql
SELECT
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY combined_index) as min_val,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY combined_index) as max_val
FROM historical_rt_si_calculations;
```

## Key Differences from MCDM

| Aspect    | MCDM                           | RT-SI                     |
| --------- | ------------------------------ | ------------------------- |
| Approach  | Multi-criteria decision making | Crash-based risk modeling |
| Base      | Normalized traffic metrics     | Historical crash rates    |
| Stability | CRITIC weights                 | Empirical Bayes shrinkage |
| Methods   | SAW, EDAS, CODAS               | Single combined index     |
| Emphasis  | Real-time conditions           | Historical + real-time    |
| VRU Focus | Implicit in metrics            | Explicit VRU sub-index    |

## Troubleshooting

### Database Connection Issues

Ensure Cloud SQL Proxy is running and environment variables are set:

```bash
export VTTI_DB_HOST="127.0.0.1"
export VTTI_DB_PORT="9470"
export VTTI_DB_NAME="vtsi"
export VTTI_DB_USER="postgres"
export VTTI_DB_PASSWORD="your_password"
```

### No Training Data

If optimization fails due to no data:

1. Check that vdot_crashes table has data for 2017-2024
2. Check that matched_intersection_id is not NULL
3. Verify speed_distribution table has corresponding data

### Zero or Negative RT-SI Scores

Check scaling parameters:

- min_val and max_val in `scale_to_100()`
- Ensure combined_index is in expected range
- May need to adjust uplift factor coefficients

## References

This implementation is based on the RT-SI methodology described in the research document, combining:

- Empirical Bayes crash rate estimation
- Real-time traffic safety indicators
- Multi-exposure (VRU + Vehicle) risk assessment
- Policy-informed weight determination
