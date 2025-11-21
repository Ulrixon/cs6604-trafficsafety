"""
Index computation service - Phases 5-7: Normalization, Index Computation, Empirical Bayes
Computes VRU, Vehicle, and Combined Safety Indices from master feature table
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np


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


def compute_safety_indices(master_features: pd.DataFrame, norm_constants: Dict[str, float]) -> pd.DataFrame:
    """
    Phase 6: Compute VRU, Vehicle, and Combined Safety Indices.

    Formulas from checkpoint document:
    - VRU Index = 100 × [0.4×(I_VRU/I_max) + 0.2×(V/V_max) + 0.2×(S/S_ref) + 0.2×(σ_S/σ_max)]
    - Vehicle Index = 100 × [0.3×(I_vehicle/I_max) + 0.3×(V/V_max) + 0.2×(σ_S/σ_max) + 0.2×(hard_braking)]
    - Combined Index = 0.6×VRU_Index + 0.4×Vehicle_Index

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

    # ========== Combined Safety Index ==========
    df['Combined_Index'] = (0.6 * df['VRU_Index'] + 0.4 * df['Vehicle_Index'])
    df['Combined_Index'] = df['Combined_Index'].clip(0, 100)

    print(f"✓ Safety indices computed for {len(df)} intervals")

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
