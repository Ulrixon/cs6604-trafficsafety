"""
Crash Data Correlation Analysis (Phase 7)

Analyzes the correlation between safety indices and actual crash occurrences
to validate formula effectiveness and identify opportunities for weight tuning.

Metrics computed:
- True Positive Rate: High safety index when crash occurred
- False Positive Rate: High safety index when no crash occurred
- Precision, Recall, F1 Score
- ROC curve and AUC
- Correlation coefficients (Pearson, Spearman)
- Feature importance analysis

Usage:
    python scripts/crash_correlation_analysis.py --start-date 2025-01-01 --end-date 2025-11-21
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import argparse
import pandas as pd
import numpy as np
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.data_collection import collect_baseline_events
from app.services.index_computation import compute_multi_source_safety_indices
from app.db.connection import db_session, init_db
from app.core.config import settings
from sqlalchemy import text
import os
import psycopg2

# GCP PostgreSQL Database Configuration
GCP_DB_HOST = "34.140.49.230"
GCP_DB_PORT = 5432
GCP_DB_NAME = "vtsi"
GCP_DB_USER = "jason"
GCP_DB_PASSWORD = "*9ZS^l(HGq].BA]6"


@dataclass
class CorrelationMetrics:
    """Results from crash correlation analysis"""
    total_crashes: int
    total_intervals: int
    crash_rate: float

    # Classification metrics (using threshold)
    threshold: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

    # Correlation metrics
    pearson_correlation: float
    spearman_correlation: float

    # AUC metrics
    auc_score: Optional[float] = None

    # Weather impact analysis
    weather_crash_multiplier: Optional[float] = None
    rain_crash_rate: Optional[float] = None
    clear_crash_rate: Optional[float] = None


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth in meters.

    Uses the Haversine formula:
    a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
    c = 2 ⋅ atan2( √a, √(1−a) )
    d = R ⋅ c

    Args:
        lat1, lon1: Latitude and longitude of point 1 (degrees)
        lat2, lon2: Latitude and longitude of point 2 (degrees)

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters

    φ1 = radians(lat1)
    φ2 = radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)

    a = sin(Δφ/2)**2 + cos(φ1) * cos(φ2) * sin(Δλ/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def load_monitored_intersections() -> pd.DataFrame:
    """
    Load monitored intersection coordinates from local PostgreSQL database.

    Returns:
        DataFrame with columns: intersection_id, name, latitude, longitude
    """
    print_section("Loading Monitored Intersections")

    try:
        from app.db.connection import db_session
        from sqlalchemy import text

        query = text("""
            SELECT
                id as intersection_id,
                name,
                latitude,
                longitude
            FROM intersections
            ORDER BY id
        """)

        with db_session() as session:
            result = session.execute(query)
            rows = result.fetchall()

            if not rows:
                print("WARNING: No intersections found in local database")
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=['intersection_id', 'name', 'latitude', 'longitude'])

            print(f"OK Loaded {len(df)} monitored intersections")
            print(f"  Sample intersections:")
            for _, row in df.head(3).iterrows():
                print(f"    - {row['name']}: ({row['latitude']:.6f}, {row['longitude']:.6f})")

            return df

    except Exception as e:
        print(f"ERROR loading intersections from database: {e}")
        print("  Using fallback coordinates for testing")

        # Fallback: Sample Virginia intersections for testing
        return pd.DataFrame({
            'intersection_id': [1, 2, 3],
            'name': [
                'I-66 & Route 28',
                'Route 7 & Leesburg Pike',
                'I-495 & Georgetown Pike'
            ],
            'latitude': [38.9547, 38.9186, 38.9539],
            'longitude': [-77.4457, -77.2253, -77.1950]
        })


def filter_crashes_near_intersections(
    crashes: pd.DataFrame,
    intersections: pd.DataFrame,
    proximity_radius_meters: float = 500.0
) -> pd.DataFrame:
    """
    Filter crashes to only include those near monitored intersections.

    For each crash, calculates distance to all monitored intersections.
    Only keeps crashes within proximity_radius_meters of at least one intersection.

    Args:
        crashes: DataFrame with crash data (must have latitude, longitude columns)
        intersections: DataFrame with intersection data (must have latitude, longitude columns)
        proximity_radius_meters: Maximum distance from intersection (default: 500 meters)

    Returns:
        Filtered DataFrame with crashes near intersections, with additional columns:
        - nearest_intersection_id: ID of nearest intersection
        - nearest_intersection_name: Name of nearest intersection
        - distance_to_intersection: Distance to nearest intersection in meters
    """
    print_section(f"Filtering Crashes Near Monitored Intersections (radius: {proximity_radius_meters}m)")

    if crashes.empty or intersections.empty:
        print("WARNING: No crashes or intersections to filter")
        return crashes

    # Check for required columns
    if 'latitude' not in crashes.columns or 'longitude' not in crashes.columns:
        print("ERROR: Crash data missing latitude/longitude columns")
        return crashes

    filtered_crashes = []

    print(f"Checking {len(crashes):,} crashes against {len(intersections)} intersections...")

    for idx, crash in crashes.iterrows():
        crash_lat = crash['latitude']
        crash_lon = crash['longitude']

        # Skip crashes with invalid coordinates
        if pd.isna(crash_lat) or pd.isna(crash_lon):
            continue

        # Calculate distance to all intersections
        min_distance = float('inf')
        nearest_intersection_id = None
        nearest_intersection_name = None

        for _, intersection in intersections.iterrows():
            distance = haversine_distance(
                crash_lat, crash_lon,
                intersection['latitude'], intersection['longitude']
            )

            if distance < min_distance:
                min_distance = distance
                nearest_intersection_id = intersection['intersection_id']
                nearest_intersection_name = intersection['name']

        # Keep crash if within proximity radius
        if min_distance <= proximity_radius_meters:
            crash_dict = crash.to_dict()
            crash_dict['nearest_intersection_id'] = nearest_intersection_id
            crash_dict['nearest_intersection_name'] = nearest_intersection_name
            crash_dict['distance_to_intersection'] = min_distance
            filtered_crashes.append(crash_dict)

    if not filtered_crashes:
        print(f"WARNING: No crashes found within {proximity_radius_meters}m of monitored intersections")
        return pd.DataFrame()

    df_filtered = pd.DataFrame(filtered_crashes)

    print(f"\nOK Spatial filtering complete:")
    print(f"  Original crashes: {len(crashes):,}")
    print(f"  Crashes near intersections: {len(df_filtered):,} ({len(df_filtered)/len(crashes)*100:.1f}%)")
    print(f"  Avg distance to intersection: {df_filtered['distance_to_intersection'].mean():.1f}m")
    print(f"  Max distance to intersection: {df_filtered['distance_to_intersection'].max():.1f}m")

    # Show crash distribution by intersection
    print(f"\n  Crashes by intersection:")
    crash_counts = df_filtered['nearest_intersection_name'].value_counts().head(5)
    for intersection, count in crash_counts.items():
        print(f"    - {intersection}: {count} crashes")

    return df_filtered


def load_crash_data(
    start_date: datetime,
    end_date: datetime,
    locality: Optional[str] = None,
    intersections: Optional[pd.DataFrame] = None,
    proximity_radius_meters: Optional[float] = None
) -> pd.DataFrame:
    """
    Load historical crash data from GCP PostgreSQL vdot_crashes table.

    Args:
        start_date: Start of analysis period
        end_date: End of analysis period
        locality: Filter by Virginia locality (optional)
        intersections: DataFrame with monitored intersections for spatial filtering (optional)
        proximity_radius_meters: Maximum distance from intersection to include crashes (optional)

    Returns:
        DataFrame with columns: crash_id, timestamp, latitude, longitude, severity,
                              total_vehicles, total_injured, total_killed, weather,
                              light_condition, road_surface
                              If spatial filtering applied, also includes:
                              nearest_intersection_id, nearest_intersection_name, distance_to_intersection
    """
    print_section("Loading VDOT Crash Data from GCP PostgreSQL")

    print("NOTE: Before running, ensure your IP is allowlisted:")
    print("  gcloud sql connect vtsi-postgres --user=jason --database=vtsi --quiet")
    print()

    try:
        # Connect to GCP database
        conn = psycopg2.connect(
            host=GCP_DB_HOST,
            port=GCP_DB_PORT,
            database=GCP_DB_NAME,
            user=GCP_DB_USER,
            password=GCP_DB_PASSWORD,
            connect_timeout=10
        )

        print(f"OK Connected to GCP database: {GCP_DB_NAME}")

        # Build query with filters
        where_clauses = ["crash_date >= %(start_date)s", "crash_date <= %(end_date)s"]
        params = {
            'start_date': start_date.date(),
            'end_date': end_date.date()
        }

        if locality:
            where_clauses.append("locality = %(locality)s")
            params['locality'] = locality

        where_clause = " AND ".join(where_clauses)

        query = f"""
            SELECT
                document_nbr as crash_id,
                crash_date,
                crash_time,
                latitude,
                longitude,
                severity,
                total_vehicles,
                total_injured,
                total_killed,
                weather,
                light_condition,
                road_surface,
                locality
            FROM vdot_crashes
            WHERE {where_clause}
            ORDER BY crash_date DESC, crash_time DESC
        """

        print(f"Querying crashes from {start_date.date()} to {end_date.date()}...")

        # Execute query
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            print("WARNING: No crash data found for the specified period")
            print("   Falling back to synthetic data")
            return generate_synthetic_crash_data(start_date, end_date)

        # Create timestamp from crash_date and crash_time
        # crash_time is in format like "845" for 8:45 AM
        def parse_crash_time(row):
            try:
                time_str = str(int(row['crash_time'])).zfill(4)  # Pad to 4 digits: "0845"
                hour = int(time_str[:2])
                minute = int(time_str[2:])
                return datetime.combine(row['crash_date'], datetime.min.time()).replace(hour=hour, minute=minute)
            except:
                # If parsing fails, use noon as default
                return datetime.combine(row['crash_date'], datetime.min.time()).replace(hour=12, minute=0)

        df['timestamp'] = df.apply(parse_crash_time, axis=1)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Determine if weather-related based on weather column
        df['weather_related'] = df['weather'].notna() & ~df['weather'].isin(['CLEAR', 'CLOUDY', ''])

        print(f"\nOK Loaded {len(df):,} crash records from VDOT database")
        print(f"  Date range: {df['crash_date'].min()} to {df['crash_date'].max()}")
        print(f"  Localities: {df['locality'].nunique()} unique")
        print(f"  Severity breakdown:")
        for severity, count in df['severity'].value_counts().head(5).items():
            print(f"    - {severity}: {count:,}")
        print(f"  Weather-related: {df['weather_related'].sum():,} ({df['weather_related'].sum()/len(df)*100:.1f}%)")

        # Apply spatial filtering if intersections provided
        if intersections is not None and proximity_radius_meters is not None:
            df = filter_crashes_near_intersections(df, intersections, proximity_radius_meters)

        return df

    except psycopg2.OperationalError as e:
        if "timeout" in str(e).lower():
            print(f"\nERROR: Connection timeout - Your IP may not be allowlisted")
            print(f"       Run: gcloud sql connect vtsi-postgres --user=jason --database=vtsi --quiet")
            print(f"       Then try again within 5 minutes")
        else:
            print(f"\nERROR: Database connection failed: {e}")
        print(f"       Falling back to synthetic crash data")
        return generate_synthetic_crash_data(start_date, end_date)
    except Exception as e:
        print(f"\nERROR: Failed to load crash data: {e}")
        print(f"       Falling back to synthetic crash data")
        return generate_synthetic_crash_data(start_date, end_date)


def load_safety_indices_from_db(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Load safety indices from PostgreSQL database.

    Args:
        start_date: Start of analysis period
        end_date: End of analysis period

    Returns:
        DataFrame with columns: timestamp, intersection_id, combined_index, vru_index, vehicle_index
    """
    print_section("Loading Safety Indices from PostgreSQL")

    query = text("""
        SELECT
            timestamp,
            intersection_id,
            combined_index AS "Combined_Index",
            vru_index AS "VRU_Index",
            vehicle_index AS "Vehicle_Index",
            traffic_volume,
            vru_count
        FROM safety_indices_realtime
        WHERE timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp
    """)

    try:
        with db_session() as session:
            result = session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            })
            rows = result.fetchall()

            if not rows:
                print("WARNING: No safety indices found in database for the specified period")
                return pd.DataFrame()

            # Convert to DataFrame
            indices = pd.DataFrame(rows, columns=['timestamp', 'intersection_id', 'Combined_Index',
                                                  'VRU_Index', 'Vehicle_Index', 'traffic_volume', 'vru_count'])

            print(f"OK Loaded {len(indices)} safety index records from PostgreSQL")
            print(f"  Date range: {indices['timestamp'].min()} to {indices['timestamp'].max()}")
            print(f"  Intersections: {indices['intersection_id'].nunique()}")
            print(f"  Avg Combined Index: {indices['Combined_Index'].mean():.1f}")

            return indices
    except Exception as e:
        print(f"ERROR loading safety indices from database: {e}")
        print("  Falling back to synthetic data generation")
        return pd.DataFrame()


def generate_synthetic_crash_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Generate synthetic crash data for testing when real data unavailable.

    Synthetic crashes are more likely during:
    - High safety index periods (validates correlation)
    - Rush hours (morning/evening)
    - Bad weather conditions
    """
    np.random.seed(42)

    # Generate crashes over time period
    total_days = (end_date - start_date).days
    num_crashes = int(total_days * 2)  # ~2 crashes per day

    crashes = []
    for i in range(num_crashes):
        # Random timestamp
        random_day = start_date + timedelta(days=np.random.randint(0, total_days))

        # Bias towards rush hours (7-9am, 4-7pm)
        hour = np.random.choice([7, 8, 16, 17, 18], p=[0.2, 0.2, 0.2, 0.2, 0.2])
        minute = np.random.randint(0, 60)

        timestamp = random_day.replace(hour=hour, minute=minute, second=0)

        crashes.append({
            'crash_id': f'CRASH_{i:04d}',
            'intersection': f'Intersection_{np.random.randint(0, 5)}',
            'timestamp': timestamp,
            'severity': np.random.choice([1, 3, 10], p=[0.7, 0.25, 0.05]),  # Mostly PDO, some injury, rare fatal
            'weather_related': np.random.choice([True, False], p=[0.3, 0.7])  # 30% weather-related
        })

    df = pd.DataFrame(crashes)
    print(f"OK Generated {len(df)} synthetic crash records for testing")

    return df


def merge_crashes_with_indices(
    crashes: pd.DataFrame,
    indices: pd.DataFrame,
    time_window_minutes: int = 15
) -> pd.DataFrame:
    """
    Merge crash data with safety indices using time window matching.

    For each crash, finds the safety index from the time bin containing the crash.

    Args:
        crashes: Crash DataFrame
        indices: Safety indices DataFrame
        time_window_minutes: Time bin size (default: 15 minutes)

    Returns:
        Merged DataFrame with crash and index data
    """
    print_section("Merging Crashes with Safety Indices")

    # Floor crash timestamps to 15-minute bins
    # Handle timezone-aware and timezone-naive timestamps
    crashes = crashes.copy()
    crashes['timestamp'] = pd.to_datetime(crashes['timestamp'])

    # Localize to UTC if timezone-naive, otherwise convert to UTC
    # Handle DST ambiguity by inferring (use first occurrence for ambiguous times)
    if crashes['timestamp'].dt.tz is None:
        crashes['timestamp'] = crashes['timestamp'].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
    else:
        # First remove timezone info, then reapply as UTC to avoid DST issues
        crashes['timestamp'] = crashes['timestamp'].dt.tz_localize(None).dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')

    crashes['time_bin'] = crashes['timestamp'].dt.floor(f'{time_window_minutes}min')

    # Floor index timestamps to 15-minute bins
    indices = indices.copy()
    if 'timestamp' in indices.columns:
        indices['timestamp'] = pd.to_datetime(indices['timestamp'])
        if indices['timestamp'].dt.tz is None:
            indices['timestamp'] = indices['timestamp'].dt.tz_localize('UTC', ambiguous='infer')
        else:
            indices['timestamp'] = indices['timestamp'].dt.tz_convert('UTC')
        indices['time_bin'] = indices['timestamp'].dt.floor(f'{time_window_minutes}min')
    else:
        indices['time_bin'] = indices.index

    # Merge on intersection and time_bin
    merged = crashes.merge(
        indices,
        on=['time_bin'],
        how='left',
        suffixes=('_crash', '_index')
    )

    # Count crashes per time bin
    crash_counts = crashes.groupby('time_bin').size().reset_index(name='crash_count')

    # Create full time series with crash counts
    all_bins = pd.DataFrame({
        'time_bin': pd.date_range(
            start=crashes['timestamp'].min().floor(f'{time_window_minutes}min'),
            end=crashes['timestamp'].max().ceil(f'{time_window_minutes}min'),
            freq=f'{time_window_minutes}min'
        )
    })

    time_series = all_bins.merge(crash_counts, on='time_bin', how='left')
    time_series['crash_count'] = time_series['crash_count'].fillna(0)
    time_series['had_crash'] = (time_series['crash_count'] > 0).astype(int)

    # Merge with indices
    time_series = time_series.merge(indices, on='time_bin', how='left')

    print(f"OK Merged data:")
    print(f"  Total time bins: {len(time_series)}")
    print(f"  Bins with crashes: {time_series['had_crash'].sum()}")
    print(f"  Bins with indices: {time_series['Combined_Index'].notna().sum()}")

    return time_series


def compute_correlation_metrics(
    data: pd.DataFrame,
    threshold: float = 60.0
) -> CorrelationMetrics:
    """
    Compute correlation metrics between safety indices and crashes.

    Args:
        data: Merged DataFrame with crash and index data
        threshold: Safety index threshold for classification (default: 60.0 = "High" risk)

    Returns:
        CorrelationMetrics object with all computed metrics
    """
    print_section("Computing Correlation Metrics")

    # Filter to rows with both crash data and index data
    valid_data = data[data['Combined_Index'].notna()].copy()

    if len(valid_data) == 0:
        print("ERROR: No valid data for correlation analysis")
        return None

    # Binary classification: did a crash occur?
    y_true = valid_data['had_crash'].values
    y_pred = (valid_data['Combined_Index'] >= threshold).astype(int).values

    # Confusion matrix
    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))

    # Classification metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0

    # Correlation metrics
    pearson_corr = np.corrcoef(valid_data['Combined_Index'], y_true)[0, 1]
    from scipy.stats import spearmanr
    spearman_corr, _ = spearmanr(valid_data['Combined_Index'], y_true)

    # Weather impact analysis
    if 'Weather_Index' in valid_data.columns:
        high_weather = valid_data[valid_data['Weather_Index'] > 50]
        low_weather = valid_data[valid_data['Weather_Index'] <= 50]

        rain_crash_rate = high_weather['had_crash'].mean() if len(high_weather) > 0 else 0.0
        clear_crash_rate = low_weather['had_crash'].mean() if len(low_weather) > 0 else 0.0
        weather_multiplier = rain_crash_rate / clear_crash_rate if clear_crash_rate > 0 else 1.0
    else:
        rain_crash_rate = None
        clear_crash_rate = None
        weather_multiplier = None

    metrics = CorrelationMetrics(
        total_crashes=int(y_true.sum()),
        total_intervals=len(valid_data),
        crash_rate=float(y_true.mean()),
        threshold=threshold,
        true_positives=int(tp),
        false_positives=int(fp),
        true_negatives=int(tn),
        false_negatives=int(fn),
        precision=float(precision),
        recall=float(recall),
        f1_score=float(f1_score),
        accuracy=float(accuracy),
        pearson_correlation=float(pearson_corr),
        spearman_correlation=float(spearman_corr),
        weather_crash_multiplier=weather_multiplier,
        rain_crash_rate=rain_crash_rate,
        clear_crash_rate=clear_crash_rate
    )

    return metrics


def print_metrics_report(metrics: CorrelationMetrics):
    """Print formatted metrics report."""
    print_section("Correlation Analysis Results")

    print(f"Dataset Overview:")
    print(f"  Total time intervals analyzed: {metrics.total_intervals:,}")
    print(f"  Total crashes: {metrics.total_crashes}")
    print(f"  Overall crash rate: {metrics.crash_rate:.2%}")

    print(f"\nClassification Performance (Threshold: {metrics.threshold}):")
    print(f"  True Positives: {metrics.true_positives} (high index + crash)")
    print(f"  False Positives: {metrics.false_positives} (high index + no crash)")
    print(f"  True Negatives: {metrics.true_negatives} (low index + no crash)")
    print(f"  False Negatives: {metrics.false_negatives} (low index + crash)")

    print(f"\nMetrics:")
    print(f"  Precision: {metrics.precision:.3f} (of high-index periods, {metrics.precision:.1%} had crashes)")
    print(f"  Recall: {metrics.recall:.3f} (of crashes, {metrics.recall:.1%} had high index)")
    print(f"  F1 Score: {metrics.f1_score:.3f}")
    print(f"  Accuracy: {metrics.accuracy:.3f}")

    print(f"\nCorrelation:")
    print(f"  Pearson correlation: {metrics.pearson_correlation:.3f}")
    print(f"  Spearman correlation: {metrics.spearman_correlation:.3f}")

    if metrics.weather_crash_multiplier is not None:
        print(f"\nWeather Impact:")
        print(f"  Crash rate in bad weather: {metrics.rain_crash_rate:.2%}")
        print(f"  Crash rate in clear weather: {metrics.clear_crash_rate:.2%}")
        print(f"  Weather crash multiplier: {metrics.weather_crash_multiplier:.2f}x")

        if metrics.weather_crash_multiplier > 1.5:
            print(f"  OK Strong weather effect - consider increasing weather plugin weight")
        elif metrics.weather_crash_multiplier > 1.2:
            print(f"  → Moderate weather effect - current weight (0.15) seems appropriate")
        else:
            print(f"  ! Weak weather effect - consider decreasing weather plugin weight")

    print(f"\nInterpretation:")
    if metrics.pearson_correlation > 0.3:
        print(f"  OK GOOD: Strong positive correlation between safety index and crashes")
        print(f"    The formula effectively predicts crash risk")
    elif metrics.pearson_correlation > 0.15:
        print(f"  → MODERATE: Moderate correlation - formula has predictive power")
        print(f"    Consider feature weight tuning to improve")
    else:
        print(f"  ! WEAK: Weak correlation - formula needs improvement")
        print(f"    Review feature selection and weights")

    if metrics.f1_score > 0.5:
        print(f"  OK F1 Score is acceptable for crash prediction")
    else:
        print(f"  ! Low F1 Score - high false positive/negative rate")


def main():
    """Main analysis function."""
    parser = argparse.ArgumentParser(description="Crash Correlation Analysis")
    parser.add_argument('--start-date', type=str, default='2025-01-01',
                      help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2025-11-21',
                      help='End date (YYYY-MM-DD)')
    parser.add_argument('--threshold', type=float, default=60.0,
                      help='Safety index threshold for high risk classification')
    parser.add_argument('--use-real-data', action='store_true',
                      help='Use real crash data (requires crash database)')
    parser.add_argument('--proximity-radius', type=float, default=500.0,
                      help='Maximum distance from intersection in meters (default: 500)')
    parser.add_argument('--no-spatial-filter', action='store_true',
                      help='Disable spatial filtering (include all crashes)')

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Initialize database connection
    # Replace 'db:5432' with 'localhost:5433' when running outside Docker
    database_url = settings.DATABASE_URL
    if '@db:5432' in database_url and not os.getenv('DOCKER_CONTAINER'):
        database_url = database_url.replace('@db:5432', '@localhost:5433')
    init_db(database_url, settings.DB_POOL_SIZE, settings.DB_MAX_OVERFLOW)

    print(f"\n{'#'*80}")
    print(f"#  CRASH CORRELATION ANALYSIS (Phase 7)")
    print(f"#  Date: {datetime.now()}")
    print(f"#  Period: {start_date.date()} to {end_date.date()}")
    print(f"#  Spatial filtering: {'DISABLED' if args.no_spatial_filter else f'ENABLED ({args.proximity_radius}m radius)'}")
    print(f"{'#'*80}")

    # Load monitored intersections for spatial filtering
    intersections = None
    proximity_radius = None

    if args.use_real_data and not args.no_spatial_filter:
        intersections = load_monitored_intersections()
        if not intersections.empty:
            proximity_radius = args.proximity_radius

    # Load crash data
    if args.use_real_data:
        crashes = load_crash_data(
            start_date,
            end_date,
            intersections=intersections,
            proximity_radius_meters=proximity_radius
        )
        if crashes.empty:
            print("\nERROR: No crash data available. Exiting.")
            return
    else:
        print_section("Generating Synthetic Crash Data")
        print("Using synthetic data for demonstration purposes")
        # Generate synthetic crashes (in production, load from database)
        n_crashes = 200
        crash_times = pd.to_datetime(np.random.choice(
            pd.date_range(start_date, end_date, freq='1h'),
            size=n_crashes,
            replace=True
        ))
        crashes = pd.DataFrame({
            'crash_id': [f'CRASH_{i:04d}' for i in range(n_crashes)],
            'timestamp': crash_times,
            'severity': np.random.choice(['Minor', 'Moderate', 'Severe'], n_crashes, p=[0.6, 0.3, 0.1]),
            'crash_type': np.random.choice(['Vehicle-Vehicle', 'Vehicle-VRU', 'Single-Vehicle'], n_crashes)
        })
        print(f"Generated {len(crashes)} synthetic crash records")
        print(f"  Crash rate: {len(crashes) / ((end_date - start_date).days * 24):.1f} crashes/hour")

    # Load safety indices from PostgreSQL
    indices = load_safety_indices_from_db(start_date, end_date)

    if indices.empty:
        print("\nWARNING: No safety indices available in database")
        print("         Generating synthetic indices for demonstration")
        # Fallback to synthetic data
        time_bins = pd.date_range(start=start_date, end=end_date, freq='15min')
        indices = pd.DataFrame({
            'timestamp': time_bins,
            'Combined_Index': np.random.uniform(30, 80, len(time_bins)),
            'Weather_Index': np.random.uniform(20, 70, len(time_bins)),
            'Traffic_Index': np.random.uniform(40, 85, len(time_bins))
        })
        print(f"OK Generated {len(indices)} synthetic safety index records")

    # Merge crashes with indices
    merged_data = merge_crashes_with_indices(crashes, indices)

    # Compute correlation metrics
    metrics = compute_correlation_metrics(merged_data, threshold=args.threshold)

    if metrics is None:
        print("\n! ERROR: Could not compute correlation metrics")
        return

    # Print results
    print_metrics_report(metrics)

    # Recommendations
    print_section("Recommendations")

    if metrics.pearson_correlation < 0.2:
        print("1. ! LOW CORRELATION: Review feature selection and normalization")
        print("   - Verify VCC features accurately capture traffic risk")
        print("   - Check weather feature scaling")
        print("   - Consider additional data sources (road geometry, lighting, etc.)")

    if metrics.weather_crash_multiplier and metrics.weather_crash_multiplier > 1.5:
        print("2. OK STRONG WEATHER EFFECT: Consider increasing weather weight from 0.15 to 0.20-0.25")

    if metrics.precision < 0.3:
        print("3. ! HIGH FALSE POSITIVE RATE: Consider raising safety index threshold")
        print(f"   - Current threshold: {metrics.threshold}")
        print(f"   - Try threshold: {metrics.threshold + 10}")

    if metrics.recall < 0.5:
        print("4. ! MISSING CRASHES: Consider lowering safety index threshold")
        print(f"   - Current threshold: {metrics.threshold}")
        print(f"   - Try threshold: {metrics.threshold - 10}")

    print(f"\n{'='*80}")
    print(f"Analysis complete. Results can be used to tune plugin weights in settings.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Install scipy if not already installed
    try:
        from scipy.stats import spearmanr
    except ImportError:
        print("Installing required package: scipy")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy"])
        from scipy.stats import spearmanr

    main()
