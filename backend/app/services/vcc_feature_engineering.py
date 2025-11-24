"""
VCC feature engineering service - Extract and aggregate features from VCC API data.

Adapts feature extraction logic for VCC API format (different from Trino format).
Aggregates to 1-minute intervals for real-time updates and 15-minute intervals for
historical baseline computation.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from .vcc_client import vcc_client


def parse_vcc_bsm_message(bsm_message: Dict) -> Optional[Dict]:
    """
    Parse a VCC API BSM message to extract vehicle data.
    
    VCC API format: bsm_message contains 'bsmJson' with nested 'coreData'
    
    Args:
        bsm_message: Raw BSM message from VCC API
        
    Returns:
        Dictionary with parsed fields or None if invalid
    """
    try:
        bsm_json = bsm_message.get('bsmJson', {})
        core_data = bsm_json.get('coreData', {})
        
        # Extract timestamp (VCC API uses milliseconds)
        timestamp_ms = bsm_message.get('timestamp', 0)
        if timestamp_ms == 0:
            # Try alternate timestamp fields
            timestamp_ms = bsm_message.get('publishTimestamp', 0)
        
        if timestamp_ms == 0:
            return None
        
        # Parse brake status (bitmask)
        brake_status = core_data.get('brakeAppliedStatus', 0)
        hard_braking = 1 if (brake_status & 0x04) != 0 else 0
        
        # Extract acceleration if available
        accel_set = core_data.get('accelSet', {})
        accel_lon = accel_set.get('long', None) if isinstance(accel_set, dict) else None
        accel_lat = accel_set.get('lat', None) if isinstance(accel_set, dict) else None
        
        return {
            'vehicle_id': core_data.get('id'),
            'timestamp_ms': timestamp_ms,
            'timestamp': pd.to_datetime(timestamp_ms, unit='ms'),  # VCC uses milliseconds
            'lat': core_data.get('lat'),
            'lon': core_data.get('lon'),
            'speed': core_data.get('speed'),
            'heading': core_data.get('heading'),
            'elev': core_data.get('elev'),
            'brake_applied_status': brake_status,
            'hard_braking': hard_braking,
            'accel_lon': accel_lon,
            'accel_lat': accel_lat,
            'rsu_name': bsm_message.get('rsuName'),
            'location_name': bsm_message.get('locationName'),  # Use VCC's location name as intersection ID
        }
    except Exception as e:
        print(f"⚠ Error parsing BSM message: {e}")
        return None


def parse_vcc_psm_message(psm_message: Dict) -> Optional[Dict]:
    """
    Parse a VCC API PSM message to extract VRU data.
    
    VCC API format: psm_message contains 'psmJson' with nested 'position'
    
    Args:
        psm_message: Raw PSM message from VCC API
        
    Returns:
        Dictionary with parsed fields or None if invalid
    """
    try:
        psm_json = psm_message.get('psmJson', {})
        position = psm_json.get('position', {})
        
        # Extract timestamp (VCC API uses milliseconds)
        timestamp_ms = psm_message.get('timestamp', 0)
        if timestamp_ms == 0:
            timestamp_ms = psm_message.get('publishTimestamp', 0)
        
        if timestamp_ms == 0:
            return None
        
        # Parse basic type (1=pedestrian, 2=cyclist, 3=public_safety_worker)
        basic_type = psm_json.get('basicType', 0)
        
        return {
            'vru_id': psm_json.get('id'),
            'timestamp_ms': timestamp_ms,
            'timestamp': pd.to_datetime(timestamp_ms, unit='ms'),  # VCC uses milliseconds
            'lat': position.get('lat'),
            'lon': position.get('lon'),
            'elev': position.get('elev'),
            'speed': psm_json.get('speed'),
            'heading': psm_json.get('heading'),
            'basic_type': basic_type,
            'is_pedestrian': 1 if basic_type == 1 else 0,
            'is_cyclist': 1 if basic_type == 2 else 0,
            'is_public_safety': 1 if basic_type == 3 else 0,
            'rsu_name': psm_message.get('rsuName'),
            'location_name': psm_message.get('locationName'),  # Use VCC's location name as intersection ID
        }
    except Exception as e:
        print(f"⚠ Error parsing PSM message: {e}")
        return None


def map_to_intersection(lat: float, lon: float, mapdata_list: List[Dict]) -> Optional[str]:
    """
    Map lat/lon coordinates to intersection ID using MapData.
    
    Uses proximity matching to find nearest intersection within threshold.
    
    Args:
        lat: Latitude
        lon: Longitude
        mapdata_list: List of MapData messages from VCC API
        
    Returns:
        Intersection ID string or None if not found
    """
    if not mapdata_list or lat is None or lon is None:
        return None
    
    threshold_distance = 0.001  # ~100 meters in degrees
    
    for mapdata in mapdata_list:
        if 'intersections' not in mapdata:
            continue
        
        for intersection in mapdata['intersections']:
            ref_point = intersection.get('refPoint', {})
            ref_lat = ref_point.get('lat')
            ref_lon = ref_point.get('lon')
            
            if ref_lat is None or ref_lon is None:
                continue
            
            # Simple distance calculation (Haversine would be more accurate but this is faster)
            lat_diff = abs(lat - ref_lat)
            lon_diff = abs(lon - ref_lon)
            
            if lat_diff < threshold_distance and lon_diff < threshold_distance:
                int_id = intersection.get('id', {})
                return str(int_id.get('id', intersection.get('id')))
    
    return None


def calculate_heading_change_rate(heading_series: pd.Series) -> float:
    """
    Calculate rate of heading changes as proxy for weaving behavior.
    
    Args:
        heading_series: Series of heading values in degrees
        
    Returns:
        Standard deviation of heading changes
    """
    if len(heading_series) < 2:
        return 0.0
    
    headings = heading_series.dropna().values
    if len(headings) < 2:
        return 0.0
    
    # Calculate angular differences (handle circular nature of heading 0-360)
    diffs = []
    for i in range(1, len(headings)):
        diff = abs(headings[i] - headings[i-1])
        # Handle wrap-around (e.g., 359° to 1° is a 2° change, not 358°)
        if diff > 180:
            diff = 360 - diff
        diffs.append(diff)
    
    return np.std(diffs) if len(diffs) > 0 else 0.0


def extract_bsm_features(bsm_messages: List[Dict], mapdata_list: Optional[List[Dict]] = None,
                        interval_minutes: int = 15) -> pd.DataFrame:
    """
    Extract and aggregate vehicle features from VCC API BSM messages.
    
    Args:
        bsm_messages: List of BSM messages from VCC API
        mapdata_list: Optional MapData for intersection mapping
        interval_minutes: Aggregation interval in minutes (1 for real-time, 15 for historical)
        
    Returns:
        DataFrame with aggregated features per interval
    """
    if not bsm_messages:
        return pd.DataFrame()
    
    # Parse all BSM messages
    parsed_data = []
    for bsm in bsm_messages:
        parsed = parse_vcc_bsm_message(bsm)
        if parsed:
            # Use locationName as intersection identifier if available, otherwise try lat/lon mapping
            if parsed.get('location_name'):
                parsed['intersection'] = parsed['location_name']
            elif mapdata_list:
                parsed['intersection'] = map_to_intersection(
                    parsed['lat'], parsed['lon'], mapdata_list
                )
            else:
                # No location name and no mapdata - skip this BSM
                continue
            parsed_data.append(parsed)
    
    if not parsed_data:
        print("⚠ No valid BSM data after parsing")
        return pd.DataFrame()
    
    df = pd.DataFrame(parsed_data)
    
    # Convert timestamp to datetime (already done in parse, but ensure consistency)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create time interval bins
    interval_str = f'{interval_minutes}min'
    df['time_interval'] = df['timestamp'].dt.floor(interval_str)
    
    # Group by intersection and time interval
    grouped = df.groupby(['intersection', 'time_interval'], dropna=False)
    
    # Aggregate features
    features = grouped.agg({
        'vehicle_id': 'nunique',  # Unique vehicle count
        'speed': ['mean', 'std'],  # Average speed and speed variance
        'hard_braking': 'sum',  # Count of hard braking events
        'heading': lambda x: calculate_heading_change_rate(x),  # Heading change rate
        'accel_lon': 'std',  # Longitudinal acceleration variance
        'accel_lat': 'std',  # Lateral acceleration variance
    }).reset_index()
    
    # Flatten column names
    features.columns = [
        'intersection', 'time_interval',
        'vehicle_count', 'avg_speed', 'speed_variance',
        'hard_braking_count', 'heading_change_rate',
        'accel_lon_variance', 'accel_lat_variance'
    ]
    
    # Rename time_interval to appropriate column name based on interval
    time_col_name = 'time_15min'  # Default for historical processing
    if interval_minutes == 15:
        features.rename(columns={'time_interval': 'time_15min'}, inplace=True)
    else:
        # For non-15-minute intervals, use the actual interval name (e.g., time_1min)
        time_col_name = f'time_{interval_minutes}min'
        features.rename(columns={'time_interval': time_col_name}, inplace=True)

    # Add time context using the appropriate column name
    features['hour_of_day'] = pd.to_datetime(features[time_col_name]).dt.hour
    features['day_of_week'] = pd.to_datetime(features[time_col_name]).dt.dayofweek

    # Standardize time column name to 'time_15min' for compatibility with downstream code
    # that expects this column name for merging
    if time_col_name != 'time_15min':
        features['time_15min'] = features[time_col_name]
    
    # Fill NaN values
    features['speed_variance'] = features['speed_variance'].fillna(0)
    features['hard_braking_count'] = features['hard_braking_count'].fillna(0)
    features['heading_change_rate'] = features['heading_change_rate'].fillna(0)
    features['accel_lon_variance'] = features['accel_lon_variance'].fillna(0)
    features['accel_lat_variance'] = features['accel_lat_variance'].fillna(0)
    
    return features


def extract_psm_features(psm_messages: List[Dict], mapdata_list: Optional[List[Dict]] = None,
                        interval_minutes: int = 15) -> pd.DataFrame:
    """
    Extract and aggregate VRU features from VCC API PSM messages.
    
    Args:
        psm_messages: List of PSM messages from VCC API
        mapdata_list: Optional MapData for intersection mapping
        interval_minutes: Aggregation interval in minutes (1 for real-time, 15 for historical)
        
    Returns:
        DataFrame with aggregated VRU features per interval
    """
    if not psm_messages:
        return pd.DataFrame()
    
    # Parse all PSM messages
    parsed_data = []
    for psm in psm_messages:
        parsed = parse_vcc_psm_message(psm)
        if parsed:
            # Use locationName as intersection identifier if available, otherwise try lat/lon mapping
            if parsed.get('location_name'):
                parsed['intersection'] = parsed['location_name']
            elif mapdata_list:
                parsed['intersection'] = map_to_intersection(
                    parsed['lat'], parsed['lon'], mapdata_list
                )
            else:
                # No location name and no mapdata - skip this PSM
                continue
            parsed_data.append(parsed)
    
    if not parsed_data:
        print("⚠ No valid PSM data after parsing")
        return pd.DataFrame()
    
    df = pd.DataFrame(parsed_data)
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create time interval bins
    interval_str = f'{interval_minutes}min'
    df['time_interval'] = df['timestamp'].dt.floor(interval_str)
    
    # Group by intersection and time interval
    grouped = df.groupby(['intersection', 'time_interval'], dropna=False)
    
    # Aggregate features
    features = grouped.agg({
        'vru_id': 'nunique',  # Unique VRU count
        'speed': 'mean',  # Average VRU speed
        'is_pedestrian': 'sum',  # Pedestrian count
        'is_cyclist': 'sum',  # Cyclist count
        'is_public_safety': 'sum',  # Public safety worker count
    }).reset_index()
    
    # Rename columns
    features.columns = [
        'intersection', 'time_interval',
        'vru_count', 'avg_vru_speed',
        'pedestrian_count', 'cyclist_count', 'emergency_responder_count'
    ]
    
    # Rename time_interval to appropriate column name based on interval
    if interval_minutes == 15:
        features.rename(columns={'time_interval': 'time_15min'}, inplace=True)
        time_col = 'time_15min'
    else:
        # For non-15-minute intervals, use the actual interval name (e.g., time_1min)
        time_col = f'time_{interval_minutes}min'
        features.rename(columns={'time_interval': time_col}, inplace=True)
    
    # Add time context (using the correct time column)
    features['hour_of_day'] = pd.to_datetime(features[time_col]).dt.hour
    features['day_of_week'] = pd.to_datetime(features[time_col]).dt.dayofweek

    # Standardize time column name to 'time_15min' for compatibility with downstream code
    # that expects this column name for merging
    if time_col != 'time_15min':
        features['time_15min'] = features[time_col]

    # Fill NaN values
    features['avg_vru_speed'] = features['avg_vru_speed'].fillna(0)
    
    return features


def detect_vru_vehicle_conflicts(bsm_messages: List[Dict], psm_messages: List[Dict],
                                 mapdata_list: Optional[List[Dict]] = None,
                                 proximity_threshold_m: float = 10.0,
                                 time_window_seconds: float = 5.0,
                                 interval_minutes: int = 15) -> pd.DataFrame:
    """
    Detect VRU-vehicle conflicts using spatial-temporal proximity.
    
    Args:
        bsm_messages: List of BSM messages
        psm_messages: List of PSM messages
        mapdata_list: Optional MapData for intersection mapping
        proximity_threshold_m: Distance threshold in meters (default 10m)
        time_window_seconds: Time window for matching in seconds (default 5s)
        interval_minutes: Aggregation interval in minutes
        
    Returns:
        DataFrame with conflict counts per interval (I_VRU)
    """
    # Parse BSM and PSM messages
    bsm_parsed = []
    for bsm in bsm_messages:
        parsed = parse_vcc_bsm_message(bsm)
        if parsed:
            if mapdata_list:
                parsed['intersection'] = map_to_intersection(parsed['lat'], parsed['lon'], mapdata_list)
            bsm_parsed.append(parsed)
    
    psm_parsed = []
    for psm in psm_messages:
        parsed = parse_vcc_psm_message(psm)
        if parsed:
            if mapdata_list:
                parsed['intersection'] = map_to_intersection(parsed['lat'], parsed['lon'], mapdata_list)
            psm_parsed.append(parsed)
    
    if not bsm_parsed or not psm_parsed:
        return pd.DataFrame(columns=['intersection', 'time_15min', 'I_VRU', 'vru_event_count'])
    
    df_bsm = pd.DataFrame(bsm_parsed)
    df_psm = pd.DataFrame(psm_parsed)
    
    # Convert timestamps
    df_bsm['timestamp'] = pd.to_datetime(df_bsm['timestamp'])
    df_psm['timestamp'] = pd.to_datetime(df_psm['timestamp'])
    
    # Simple proximity-based conflict detection
    # Convert proximity threshold from meters to approximate degrees
    # 1 degree latitude ≈ 111,000 meters
    threshold_deg = proximity_threshold_m / 111000.0
    time_window_td = pd.Timedelta(seconds=time_window_seconds)
    
    conflicts = []
    
    # Group by intersection for efficiency
    for intersection in df_psm['intersection'].dropna().unique():
        psm_int = df_psm[df_psm['intersection'] == intersection]
        bsm_int = df_bsm[df_bsm['intersection'] == intersection]
        
        for _, psm_row in psm_int.iterrows():
            psm_time = psm_row['timestamp']
            psm_lat = psm_row['lat']
            psm_lon = psm_row['lon']
            
            # Find nearby vehicles within time window
            nearby = bsm_int[
                (abs(bsm_int['timestamp'] - psm_time) <= time_window_td) &
                (abs(bsm_int['lat'] - psm_lat) < threshold_deg) &
                (abs(bsm_int['lon'] - psm_lon) < threshold_deg)
            ]
            
            if len(nearby) > 0:
                # Create conflict record
                interval_time = psm_time.floor(f'{interval_minutes}min')
                # Use appropriate time column name based on interval
                time_col = 'time_15min' if interval_minutes == 15 else f'time_{interval_minutes}min'
                conflicts.append({
                    'intersection': intersection,
                    time_col: interval_time,
                    'conflict_id': f"{psm_row['vru_id']}_{nearby.iloc[0]['vehicle_id']}_{psm_time.timestamp()}",
                })
    
    # Determine time column name based on interval
    time_col = 'time_15min' if interval_minutes == 15 else f'time_{interval_minutes}min'
    
    if not conflicts:
        return pd.DataFrame(columns=['intersection', time_col, 'I_VRU', 'vru_event_count'])
    
    df_conflicts = pd.DataFrame(conflicts)
    
    # Aggregate conflicts per interval
    conflict_agg = df_conflicts.groupby(['intersection', time_col]).agg({
        'conflict_id': 'count'
    }).reset_index()
    
    conflict_agg.columns = ['intersection', time_col, 'I_VRU']
    conflict_agg['vru_event_count'] = conflict_agg['I_VRU']
    
    return conflict_agg


def detect_vehicle_vehicle_conflicts(bsm_messages: List[Dict],
                                     mapdata_list: Optional[List[Dict]] = None,
                                     proximity_threshold_m: float = 10.0,
                                     speed_variance_threshold: float = 5.0,
                                     time_window_seconds: float = 5.0,
                                     interval_minutes: int = 15) -> pd.DataFrame:
    """
    Detect vehicle-vehicle conflicts using proximity and speed variance.
    
    Args:
        bsm_messages: List of BSM messages
        mapdata_list: Optional MapData for intersection mapping
        proximity_threshold_m: Distance threshold in meters
        speed_variance_threshold: Speed variance threshold for conflict detection
        time_window_seconds: Time window for matching
        interval_minutes: Aggregation interval in minutes
        
    Returns:
        DataFrame with vehicle conflict counts per interval (I_vehicle)
    """
    # Parse BSM messages
    bsm_parsed = []
    for bsm in bsm_messages:
        parsed = parse_vcc_bsm_message(bsm)
        if parsed:
            if mapdata_list:
                parsed['intersection'] = map_to_intersection(parsed['lat'], parsed['lon'], mapdata_list)
            bsm_parsed.append(parsed)
    
    if len(bsm_parsed) < 2:
        return pd.DataFrame(columns=['intersection', 'time_15min', 'I_vehicle', 'vehicle_event_count'])
    
    df_bsm = pd.DataFrame(bsm_parsed)
    df_bsm['timestamp'] = pd.to_datetime(df_bsm['timestamp'])
    
    threshold_deg = proximity_threshold_m / 111000.0
    time_window_td = pd.Timedelta(seconds=time_window_seconds)
    
    conflicts = []
    
    # Group by intersection
    for intersection in df_bsm['intersection'].dropna().unique():
        bsm_int = df_bsm[df_bsm['intersection'] == intersection].sort_values('timestamp')
        
        # Check pairs of vehicles
        for i, row1 in bsm_int.iterrows():
            nearby = bsm_int[
                (abs(bsm_int['timestamp'] - row1['timestamp']) <= time_window_td) &
                (abs(bsm_int['lat'] - row1['lat']) < threshold_deg) &
                (abs(bsm_int['lon'] - row1['lon']) < threshold_deg) &
                (bsm_int.index != i)
            ]
            
            for j, row2 in nearby.iterrows():
                # Check if speed variance indicates conflict
                speed_diff = abs(row1['speed'] - row2['speed'])
                if speed_diff > speed_variance_threshold:
                    interval_time = row1['timestamp'].floor(f'{interval_minutes}min')
                    # Use appropriate time column name based on interval
                    time_col = 'time_15min' if interval_minutes == 15 else f'time_{interval_minutes}min'
                    conflicts.append({
                        'intersection': intersection,
                        time_col: interval_time,
                        'conflict_id': f"{row1['vehicle_id']}_{row2['vehicle_id']}_{row1['timestamp'].timestamp()}",
                    })
    
    # Determine time column name based on interval
    time_col = 'time_15min' if interval_minutes == 15 else f'time_{interval_minutes}min'
    
    if not conflicts:
        return pd.DataFrame(columns=['intersection', time_col, 'I_vehicle', 'vehicle_event_count'])
    
    df_conflicts = pd.DataFrame(conflicts)
    
    # Remove duplicate conflicts (same vehicle pair in same interval)
    df_conflicts = df_conflicts.drop_duplicates(subset=['intersection', time_col, 'conflict_id'])
    
    # Aggregate
    conflict_agg = df_conflicts.groupby(['intersection', time_col]).agg({
        'conflict_id': 'count'
    }).reset_index()
    
    conflict_agg.columns = ['intersection', time_col, 'I_vehicle']
    conflict_agg['vehicle_event_count'] = conflict_agg['I_vehicle']
    
    return conflict_agg

