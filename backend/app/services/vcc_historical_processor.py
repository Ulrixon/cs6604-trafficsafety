"""
VCC historical processor for batch processing historical data.

Processes all collected VCC API data, computes features and indices,
and saves to Parquet storage for historical baseline computation.
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from .vcc_data_collection import collect_historical_vcc_data
from .vcc_feature_engineering import (
    extract_bsm_features, extract_psm_features,
    detect_vru_vehicle_conflicts, detect_vehicle_vehicle_conflicts
)
from .parquet_storage import parquet_storage
from .index_computation import (
    compute_normalization_constants,
    compute_safety_indices,
    apply_empirical_bayes
)
from .data_collection import collect_baseline_events
from ..core.config import settings


def process_historical_vcc_data(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    intersection_id: Optional[int] = None,
    save_to_parquet: bool = True
) -> Dict:
    """
    Process all historical VCC API data and compute safety indices.
    
    This function:
    1. Collects all available historical data from VCC API
    2. Extracts features at 15-minute intervals
    3. Computes normalization constants from full dataset
    4. Computes safety indices for each 15-minute interval
    5. Applies Empirical Bayes adjustment
    6. Saves to Parquet storage
    
    Args:
        start_date: Start date for processing (optional)
        end_date: End date for processing (optional)
        intersection_id: Optional intersection ID filter
        save_to_parquet: If True, save results to Parquet files
        
    Returns:
        Dictionary with processing results and statistics
    """
    print(f"\n{'='*80}")
    print("VCC HISTORICAL DATA PROCESSING")
    print(f"{'='*80}")
    
    # Determine date range
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=settings.DEFAULT_LOOKBACK_DAYS)
    
    print(f"\nDate range: {start_date.date()} to {end_date.date()}")
    
    # Step 1: Collect historical data
    print("\n[Step 1/6] Collecting historical data from VCC API...")
    bsm_messages, psm_messages, mapdata_list = collect_historical_vcc_data(
        start_date=start_date,
        end_date=end_date,
        intersection_id=intersection_id
    )
    
    if not bsm_messages and not psm_messages:
        print("⚠ No data collected - cannot process")
        return {
            'status': 'error',
            'message': 'No data collected from VCC API',
            'bsm_count': 0,
            'psm_count': 0
        }
    
    # Step 2: Extract features at 15-minute intervals
    print("\n[Step 2/6] Extracting features at 15-minute intervals...")
    
    # Extract BSM features
    bsm_features = pd.DataFrame()
    if bsm_messages:
        bsm_features = extract_bsm_features(
            bsm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15  # Historical baseline uses 15-minute intervals
        )
        print(f"✓ Extracted BSM features: {len(bsm_features)} 15-minute intervals")
    
    # Extract PSM features
    psm_features = pd.DataFrame()
    if psm_messages:
        psm_features = extract_psm_features(
            psm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ Extracted PSM features: {len(psm_features)} 15-minute intervals")
    
    # Step 3: Detect conflicts (for I_VRU and I_vehicle)
    print("\n[Step 3/6] Detecting VRU-vehicle and vehicle-vehicle conflicts...")
    
    vru_conflicts = pd.DataFrame()
    if bsm_messages and psm_messages:
        vru_conflicts = detect_vru_vehicle_conflicts(
            bsm_messages,
            psm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ Detected {len(vru_conflicts)} intervals with VRU-vehicle conflicts")
    
    vehicle_conflicts = pd.DataFrame()
    if bsm_messages and len(bsm_messages) >= 2:
        vehicle_conflicts = detect_vehicle_vehicle_conflicts(
            bsm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ Detected {len(vehicle_conflicts)} intervals with vehicle-vehicle conflicts")
    
    # Step 4: Create master feature table
    print("\n[Step 4/6] Creating master feature table...")
    
    # Start with BSM features as base
    if len(bsm_features) == 0:
        print("⚠ ERROR: No BSM features available - cannot create master table")
        return {
            'status': 'error',
            'message': 'No BSM features available',
            'bsm_count': len(bsm_messages),
            'psm_count': len(psm_messages)
        }
    
    master_features = bsm_features.copy()
    
    # Merge PSM features
    if len(psm_features) > 0:
        psm_subset = psm_features[[
            'intersection', 'time_15min', 'vru_count', 'avg_vru_speed',
            'pedestrian_count', 'cyclist_count'
        ]].copy()
        psm_subset.rename(columns={'vru_count': 'psm_vru_count'}, inplace=True)
        master_features = master_features.merge(
            psm_subset,
            on=['intersection', 'time_15min'],
            how='left'
        )
        print(f"  + Merged PSM features: {len(psm_features)} records")
    else:
        master_features['psm_vru_count'] = 0
        master_features['avg_vru_speed'] = 0
        master_features['pedestrian_count'] = 0
        master_features['cyclist_count'] = 0
        print("  ⚠ No PSM features available")
    
    # Merge VRU conflicts (I_VRU)
    if len(vru_conflicts) > 0:
        vru_subset = vru_conflicts[[
            'intersection', 'time_15min', 'I_VRU', 'vru_event_count'
        ]].copy()
        master_features = master_features.merge(
            vru_subset,
            on=['intersection', 'time_15min'],
            how='left'
        )
        print(f"  + Merged VRU conflicts: {len(vru_conflicts)} records")
    else:
        master_features['I_VRU'] = 0
        master_features['vru_event_count'] = 0
        print("  ⚠ No VRU conflicts detected")
    
    # Merge vehicle conflicts (I_vehicle)
    if len(vehicle_conflicts) > 0:
        vehicle_subset = vehicle_conflicts[[
            'intersection', 'time_15min', 'I_vehicle', 'vehicle_event_count'
        ]].copy()
        master_features = master_features.merge(
            vehicle_subset,
            on=['intersection', 'time_15min'],
            how='left'
        )
        print(f"  + Merged vehicle conflicts: {len(vehicle_conflicts)} records")
    else:
        master_features['I_vehicle'] = 0
        master_features['vehicle_event_count'] = 0
        print("  ⚠ No vehicle conflicts detected")
    
    # Calculate total event counts
    master_features['total_event_count'] = (
        master_features.get('vru_event_count', 0) +
        master_features.get('vehicle_event_count', 0)
    )
    
    # Fill NaN values
    count_cols = [
        'psm_vru_count', 'pedestrian_count', 'cyclist_count',
        'I_VRU', 'vru_event_count', 'I_vehicle', 'vehicle_event_count',
        'total_event_count'
    ]
    for col in count_cols:
        if col in master_features.columns:
            master_features[col] = master_features[col].fillna(0)
    
    if 'avg_vru_speed' in master_features.columns:
        master_features['avg_vru_speed'] = master_features['avg_vru_speed'].fillna(0)
    
    print(f"✓ Master feature table: {len(master_features)} 15-minute intervals")
    
    # Step 5: Compute normalization constants
    print("\n[Step 5/6] Computing normalization constants...")
    
    norm_constants = compute_normalization_constants(master_features)
    
    if not norm_constants:
        print("⚠ ERROR: Failed to compute normalization constants")
        return {
            'status': 'error',
            'message': 'Failed to compute normalization constants',
            'master_features_count': len(master_features)
        }
    
    print(f"✓ Normalization constants computed")
    
    # Step 6: Compute safety indices
    print("\n[Step 6/6] Computing safety indices...")
    
    indices_df = compute_safety_indices(master_features, norm_constants)
    
    if len(indices_df) == 0:
        print("⚠ ERROR: Failed to compute safety indices")
        return {
            'status': 'error',
            'message': 'Failed to compute safety indices',
            'norm_constants': norm_constants
        }
    
    print(f"✓ Safety indices computed: {len(indices_df)} intervals")
    
    # Apply Empirical Bayes adjustment (optional - requires baseline events)
    # For VCC-only data, we may not have baseline events from Trino
    # Skip EB adjustment if no baseline available
    try:
        baseline_events = collect_baseline_events(
            start_date=start_date,
            end_date=end_date
        )
        if len(baseline_events) > 0:
            print("\n[Bonus] Applying Empirical Bayes adjustment...")
            indices_df = apply_empirical_bayes(
                indices_df,
                baseline_events,
                k=settings.EMPIRICAL_BAYES_K
            )
            print("✓ Empirical Bayes adjustment applied")
        else:
            print("\n⚠ No baseline events available - skipping Empirical Bayes adjustment")
    except Exception as e:
        print(f"\n⚠ Could not apply Empirical Bayes adjustment: {e}")
    
    # Save to Parquet if requested
    if save_to_parquet:
        print("\n[Saving] Saving results to Parquet storage...")
        
        # Save features by date
        if 'time_15min' in master_features.columns:
            master_features['time_15min'] = pd.to_datetime(master_features['time_15min'])
            for date_val in master_features['time_15min'].dt.date.unique():
                day_features = master_features[
                    master_features['time_15min'].dt.date == date_val
                ]
                if len(day_features) > 0:
                    parquet_storage.save_features(day_features, date_val)
        
        # Save indices by date
        if 'time_15min' in indices_df.columns:
            indices_df['time_15min'] = pd.to_datetime(indices_df['time_15min'])
            for date_val in indices_df['time_15min'].dt.date.unique():
                day_indices = indices_df[
                    indices_df['time_15min'].dt.date == date_val
                ]
                if len(day_indices) > 0:
                    parquet_storage.save_indices(day_indices, date_val)
        
        # Save normalization constants
        parquet_storage.save_normalization_constants(norm_constants)
        
        print("✓ Results saved to Parquet storage")
    
    # Summary statistics
    print(f"\n{'='*80}")
    print("PROCESSING SUMMARY")
    print(f"{'='*80}")
    print(f"Total 15-minute intervals: {len(indices_df)}")
    print(f"Intersections: {indices_df['intersection'].nunique() if 'intersection' in indices_df.columns else 0}")
    
    if 'Combined_Index_EB' in indices_df.columns:
        print(f"\nSafety Index Statistics (EB-Adjusted):")
        print(f"  Combined Index: Mean={indices_df['Combined_Index_EB'].mean():.2f}, "
              f"Min={indices_df['Combined_Index_EB'].min():.2f}, "
              f"Max={indices_df['Combined_Index_EB'].max():.2f}")
        index_col = 'Combined_Index_EB'
    elif 'Combined_Index' in indices_df.columns:
        print(f"\nSafety Index Statistics:")
        print(f"  Combined Index: Mean={indices_df['Combined_Index'].mean():.2f}, "
              f"Min={indices_df['Combined_Index'].min():.2f}, "
              f"Max={indices_df['Combined_Index'].max():.2f}")
        index_col = 'Combined_Index'
    else:
        index_col = None
    
    print(f"{'='*80}\n")
    
    return {
        'status': 'success',
        'bsm_count': len(bsm_messages),
        'psm_count': len(psm_messages),
        'mapdata_count': len(mapdata_list),
        'features_count': len(master_features),
        'indices_count': len(indices_df),
        'intersections': indices_df['intersection'].nunique() if 'intersection' in indices_df.columns else 0,
        'date_range': {
            'start': start_date.isoformat() if start_date else None,
            'end': end_date.isoformat() if end_date else None
        },
        'saved_to_parquet': save_to_parquet,
        'norm_constants': norm_constants
    }

