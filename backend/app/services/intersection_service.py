"""
Intersection service - Orchestrates the full safety index computation pipeline
Phases 2-7: Data Collection → Feature Engineering → Index Computation
"""

from typing import List, Optional
from datetime import datetime, timedelta

from ..models.intersection import Intersection
from ..core.config import settings
from .data_collection import collect_baseline_events, collect_exposure_metrics
from .feature_engineering import (
    collect_bsm_features, collect_psm_features,
    aggregate_safety_events, create_master_feature_table
)
from .index_computation import (
    compute_normalization_constants,
    compute_safety_indices,
    apply_empirical_bayes
)


def compute_current_indices() -> List[Intersection]:
    """
    Compute current safety indices for all intersections using the complete pipeline.

    Pipeline:
    1. Phase 2: Collect baseline events + exposure metrics
    2. Phase 3: Engineer features from BSM, PSM, and events
    3. Phase 4: Create master feature table
    4. Phase 5: Compute normalization constants
    5. Phase 6: Compute VRU, Vehicle, Combined indices
    6. Phase 7: Apply Empirical Bayes adjustment

    Returns:
        List of Intersection objects with computed safety scores
    """
    try:
        # Use configurable lookback period
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=settings.DEFAULT_LOOKBACK_DAYS)

        print(f"\n{'='*80}")
        print(f"TRAFFIC SAFETY INDEX COMPUTATION PIPELINE")
        print(f"{'='*80}")
        print(f"Time range: {start_dt.date()} to {end_dt.date()}")
        print(f"Lookback period: {settings.DEFAULT_LOOKBACK_DAYS} days\n")

        # ========== Phase 2: Data Collection ==========
        print("[Phase 2] Collecting baseline events and exposure metrics...")
        baseline_events = collect_baseline_events(start_date=start_dt, end_date=end_dt)
        vehicle_counts, vru_counts = collect_exposure_metrics(start_date=start_dt, end_date=end_dt)

        # ========== Phase 3: Feature Engineering ==========
        print("\n[Phase 3] Engineering features from BSM, PSM, and safety events...")
        bsm_features = collect_bsm_features(start_date=start_dt, end_date=end_dt)

        if len(bsm_features) == 0:
            print("⚠ No BSM features available - cannot compute indices")
            return []

        psm_features = collect_psm_features(start_date=start_dt, end_date=end_dt)
        aggregated_events = aggregate_safety_events(start_date=start_dt, end_date=end_dt)

        # ========== Phase 4: Master Feature Table ==========
        print("\n[Phase 4] Creating master feature table...")
        master_features = create_master_feature_table(
            bsm_features=bsm_features,
            psm_features=psm_features,
            aggregated_events=aggregated_events,
            vehicle_counts=vehicle_counts,
            vru_counts=vru_counts
        )

        if len(master_features) == 0:
            print("⚠ Master feature table is empty - cannot compute indices")
            return []

        # ========== Phase 5: Normalization Constants ==========
        print("\n[Phase 5] Computing normalization constants...")
        norm_constants = compute_normalization_constants(master_features)

        # ========== Phase 6: Safety Index Computation ==========
        print("\n[Phase 6] Computing VRU, Vehicle, and Combined Safety Indices...")
        indices_df = compute_safety_indices(master_features, norm_constants)

        if len(indices_df) == 0:
            print("⚠ No indices computed")
            return []

        # ========== Phase 7: Empirical Bayes Adjustment ==========
        print("\n[Phase 7] Applying Empirical Bayes stabilization...")
        indices_df = apply_empirical_bayes(
            indices_df,
            baseline_events,
            k=settings.EMPIRICAL_BAYES_K
        )

        # ========== Get Latest Index per Intersection ==========
        print("\n[Final] Aggregating latest indices per intersection...")
        latest = indices_df.sort_values('time_15min').groupby('intersection').last().reset_index()

        print(f"\n{'='*80}")
        print(f"✓ PIPELINE COMPLETE: Computed indices for {len(latest)} intersections")
        print(f"{'='*80}\n")

        # Convert to Intersection objects
        intersections = []
        for idx, row in latest.iterrows():
            # Use EB-adjusted Combined Index if available, otherwise raw
            safety_index = float(row.get('Combined_Index_EB', row.get('Combined_Index', 0)))

            intersections.append(
                Intersection(
                    intersection_id=100 + idx + 1,  # Generate sequential IDs
                    intersection_name=row['intersection'],
                    safety_index=safety_index,
                    traffic_volume=int(row.get('vehicle_count', 0)),
                    longitude=-77.053,  # Default coordinates (TODO: lookup from metadata)
                    latitude=38.856
                )
            )

        return intersections

    except Exception as e:
        print(f"\n⚠ ERROR in safety index pipeline: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_all() -> List[Intersection]:
    """Return a list of all intersections with current safety indices."""
    return compute_current_indices()


def get_by_id(intersection_id: int) -> Optional[Intersection]:
    """Return a single intersection matching the given ID, or None."""
    all_intersections = get_all()

    for item in all_intersections:
        if item.intersection_id == intersection_id:
            return item

    return None
