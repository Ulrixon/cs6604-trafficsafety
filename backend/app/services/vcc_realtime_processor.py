"""
VCC real-time processor for processing 1-minute buffered messages.

Processes 1-minute aggregated features and computes safety indices using
15-minute rolling windows for real-time updates.
"""

import pandas as pd
from typing import List, Dict, Optional, Deque
from collections import deque
from datetime import datetime, timedelta
from .vcc_feature_engineering import (
    extract_bsm_features, extract_psm_features,
    detect_vru_vehicle_conflicts, detect_vehicle_vehicle_conflicts
)
from .parquet_storage import parquet_storage
from .index_computation import (
    compute_normalization_constants,
    compute_safety_indices
)
from ..core.config import settings


class VCCRealtimeProcessor:
    """
    Real-time processor for VCC API data.
    
    Maintains a 15-minute rolling window of 1-minute aggregated features
    and computes safety indices for the most recent 15-minute window.
    """
    
    def __init__(self, window_minutes: int = 15):
        """
        Initialize real-time processor.
        
        Args:
            window_minutes: Size of rolling window in minutes (default 15)
        """
        self.window_minutes = window_minutes
        self.feature_window: Deque[pd.DataFrame] = deque(maxlen=window_minutes)
        self.norm_constants: Optional[Dict] = None
        self.mapdata_list: Optional[List[Dict]] = None
        self._load_normalization_constants()
    
    def _load_normalization_constants(self):
        """Load normalization constants from Parquet storage"""
        self.norm_constants = parquet_storage.load_normalization_constants()
        if not self.norm_constants:
            print("⚠ No normalization constants found - will need to compute from historical data")
    
    def set_mapdata(self, mapdata_list: List[Dict]):
        """Set MapData for intersection mapping"""
        self.mapdata_list = mapdata_list
    
    def update_mapdata(self):
        """Update MapData from VCC API if needed"""
        # This would fetch MapData from VCC API
        # For now, it's expected to be set externally
        pass
    
    async def process_minute_interval(
        self,
        bsm_messages: List[Dict],
        psm_messages: List[Dict],
        interval_start: datetime
    ) -> Dict:
        """
        Process a 1-minute interval of messages and update safety indices.
        
        This function:
        1. Extracts features from 1-minute aggregated messages
        2. Adds to 15-minute rolling window
        3. Computes safety indices for most recent 15-minute window
        4. Saves to Parquet storage
        5. Returns updated indices
        
        Args:
            bsm_messages: BSM messages from 1-minute interval
            psm_messages: PSM messages from 1-minute interval
            interval_start: Start time of the 1-minute interval
            
        Returns:
            Dictionary with processing results and updated indices
        """
        print(f"\n[{interval_start.strftime('%Y-%m-%d %H:%M:%S')}] Processing 1-minute interval...")
        
        # Step 1: Extract features at 1-minute intervals
        bsm_features = pd.DataFrame()
        if bsm_messages:
            bsm_features = extract_bsm_features(
                bsm_messages,
                mapdata_list=self.mapdata_list,
                interval_minutes=1  # Real-time uses 1-minute intervals
            )
            print(f"  ✓ BSM features: {len(bsm_features)} 1-minute intervals")
        
        psm_features = pd.DataFrame()
        if psm_messages:
            psm_features = extract_psm_features(
                psm_messages,
                mapdata_list=self.mapdata_list,
                interval_minutes=1
            )
            print(f"  ✓ PSM features: {len(psm_features)} 1-minute intervals")
        
        # Step 2: Detect conflicts (using 1-minute intervals for real-time)
        vru_conflicts = pd.DataFrame()
        if bsm_messages and psm_messages:
            vru_conflicts = detect_vru_vehicle_conflicts(
                bsm_messages,
                psm_messages,
                mapdata_list=self.mapdata_list,
                interval_minutes=1  # Real-time uses 1-minute intervals
            )
        
        vehicle_conflicts = pd.DataFrame()
        if bsm_messages and len(bsm_messages) >= 2:
            vehicle_conflicts = detect_vehicle_vehicle_conflicts(
                bsm_messages,
                mapdata_list=self.mapdata_list,
                interval_minutes=1
            )
        
        # Step 3: Combine 1-minute features
        minute_features = pd.DataFrame()
        
        if len(bsm_features) > 0:
            minute_features = bsm_features.copy()
            
            # Ensure 1-minute features have time_1min column (they should after fix)
            if 'time_1min' not in minute_features.columns and 'time_15min' in minute_features.columns:
                # Fallback: rename time_15min to time_1min if it exists (shouldn't happen with fix)
                minute_features.rename(columns={'time_15min': 'time_1min'}, inplace=True)
            elif 'time_1min' not in minute_features.columns:
                # If neither exists, create from timestamp
                if 'timestamp' in minute_features.columns:
                    minute_features['time_1min'] = pd.to_datetime(minute_features['timestamp']).dt.floor('1min')
            
            # Merge PSM features
            if len(psm_features) > 0:
                # PSM features should have time_1min column when interval_minutes=1
                psm_time_col = 'time_1min' if 'time_1min' in psm_features.columns else 'time_15min'
                psm_subset = psm_features[[
                    'intersection', psm_time_col, 'vru_count', 'avg_vru_speed',
                    'pedestrian_count', 'cyclist_count'
                ]].copy()
                psm_subset.rename(columns={'vru_count': 'psm_vru_count'}, inplace=True)
                # Ensure PSM has time_1min column for merge
                if psm_time_col != 'time_1min':
                    psm_subset.rename(columns={psm_time_col: 'time_1min'}, inplace=True)
                
                minute_features = minute_features.merge(
                    psm_subset,
                    on=['intersection', 'time_1min'],
                    how='outer'
                )
            else:
                minute_features['psm_vru_count'] = 0
                minute_features['avg_vru_speed'] = 0
                minute_features['pedestrian_count'] = 0
                minute_features['cyclist_count'] = 0
            
            # Merge conflicts (conflicts should have time_1min when interval_minutes=1)
            if len(vru_conflicts) > 0:
                vru_time_col = 'time_1min' if 'time_1min' in vru_conflicts.columns else 'time_15min'
                vru_subset = vru_conflicts[[
                    'intersection', vru_time_col, 'I_VRU', 'vru_event_count'
                ]].copy()
                # Ensure VRU conflicts have time_1min column for merge
                if vru_time_col != 'time_1min':
                    vru_subset.rename(columns={vru_time_col: 'time_1min'}, inplace=True)
                minute_features = minute_features.merge(
                    vru_subset,
                    on=['intersection', 'time_1min'],
                    how='left'
                )
            else:
                minute_features['I_VRU'] = 0
                minute_features['vru_event_count'] = 0
            
            if len(vehicle_conflicts) > 0:
                vehicle_time_col = 'time_1min' if 'time_1min' in vehicle_conflicts.columns else 'time_15min'
                vehicle_subset = vehicle_conflicts[[
                    'intersection', vehicle_time_col, 'I_vehicle', 'vehicle_event_count'
                ]].copy()
                # Ensure vehicle conflicts have time_1min column for merge
                if vehicle_time_col != 'time_1min':
                    vehicle_subset.rename(columns={vehicle_time_col: 'time_1min'}, inplace=True)
                minute_features = minute_features.merge(
                    vehicle_subset,
                    on=['intersection', 'time_1min'],
                    how='left'
                )
            else:
                minute_features['I_vehicle'] = 0
                minute_features['vehicle_event_count'] = 0
            
            # Fill NaN values
            count_cols = [
                'psm_vru_count', 'pedestrian_count', 'cyclist_count',
                'I_VRU', 'vru_event_count', 'I_vehicle', 'vehicle_event_count'
            ]
            for col in count_cols:
                if col in minute_features.columns:
                    minute_features[col] = minute_features[col].fillna(0)
            
            if 'avg_vru_speed' in minute_features.columns:
                minute_features['avg_vru_speed'] = minute_features['avg_vru_speed'].fillna(0)
        elif len(psm_features) > 0:
            # Only PSM features available
            minute_features = psm_features.copy()
            # Ensure time_1min column exists (should already be there after fix)
            if 'time_1min' not in minute_features.columns and 'time_15min' in minute_features.columns:
                minute_features.rename(columns={'time_15min': 'time_1min'}, inplace=True)
            elif 'time_1min' not in minute_features.columns:
                # Create from timestamp if available
                if 'timestamp' in minute_features.columns:
                    minute_features['time_1min'] = pd.to_datetime(minute_features['timestamp']).dt.floor('1min')
            minute_features['vehicle_count'] = 0
            minute_features['avg_speed'] = 0
            minute_features['speed_variance'] = 0
            minute_features['hard_braking_count'] = 0
            minute_features['heading_change_rate'] = 0
            minute_features['I_VRU'] = 0
            minute_features['vru_event_count'] = 0
            minute_features['I_vehicle'] = 0
            minute_features['vehicle_event_count'] = 0
        
        if len(minute_features) == 0:
            print("  ⚠ No features extracted from messages")
            return {
                'status': 'no_data',
                'message': 'No features extracted from messages',
                'indices': pd.DataFrame()
            }
        
        # Step 4: Add to rolling window (convert 1-minute to 15-minute bins)
        # For 15-minute window computation, we need to aggregate 1-minute features
        minute_features['time_15min'] = pd.to_datetime(minute_features['time_1min']).dt.floor('15min')
        
        # Add to window
        self.feature_window.append(minute_features)
        
        # Step 5: Compute 15-minute aggregated features from rolling window
        if len(self.feature_window) >= self.window_minutes:
            # Combine all 1-minute features in window
            window_features = pd.concat(list(self.feature_window), ignore_index=True)
            
            # Aggregate to 15-minute intervals
            window_15min = window_features.groupby(['intersection', 'time_15min']).agg({
                'vehicle_count': 'sum',  # Sum vehicle counts
                'avg_speed': 'mean',  # Average speed
                'speed_variance': lambda x: pd.Series(x).mean(),  # Average variance
                'hard_braking_count': 'sum',  # Sum braking events
                'heading_change_rate': 'mean',
                'psm_vru_count': 'sum',
                'avg_vru_speed': 'mean',
                'pedestrian_count': 'sum',
                'cyclist_count': 'sum',
                'I_VRU': 'sum',  # Sum conflicts
                'vru_event_count': 'sum',
                'I_vehicle': 'sum',
                'vehicle_event_count': 'sum',
            }).reset_index()
            
            # Step 6: Compute safety indices for 15-minute window
            if not self.norm_constants:
                print("  ⚠ Computing normalization constants from window...")
                self.norm_constants = compute_normalization_constants(window_15min)
                if not self.norm_constants:
                    print("  ⚠ Failed to compute normalization constants")
                    return {
                        'status': 'error',
                        'message': 'Failed to compute normalization constants',
                        'indices': pd.DataFrame()
                    }
            
            indices_df = compute_safety_indices(window_15min, self.norm_constants)
            
            if len(indices_df) == 0:
                print("  ⚠ Failed to compute safety indices")
                return {
                    'status': 'error',
                    'message': 'Failed to compute safety indices',
                    'indices': pd.DataFrame()
                }
            
            # Step 7: Save to Parquet storage (for most recent 15-minute interval only)
            most_recent_time = indices_df['time_15min'].max()
            most_recent_indices = indices_df[indices_df['time_15min'] == most_recent_time].copy()
            
            if len(most_recent_indices) > 0:
                target_date = pd.to_datetime(most_recent_time).date()
                
                # Load existing indices for this date and merge
                try:
                    existing_indices = parquet_storage.load_indices(
                        target_date, target_date
                    )
                    if len(existing_indices) > 0:
                        # Remove duplicate intervals
                        existing_indices = existing_indices[
                            existing_indices['time_15min'] != most_recent_time
                        ]
                        # Combine and save
                        combined_indices = pd.concat([existing_indices, most_recent_indices], ignore_index=True)
                        parquet_storage.save_indices(combined_indices, target_date)
                    else:
                        parquet_storage.save_indices(most_recent_indices, target_date)
                    
                    print(f"  ✓ Saved indices for {most_recent_time.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception as e:
                    print(f"  ⚠ Error saving indices: {e}")
            
            print(f"  ✓ Safety indices computed: {len(indices_df)} intervals")
            
            return {
                'status': 'success',
                'interval_start': interval_start.isoformat(),
                'window_size': len(self.feature_window),
                'indices': indices_df,
                'most_recent_indices': most_recent_indices
            }
        else:
            # Window not yet full
            print(f"  ⚠ Window not full ({len(self.feature_window)}/{self.window_minutes} minutes)")
            return {
                'status': 'window_building',
                'interval_start': interval_start.isoformat(),
                'window_size': len(self.feature_window),
                'window_capacity': self.window_minutes,
                'indices': pd.DataFrame()
            }


# Global processor instance
vcc_realtime_processor = VCCRealtimeProcessor(window_minutes=15)

