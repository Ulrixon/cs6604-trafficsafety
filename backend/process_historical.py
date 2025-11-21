"""
Historical Safety Index Processing Script

Processes all accumulated VCC data from Parquet storage to compute:
- Features at 15-minute intervals
- Normalization constants from full dataset
- Safety indices for all time periods
- Empirical Bayes adjusted indices

Usage:
    python process_historical.py [--days N] [--intersection ID]
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.parquet_storage import ParquetStorage
from app.services.vcc_feature_engineering import (
    extract_bsm_features,
    extract_psm_features,
    detect_vru_vehicle_conflicts,
    detect_vehicle_vehicle_conflicts
)
from app.services.index_computation import (
    compute_normalization_constants,
    compute_safety_indices,
    apply_empirical_bayes
)
from app.core.config import settings
import pandas as pd


def load_parquet_data(storage: ParquetStorage, days: int = 7):
    """
    Load all raw data from Parquet files.

    Args:
        storage: ParquetStorage instance
        days: Number of days to look back

    Returns:
        Tuple of (bsm_list, psm_list, mapdata_list)
    """
    print(f"\n[1/7] Loading raw data from Parquet files...")

    # Load BSM data
    bsm_files = list(storage.raw_bsm_path.glob("bsm_*.parquet"))
    print(f"  Found {len(bsm_files)} BSM files")

    bsm_dfs = []
    for f in bsm_files:
        try:
            df = pd.read_parquet(f)
            bsm_dfs.append(df)
        except Exception as e:
            print(f"  ⚠ Error reading {f.name}: {e}")

    bsm_df = pd.concat(bsm_dfs, ignore_index=True) if bsm_dfs else pd.DataFrame()
    bsm_messages = bsm_df.to_dict('records') if not bsm_df.empty else []

    # Load PSM data
    psm_files = list(storage.raw_psm_path.glob("psm_*.parquet"))
    print(f"  Found {len(psm_files)} PSM files")

    psm_dfs = []
    for f in psm_files:
        try:
            df = pd.read_parquet(f)
            psm_dfs.append(df)
        except Exception as e:
            print(f"  ⚠ Error reading {f.name}: {e}")

    psm_df = pd.concat(psm_dfs, ignore_index=True) if psm_dfs else pd.DataFrame()
    psm_messages = psm_df.to_dict('records') if not psm_df.empty else []

    # Load MapData (use most recent)
    mapdata_files = sorted(storage.raw_mapdata_path.glob("mapdata_*.parquet"))
    mapdata_list = []

    if mapdata_files:
        print(f"  Found {len(mapdata_files)} MapData files (using most recent)")
        try:
            latest_mapdata = pd.read_parquet(mapdata_files[-1])
            mapdata_list = latest_mapdata.to_dict('records')
        except Exception as e:
            print(f"  ⚠ Error reading MapData: {e}")

    print(f"✓ Loaded {len(bsm_messages)} BSM, {len(psm_messages)} PSM, {len(mapdata_list)} MapData messages")

    return bsm_messages, psm_messages, mapdata_list


def process_historical_data(storage_path: str, days: int = 7, intersection_id: str = None):
    """
    Main processing pipeline for historical data.
    """
    print(f"\n{'='*80}")
    print("HISTORICAL SAFETY INDEX PROCESSING")
    print(f"{'='*80}")
    print(f"Storage Path: {storage_path}")
    print(f"Lookback Period: {days} days")
    if intersection_id:
        print(f"Intersection Filter: {intersection_id}")
    print(f"{'='*80}\n")

    # Initialize storage
    storage = ParquetStorage(storage_path)

    # Load raw data from Parquet files
    bsm_messages, psm_messages, mapdata_list = load_parquet_data(storage, days)

    if not bsm_messages:
        print("\n✗ No BSM data found. Cannot process.")
        return None

    # Step 2: Extract features at 15-minute intervals
    print(f"\n[2/7] Extracting features at 15-minute intervals...")

    bsm_features = extract_bsm_features(
        bsm_messages,
        mapdata_list=mapdata_list,
        interval_minutes=15
    )
    print(f"✓ Extracted BSM features: {len(bsm_features)} intervals")

    psm_features = pd.DataFrame()
    if psm_messages:
        psm_features = extract_psm_features(
            psm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ Extracted PSM features: {len(psm_features)} intervals")
    else:
        print("  ⚠ No PSM data available")

    # Step 3: Detect conflicts
    print(f"\n[3/7] Detecting conflicts...")

    vru_conflicts = pd.DataFrame()
    if psm_messages:
        vru_conflicts = detect_vru_vehicle_conflicts(
            bsm_messages,
            psm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ VRU-vehicle conflicts: {len(vru_conflicts)} intervals")
    else:
        print("  ⚠ No PSM data for VRU conflict detection")

    vehicle_conflicts = pd.DataFrame()
    if len(bsm_messages) >= 2:
        vehicle_conflicts = detect_vehicle_vehicle_conflicts(
            bsm_messages,
            mapdata_list=mapdata_list,
            interval_minutes=15
        )
        print(f"✓ Vehicle-vehicle conflicts: {len(vehicle_conflicts)} intervals")

    # Step 4: Create master feature table
    print(f"\n[4/7] Creating master feature table...")

    master_features = bsm_features.copy()

    # Merge PSM features
    if not psm_features.empty:
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
    else:
        master_features['psm_vru_count'] = 0
        master_features['avg_vru_speed'] = 0
        master_features['pedestrian_count'] = 0
        master_features['cyclist_count'] = 0

    # Merge conflicts
    if not vru_conflicts.empty:
        vru_subset = vru_conflicts[['intersection', 'time_15min', 'I_VRU', 'vru_event_count']].copy()
        master_features = master_features.merge(vru_subset, on=['intersection', 'time_15min'], how='left')
    else:
        master_features['I_VRU'] = 0
        master_features['vru_event_count'] = 0

    if not vehicle_conflicts.empty:
        vehicle_subset = vehicle_conflicts[['intersection', 'time_15min', 'I_vehicle', 'vehicle_event_count']].copy()
        master_features = master_features.merge(vehicle_subset, on=['intersection', 'time_15min'], how='left')
    else:
        master_features['I_vehicle'] = 0
        master_features['vehicle_event_count'] = 0

    # Fill NaN values
    master_features = master_features.fillna(0)

    print(f"✓ Master feature table: {len(master_features)} intervals")

    # Step 5: Compute normalization constants
    print(f"\n[5/7] Computing normalization constants...")

    norm_constants = compute_normalization_constants(master_features)

    # Save constants for real-time use
    storage.save_normalization_constants(norm_constants)
    print(f"✓ Normalization constants saved to Parquet")

    # Step 6: Compute safety indices
    print(f"\n[6/7] Computing safety indices...")

    indices_df = compute_safety_indices(master_features, norm_constants)
    print(f"✓ Safety indices computed for {len(indices_df)} intervals")

    # Step 7: Apply Empirical Bayes adjustment (SKIPPED for now)
    print(f"\n[7/7] Skipping Empirical Bayes adjustment (using raw indices)...")
    indices_df_eb = indices_df.copy()

    # Add EB columns as copies of raw indices for compatibility
    if 'Combined_Index' in indices_df.columns:
        indices_df_eb['Combined_Index_EB'] = indices_df['Combined_Index']
    if 'I_VRU' in indices_df.columns:
        indices_df_eb['I_VRU_EB'] = indices_df['I_VRU']
    if 'I_vehicle' in indices_df.columns:
        indices_df_eb['I_vehicle_EB'] = indices_df['I_vehicle']

    print(f"✓ Using raw safety indices (EB adjustment skipped)")

    # Save results
    print(f"\nSaving results to Parquet...")
    storage.save_features(master_features)
    storage.save_indices(indices_df_eb)

    print(f"\n{'='*80}")
    print("PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total Intervals: {len(master_features)}")
    print(f"Unique Intersections: {master_features['intersection'].nunique()}")
    print(f"Date Range: {master_features['time_15min'].min()} to {master_features['time_15min'].max()}")
    print(f"{'='*80}\n")

    # Display summary statistics
    print("Safety Index Summary (by intersection):")
    print("-" * 80)
    if 'Combined_Index_EB' in indices_df_eb.columns:
        summary = indices_df_eb.groupby('intersection').agg({
            'Combined_Index_EB': ['mean', 'min', 'max', 'count']
        }).round(2)
        print(summary.head(10))
    else:
        print("  No safety indices to display")
    print(f"\n...")

    return {
        'master_features': master_features,
        'indices': indices_df_eb,
        'norm_constants': norm_constants
    }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Process historical VCC data and compute safety indices')
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to look back (default: 7)'
    )
    parser.add_argument(
        '--intersection',
        type=str,
        default=None,
        help='Optional intersection ID filter'
    )
    parser.add_argument(
        '--storage-path',
        type=str,
        default='data/parquet',
        help='Path to Parquet storage (default: data/parquet)'
    )

    args = parser.parse_args()

    try:
        result = process_historical_data(
            storage_path=args.storage_path,
            days=args.days,
            intersection_id=args.intersection
        )

        if result:
            print("\n✓ Historical processing completed successfully!")
            return 0
        else:
            print("\n✗ Historical processing failed")
            return 1

    except Exception as e:
        print(f"\n✗ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
