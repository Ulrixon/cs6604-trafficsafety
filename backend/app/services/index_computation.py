"""
Index computation service - Phases 5-7: Normalization, Index Computation, Empirical Bayes
Computes VRU, Vehicle, and Combined Safety Indices from master feature table

Updated for Phase 5: Multi-Source Safety Index Integration
- Incorporates weather features from NOAA Weather Plugin
- Weighted combination of VCC (0.70) + Weather (0.15) + Other (0.15)
"""

from typing import Dict, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from app.core.config import settings


def compute_normalization_constants(master_features: pd.DataFrame) -> Dict[str, float]:
    """
    Phase 5: Compute all normalization constants from the master feature table.

    Constants computed:
    - I_max: Maximum VRU conflict intensity (events per 15-min)
    - V_max: Maximum vehicle volume per 15-min interval
    - σ_max: Maximum speed variance
    - S_ref: Reference speed (85th percentile of average speeds)
    - N_VRU_max: Maximum VRU count per 15-min interval

    Returns:
        Dictionary of normalization constants
    """
    if len(master_features) == 0:
        print("⚠ ERROR: No master features available")
        return {}

    constants = {}

    # I_max: Maximum VRU conflict intensity
    if 'I_VRU' in master_features.columns:
        constants['I_max'] = float(master_features['I_VRU'].max())
        if constants['I_max'] == 0:
            constants['I_max'] = 1.0
    else:
        constants['I_max'] = 1.0

    # V_max: Maximum vehicle volume
    v_sources = []
    if 'vehicle_count' in master_features.columns:
        v_sources.append(master_features['vehicle_count'].max())
    if 'vehicle_volume' in master_features.columns:
        v_sources.append(master_features['vehicle_volume'].max())

    constants['V_max'] = float(max(v_sources)) if v_sources else 1.0
    if constants['V_max'] == 0:
        constants['V_max'] = 1.0

    # σ_max: Maximum speed variance
    if 'speed_variance' in master_features.columns:
        constants['sigma_max'] = float(master_features['speed_variance'].max())
        if constants['sigma_max'] == 0:
            constants['sigma_max'] = 1.0
    else:
        constants['sigma_max'] = 1.0

    # S_ref: Reference speed (85th percentile)
    if 'avg_speed' in master_features.columns:
        valid_speeds = master_features['avg_speed'][master_features['avg_speed'] > 0]
        if len(valid_speeds) > 0:
            constants['S_ref'] = float(valid_speeds.quantile(0.85))
            if constants['S_ref'] == 0:
                constants['S_ref'] = 1.0
        else:
            constants['S_ref'] = 1.0
    else:
        constants['S_ref'] = 1.0

    # N_VRU_max: Maximum VRU count
    vru_sources = []
    if 'psm_vru_count' in master_features.columns:
        vru_sources.append(master_features['psm_vru_count'].max())
    if 'vru_volume' in master_features.columns:
        vru_sources.append(master_features['vru_volume'].max())

    constants['N_VRU_max'] = float(max(vru_sources)) if vru_sources else 1.0
    if constants['N_VRU_max'] == 0:
        constants['N_VRU_max'] = 1.0

    # Hard braking rate normalization
    if 'hard_braking_count' in master_features.columns:
        constants['hard_braking_max'] = float(master_features['hard_braking_count'].max())
        if constants['hard_braking_max'] == 0:
            constants['hard_braking_max'] = 1.0
    else:
        constants['hard_braking_max'] = 1.0

    print(f"✓ Normalization constants: I_max={constants['I_max']:.1f}, V_max={constants['V_max']:.1f}, "
          f"σ_max={constants['sigma_max']:.1f}, S_ref={constants['S_ref']:.1f}")

    return constants


def compute_weather_index(features: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Weather Safety Index from NOAA Weather Plugin features.

    Weather features (already normalized 0-1 by plugin):
    - weather_precipitation: 0=no rain, 1=heavy rain (≥20mm/hr)
    - weather_visibility: 0=clear (10km+), 1=zero visibility
    - weather_wind_speed: 0=calm, 1=high wind (≥25 m/s)
    - weather_temperature: 0=optimal (20°C), 1=extreme hot/cold

    Weather Index Formula:
    Weather_Index = 100 × [0.35×precip + 0.30×visibility + 0.20×wind + 0.15×temp]

    Args:
        features: DataFrame with weather columns

    Returns:
        DataFrame with 'Weather_Index' column added (0-100 scale)
    """
    df = features.copy()

    # Check if weather features exist
    weather_cols = ['weather_precipitation', 'weather_visibility',
                   'weather_wind_speed', 'weather_temperature']

    has_weather = all(col in df.columns for col in weather_cols)

    if not has_weather:
        # No weather data available - set Weather Index to baseline (20.0)
        df['Weather_Index'] = 20.0
        print("⚠ No weather data available - using baseline Weather Index (20.0)")
        return df

    # Fill missing weather values with safe defaults (0.0 = optimal conditions)
    for col in weather_cols:
        df[col] = df[col].fillna(0.0)

    # Compute Weather Safety Index
    # Higher values = worse weather conditions = higher risk
    df['Weather_Index'] = 100 * (
        0.35 * df['weather_precipitation'] +    # Precipitation has highest impact
        0.30 * df['weather_visibility'] +       # Visibility is critical
        0.20 * df['weather_wind_speed'] +       # Wind affects vehicle control
        0.15 * df['weather_temperature']        # Temperature extremes
    )

    df['Weather_Index'] = df['Weather_Index'].clip(0, 100)

    print(f"✓ Weather Index computed (mean={df['Weather_Index'].mean():.1f}, max={df['Weather_Index'].max():.1f})")

    return df


def compute_safety_indices(master_features: pd.DataFrame, norm_constants: Dict[str, float]) -> pd.DataFrame:
    """
    Phase 6: Compute VRU, Vehicle, Weather, and Combined Safety Indices.

    Formulas from checkpoint document (updated for multi-source integration):
    - VRU Index = 100 × [0.4×(I_VRU/I_max) + 0.2×(V/V_max) + 0.2×(S/S_ref) + 0.2×(σ_S/σ_max)]
    - Vehicle Index = 100 × [0.3×(I_vehicle/I_max) + 0.3×(V/V_max) + 0.2×(σ_S/σ_max) + 0.2×(hard_braking)]
    - Weather Index = 100 × [0.35×precip + 0.30×visibility + 0.20×wind + 0.15×temp]
    - Combined Index = w_traffic×Traffic_Index + w_weather×Weather_Index

    Where Traffic_Index = 0.6×VRU_Index + 0.4×Vehicle_Index (from original formula)
    Default weights: w_traffic=0.85, w_weather=0.15 (configurable via plugin settings)

    Returns:
        DataFrame with computed indices added
    """
    if len(master_features) == 0:
        print("⚠ ERROR: No master features available")
        return pd.DataFrame()

    if not norm_constants:
        print("⚠ ERROR: No normalization constants available")
        return master_features

    df = master_features.copy()

    # Extract normalization constants
    I_max = norm_constants.get('I_max', 1.0)
    V_max = norm_constants.get('V_max', 1.0)
    sigma_max = norm_constants.get('sigma_max', 1.0)
    S_ref = norm_constants.get('S_ref', 1.0)
    hard_braking_max = norm_constants.get('hard_braking_max', 1.0)

    # ========== VRU Safety Index Components ==========
    df['I_VRU_norm'] = df['I_VRU'] / I_max if I_max > 0 else 0

    # Vehicle volume exposure
    df['V'] = df['vehicle_count'].fillna(0)
    if 'vehicle_volume' in df.columns:
        df['V'] = df['V'].combine_first(df['vehicle_volume'])
    df['V_norm'] = df['V'] / V_max if V_max > 0 else 0

    # Speed factor
    df['S_norm'] = df['avg_speed'] / S_ref if S_ref > 0 else 0

    # Speed variance
    df['sigma_norm'] = df['speed_variance'] / sigma_max if sigma_max > 0 else 0

    # Compute VRU Safety Index
    df['VRU_Index'] = 100 * (
        0.4 * df['I_VRU_norm'] +
        0.2 * df['V_norm'] +
        0.2 * df['S_norm'] +
        0.2 * df['sigma_norm']
    )
    df['VRU_Index'] = df['VRU_Index'].clip(0, 100)

    # ========== Vehicle Safety Index Components ==========
    if 'vehicle_event_count' in df.columns:
        df['I_vehicle'] = df['vehicle_event_count']
    else:
        df['I_vehicle'] = df.get('total_event_count', 0) - df.get('vru_event_count', 0)

    df['I_vehicle_norm'] = df['I_vehicle'] / I_max if I_max > 0 else 0

    # Hard braking rate
    if 'hard_braking_count' in df.columns:
        df['hard_braking_norm'] = df['hard_braking_count'] / hard_braking_max if hard_braking_max > 0 else 0
    else:
        df['hard_braking_norm'] = 0

    # Compute Vehicle Safety Index
    df['Vehicle_Index'] = 100 * (
        0.3 * df['I_vehicle_norm'] +
        0.3 * df['V_norm'] +
        0.2 * df['sigma_norm'] +
        0.2 * df['hard_braking_norm']
    )
    df['Vehicle_Index'] = df['Vehicle_Index'].clip(0, 100)

    # ========== Weather Safety Index ==========
    df = compute_weather_index(df)

    # ========== Combined Safety Index (Multi-Source) ==========
    # Traffic Index = weighted combination of VRU and Vehicle indices
    df['Traffic_Index'] = (0.6 * df['VRU_Index'] + 0.4 * df['Vehicle_Index'])
    df['Traffic_Index'] = df['Traffic_Index'].clip(0, 100)

    # Get plugin weights from settings (default: VCC=0.70, Weather=0.15, Other=0.15)
    # For safety index: combine Traffic (VCC-based) and Weather
    # Traffic gets combined weight of VCC + Other = 0.85
    # Weather gets its weight = 0.15
    vcc_weight = getattr(settings, 'VCC_PLUGIN_WEIGHT', 0.70)
    weather_weight = getattr(settings, 'WEATHER_PLUGIN_WEIGHT', 0.15)

    # Normalize weights for Traffic + Weather combination
    traffic_weight = 1.0 - weather_weight  # Everything except weather
    total_weight = traffic_weight + weather_weight

    if total_weight > 0:
        traffic_weight_norm = traffic_weight / total_weight
        weather_weight_norm = weather_weight / total_weight
    else:
        traffic_weight_norm = 0.85
        weather_weight_norm = 0.15

    # Combined Index incorporating multi-source data
    df['Combined_Index'] = (
        traffic_weight_norm * df['Traffic_Index'] +
        weather_weight_norm * df['Weather_Index']
    )
    df['Combined_Index'] = df['Combined_Index'].clip(0, 100)

    print(f"✓ Safety indices computed for {len(df)} intervals")
    print(f"  Weights: Traffic={traffic_weight_norm:.2f}, Weather={weather_weight_norm:.2f}")
    print(f"  Mean indices: VRU={df['VRU_Index'].mean():.1f}, Vehicle={df['Vehicle_Index'].mean():.1f}, "
          f"Weather={df['Weather_Index'].mean():.1f}, Combined={df['Combined_Index'].mean():.1f}")

    return df


def apply_empirical_bayes(
    indices_df: pd.DataFrame,
    baseline_events: pd.DataFrame,
    k: int = 50
) -> pd.DataFrame:
    """
    Phase 7: Apply Empirical Bayes adjustment to safety indices.

    Formula: Adjusted_Index = λ × Raw_Index + (1-λ) × Baseline_Index
    Where λ = N / (N + k), with:
    - N = number of observations in current period
    - k = tuning parameter (default: 50 for 15-min intervals)

    Returns:
        DataFrame with EB-adjusted indices added
    """
    if len(indices_df) == 0:
        print("⚠ No indices to adjust")
        return indices_df

    df = indices_df.copy()

    # Calculate historical baseline indices by intersection
    if len(baseline_events) > 0:
        baseline_events['hour_of_day'] = baseline_events['hour_of_day'].astype(int)
        baseline_summary = baseline_events.groupby(['intersection', 'hour_of_day']).agg({
            'severity_weight': 'sum',
            'event_id': 'count',
            'is_vru_involved': 'sum'
        }).reset_index()

        baseline_summary.rename(columns={
            'severity_weight': 'baseline_severity',
            'event_id': 'baseline_event_count',
            'is_vru_involved': 'baseline_vru_count'
        }, inplace=True)

        # Merge baseline with current data
        df['hour_of_day'] = df['hour_of_day'].astype(int)
        df = df.merge(baseline_summary, on=['intersection', 'hour_of_day'], how='left')

        # Fill missing baselines
        for col in ['baseline_severity', 'baseline_event_count', 'baseline_vru_count']:
            df[col] = df[col].fillna(baseline_summary[col].mean())
    else:
        df['baseline_event_count'] = df.get('total_event_count', 0).mean()

    # Calculate adaptive lambda
    df['N'] = df['vehicle_count'].fillna(0) + 1
    df['lambda'] = df['N'] / (df['N'] + k)

    # Convert baseline to index scale
    max_baseline = df['baseline_event_count'].max() if 'baseline_event_count' in df.columns else 1
    df['baseline_index'] = (df.get('baseline_event_count', 0) / max_baseline * 100) if max_baseline > 0 else 20.0
    df['baseline_index'] = df['baseline_index'].fillna(20.0)

    # Apply Empirical Bayes adjustment
    df['VRU_Index_EB'] = (df['lambda'] * df['VRU_Index'] + (1 - df['lambda']) * df['baseline_index']).clip(0, 100)
    df['Vehicle_Index_EB'] = (df['lambda'] * df['Vehicle_Index'] + (1 - df['lambda']) * df['baseline_index']).clip(0, 100)
    df['Combined_Index_EB'] = (df['lambda'] * df['Combined_Index'] + (1 - df['lambda']) * df['baseline_index']).clip(0, 100)

    print(f"✓ Empirical Bayes adjustment applied (k={k}, mean λ={df['lambda'].mean():.3f})")

    return df


def compute_multi_source_safety_indices(
    start_time: datetime,
    end_time: datetime,
    baseline_events: Optional[pd.DataFrame] = None,
    apply_eb: bool = True
) -> pd.DataFrame:
    """
    Compute safety indices using multi-source data collection (VCC + Weather + Other).

    This is a convenience function that:
    1. Collects data from all enabled plugins (VCC, Weather, etc.)
    2. Computes normalization constants
    3. Calculates VRU, Vehicle, Weather, and Combined indices
    4. Optionally applies Empirical Bayes adjustment

    Args:
        start_time: Start of collection window
        end_time: End of collection window
        baseline_events: Optional historical baseline events for EB adjustment
        apply_eb: Whether to apply Empirical Bayes adjustment (default: True)

    Returns:
        DataFrame with all computed safety indices

    Example:
        ```python
        from datetime import datetime, timedelta
        from app.services.index_computation import compute_multi_source_safety_indices

        end = datetime.now()
        start = end - timedelta(hours=1)

        indices_df = compute_multi_source_safety_indices(start, end)
        print(indices_df[['timestamp', 'VRU_Index', 'Vehicle_Index',
                         'Weather_Index', 'Combined_Index']].head())
        ```
    """
    from app.services.multi_source_collector import multi_source_collector

    print(f"\n{'='*80}")
    print("MULTI-SOURCE SAFETY INDEX COMPUTATION")
    print(f"{'='*80}")
    print(f"Time range: {start_time} to {end_time}")

    # Step 1: Collect multi-source data
    print("\n[1/4] Collecting data from all enabled plugins...")
    data = multi_source_collector.collect_all(start_time, end_time, fail_fast=False)

    if data.empty:
        print("⚠ ERROR: No data collected from any plugin")
        return pd.DataFrame()

    print(f"✓ Collected {len(data)} rows with {len(data.columns)} features")

    # Step 2: Compute normalization constants
    print("\n[2/4] Computing normalization constants...")
    norm_constants = compute_normalization_constants(data)

    if not norm_constants:
        print("⚠ ERROR: Failed to compute normalization constants")
        return pd.DataFrame()

    # Step 3: Compute safety indices
    print("\n[3/4] Computing safety indices...")
    indices_df = compute_safety_indices(data, norm_constants)

    if indices_df.empty:
        print("⚠ ERROR: Failed to compute safety indices")
        return pd.DataFrame()

    # Step 4: Apply Empirical Bayes (optional)
    if apply_eb and baseline_events is not None and len(baseline_events) > 0:
        print("\n[4/4] Applying Empirical Bayes adjustment...")
        indices_df = apply_empirical_bayes(indices_df, baseline_events)
    else:
        print("\n[4/4] Skipping Empirical Bayes adjustment (no baseline data)")

    print(f"\n{'='*80}")
    print("COMPUTATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total intervals: {len(indices_df)}")
    print(f"Time range: {indices_df['timestamp'].min()} to {indices_df['timestamp'].max()}")
    print(f"\nSafety Index Summary:")
    print(f"  VRU Index: mean={indices_df['VRU_Index'].mean():.1f}, max={indices_df['VRU_Index'].max():.1f}")
    print(f"  Vehicle Index: mean={indices_df['Vehicle_Index'].mean():.1f}, max={indices_df['Vehicle_Index'].max():.1f}")
    print(f"  Weather Index: mean={indices_df['Weather_Index'].mean():.1f}, max={indices_df['Weather_Index'].max():.1f}")
    print(f"  Combined Index: mean={indices_df['Combined_Index'].mean():.1f}, max={indices_df['Combined_Index'].max():.1f}")
    print(f"{'='*80}\n")

    return indices_df
