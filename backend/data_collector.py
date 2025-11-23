"""
Standalone VCC Data Collector Service

This service runs continuously to collect real-time data from the VCC API,
process it, and update intersection safety indices.

Usage:
    python data_collector.py [--interval SECONDS] [--realtime]
"""

import sys
import os
import time
import argparse
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.vcc_client import vcc_client
from app.services.vcc_data_collection import collect_all_vcc_data
from app.services.parquet_storage import ParquetStorage
from app.services.vcc_feature_engineering import (
    extract_bsm_features,
    extract_psm_features,
    detect_vru_vehicle_conflicts,
    detect_vehicle_vehicle_conflicts
)
from app.services.index_computation import compute_safety_indices
from app.core.config import settings
from app.db.connection import init_db, close_db
from app.services.db_service import insert_safety_indices_batch, SafetyIndexRecord, upsert_intersection
from app.services.gcs_storage import GCSStorage
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataCollector:
    """Main data collector service"""

    def __init__(
        self,
        collection_interval: int = 60,
        realtime_mode: bool = False,
        storage_path: str = "data/parquet"
    ):
        """
        Initialize data collector.

        Args:
            collection_interval: Seconds between collection cycles
            realtime_mode: Enable real-time WebSocket streaming
            storage_path: Path to store Parquet files
        """
        self.collection_interval = collection_interval
        self.realtime_mode = realtime_mode
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        self.storage = ParquetStorage(str(self.storage_path))

        # Initialize database connection if PostgreSQL is enabled
        self.db_initialized = False
        if settings.USE_POSTGRESQL or settings.ENABLE_DUAL_WRITE:
            try:
                logger.info("Initializing PostgreSQL connection for dual-write...")
                init_db(
                    database_url=settings.DATABASE_URL,
                    pool_size=settings.DB_POOL_SIZE,
                    max_overflow=settings.DB_MAX_OVERFLOW
                )
                self.db_initialized = True
                logger.info("✓ PostgreSQL connection initialized")
            except Exception as e:
                logger.error(f"✗ Failed to initialize PostgreSQL: {e}")
                if not settings.FALLBACK_TO_PARQUET:
                    raise
                logger.warning("Continuing with Parquet-only mode...")

        # Initialize GCS client if cloud upload is enabled
        self.gcs_initialized = False
        self.gcs = None
        if settings.ENABLE_GCS_UPLOAD:
            try:
                if not settings.GCS_BUCKET_NAME:
                    logger.warning("GCS upload enabled but GCS_BUCKET_NAME not configured")
                else:
                    logger.info("Initializing GCS client for cloud archival...")
                    self.gcs = GCSStorage(
                        bucket_name=settings.GCS_BUCKET_NAME,
                        project_id=settings.GCS_PROJECT_ID or None
                    )
                    self.gcs_initialized = True
                    logger.info(f"✓ GCS client initialized: gs://{settings.GCS_BUCKET_NAME}")
            except Exception as e:
                logger.error(f"✗ Failed to initialize GCS client: {e}")
                logger.warning("Continuing without GCS upload...")

        # Running flag
        self.running = False

        # Statistics
        self.stats = {
            'collections': 0,
            'total_bsm': 0,
            'total_psm': 0,
            'total_mapdata': 0,
            'last_collection': None,
            'errors': 0,
            'parquet_writes': 0,
            'db_writes': 0,
            'dual_write_errors': 0,
            'gcs_uploads': 0,
            'gcs_errors': 0
        }

        # Intersection name to ID mapping (in-memory cache)
        self.intersection_id_map = {}
        self.next_intersection_id = 1

    def get_or_create_intersection_id(self, intersection_name: str, lat: float = None, lon: float = None) -> int:
        """
        Get or create an intersection ID for a given intersection name.
        Upserts the intersection into the database if it doesn't exist.

        Args:
            intersection_name: Name of the intersection (e.g., "US-50 & Nutley")
            lat: Optional latitude (average from BSM data)
            lon: Optional longitude (average from BSM data)

        Returns:
            Integer intersection ID
        """
        # Check cache first
        if intersection_name in self.intersection_id_map:
            return self.intersection_id_map[intersection_name]

        # Assign new ID
        intersection_id = self.next_intersection_id
        self.intersection_id_map[intersection_name] = intersection_id
        self.next_intersection_id += 1

        # Upsert into database if initialized
        if self.db_initialized:
            try:
                upsert_intersection(
                    intersection_id=intersection_id,
                    name=intersection_name,
                    latitude=lat or 0.0,
                    longitude=lon or 0.0
                )
            except Exception as e:
                print(f"  ⚠ Failed to upsert intersection '{intersection_name}': {e}")

        return intersection_id

    def setup_signal_handlers(self):
        """Setup graceful shutdown on SIGINT/SIGTERM"""
        def shutdown_handler(signum, frame):
            print("\n\n⚠ Received shutdown signal, stopping collector...")
            self.running = False
            # Close database connection
            if self.db_initialized:
                close_db()
                print("✓ Database connections closed")

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    def save_safety_indices_dual_write(self, indices_df: pd.DataFrame) -> tuple[bool, bool, bool]:
        """
        Save safety indices to Parquet, PostgreSQL, and GCS (triple-write).

        Args:
            indices_df: DataFrame with computed safety indices

        Returns:
            Tuple of (parquet_success, db_success, gcs_success)
        """
        parquet_success = False
        db_success = False
        gcs_success = False
        local_parquet_path = None

        # 1. Save to Parquet (local archive)
        try:
            local_parquet_path = self.storage.save_indices(indices_df)
            parquet_success = True
            self.stats['parquet_writes'] += 1
            print(f"  ✓ Parquet: Saved {len(indices_df)} records")
        except Exception as e:
            print(f"  ✗ Parquet write failed: {e}")
            logger.error(f"Parquet write failed: {e}", exc_info=True)
            self.stats['dual_write_errors'] += 1

        # 2. Save to PostgreSQL (operational database)
        if self.db_initialized and (settings.USE_POSTGRESQL or settings.ENABLE_DUAL_WRITE):
            try:
                # Convert DataFrame rows to SafetyIndexRecord objects
                records = []
                for _, row in indices_df.iterrows():
                    # Get or create intersection ID from name
                    intersection_name = row['intersection'] if pd.notna(row['intersection']) else None
                    if not intersection_name:
                        continue  # Skip records without intersection name

                    intersection_id = self.get_or_create_intersection_id(intersection_name)

                    # Extract timestamp (column is named time_15min but contains 1-minute timestamps)
                    timestamp = pd.to_datetime(row['time_15min'])

                    # Create record
                    record = SafetyIndexRecord(
                        intersection_id=intersection_id,
                        timestamp=timestamp,
                        combined_index=float(row.get('Combined_Index', 0)),
                        combined_index_eb=float(row.get('Combined_Index_EB')) if pd.notna(row.get('Combined_Index_EB')) else None,
                        vru_index=float(row.get('VRU_Index')) if pd.notna(row.get('VRU_Index')) else None,
                        vehicle_index=float(row.get('Vehicle_Index')) if pd.notna(row.get('Vehicle_Index')) else None,
                        traffic_volume=int(row.get('traffic_volume', 0)),
                        vru_count=int(row.get('psm_vru_count', 0)),
                        hour_of_day=timestamp.hour,
                        day_of_week=timestamp.weekday()
                    )
                    records.append(record)

                # Batch insert
                success_count = insert_safety_indices_batch(records)
                if success_count == len(records):
                    db_success = True
                    self.stats['db_writes'] += 1
                    print(f"  ✓ PostgreSQL: Saved {success_count}/{len(records)} records")
                else:
                    print(f"  ⚠ PostgreSQL: Partial success {success_count}/{len(records)} records")
                    self.stats['dual_write_errors'] += 1

            except Exception as e:
                print(f"  ✗ PostgreSQL write failed: {e}")
                logger.error(f"PostgreSQL write failed: {e}", exc_info=True)
                self.stats['dual_write_errors'] += 1
                if not settings.FALLBACK_TO_PARQUET:
                    raise

        # 3. Upload to GCS (cloud archive)
        if self.gcs_initialized and parquet_success and local_parquet_path:
            try:
                # Extract date from the first timestamp in the DataFrame
                first_timestamp = pd.to_datetime(indices_df.iloc[0]['time_15min'])
                target_date = first_timestamp.date()

                # Upload to GCS
                gcs_uri = self.gcs.upload_indices(
                    local_path=Path(local_parquet_path),
                    target_date=target_date
                )
                gcs_success = True
                self.stats['gcs_uploads'] += 1
                print(f"  ✓ GCS: Uploaded to {gcs_uri}")
            except Exception as e:
                print(f"  ✗ GCS upload failed: {e}")
                logger.error(f"GCS upload failed: {e}", exc_info=True)
                self.stats['gcs_errors'] += 1

        return parquet_success, db_success, gcs_success

    def collect_cycle(self) -> bool:
        """
        Execute one collection cycle.

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n{'='*80}")
            print(f"COLLECTION CYCLE #{self.stats['collections'] + 1}")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")

            # Collect data from VCC API
            print("\n[1/3] Collecting VCC data...")
            bsm_messages, psm_messages, mapdata_list = collect_all_vcc_data()

            # Update statistics
            self.stats['total_bsm'] += len(bsm_messages)
            self.stats['total_psm'] += len(psm_messages)
            self.stats['total_mapdata'] += len(mapdata_list)
            self.stats['last_collection'] = datetime.now()

            if not bsm_messages and not psm_messages:
                print("⚠ No new data collected")
                return True

            # Save raw data to Parquet and upload to GCS
            print("\n[2/3] Saving data to Parquet storage...")
            if bsm_messages:
                bsm_path = self.storage.save_bsm_batch(bsm_messages)
                print(f"✓ Saved {len(bsm_messages)} BSM messages")

                # Upload to GCS if enabled
                if self.gcs_initialized and bsm_path:
                    try:
                        # Extract date from first message timestamp
                        first_timestamp = pd.to_datetime(bsm_messages[0].get('metadata', {}).get('generatedAt', datetime.now()))
                        target_date = first_timestamp.date()
                        gcs_uri = self.gcs.upload_bsm_batch(Path(bsm_path), target_date)
                        self.stats['gcs_uploads'] += 1
                        print(f"  ✓ GCS: Uploaded BSM to {gcs_uri}")
                    except Exception as e:
                        print(f"  ⚠ GCS upload failed: {e}")
                        logger.error(f"GCS BSM upload failed: {e}", exc_info=True)
                        self.stats['gcs_errors'] += 1

            if psm_messages:
                psm_path = self.storage.save_psm_batch(psm_messages)
                print(f"✓ Saved {len(psm_messages)} PSM messages")

                # Upload to GCS if enabled
                if self.gcs_initialized and psm_path:
                    try:
                        first_timestamp = pd.to_datetime(psm_messages[0].get('metadata', {}).get('generatedAt', datetime.now()))
                        target_date = first_timestamp.date()
                        gcs_uri = self.gcs.upload_psm_batch(Path(psm_path), target_date)
                        self.stats['gcs_uploads'] += 1
                        print(f"  ✓ GCS: Uploaded PSM to {gcs_uri}")
                    except Exception as e:
                        print(f"  ⚠ GCS upload failed: {e}")
                        logger.error(f"GCS PSM upload failed: {e}", exc_info=True)
                        self.stats['gcs_errors'] += 1

            if mapdata_list:
                mapdata_path = self.storage.save_mapdata_batch(mapdata_list)
                print(f"✓ Saved {len(mapdata_list)} MapData messages")

                # Upload to GCS if enabled
                if self.gcs_initialized and mapdata_path:
                    try:
                        # MapData doesn't have timestamp, use current date
                        target_date = datetime.now().date()
                        gcs_uri = self.gcs.upload_mapdata_batch(Path(mapdata_path), target_date)
                        self.stats['gcs_uploads'] += 1
                        print(f"  ✓ GCS: Uploaded MapData to {gcs_uri}")
                    except Exception as e:
                        print(f"  ⚠ GCS upload failed: {e}")
                        logger.error(f"GCS MapData upload failed: {e}", exc_info=True)
                        self.stats['gcs_errors'] += 1

            # Real-time processing: Compute safety indices
            print("\n[3/3] Computing real-time safety indices...")
            try:
                # Load normalization constants if they exist
                norm_constants = None
                try:
                    norm_constants = self.storage.load_normalization_constants()
                    print("✓ Loaded normalization constants")
                except Exception as e:
                    print(f"⚠ No normalization constants found - run process_historical.py first")
                    print("  Skipping real-time index computation")
                    norm_constants = None

                if norm_constants is not None and bsm_messages:
                    # Extract features at 1-minute intervals for real-time
                    bsm_features = extract_bsm_features(
                        bsm_messages,
                        mapdata_list=mapdata_list,
                        interval_minutes=1
                    )
                    print(f"✓ Extracted BSM features: {len(bsm_features)} intervals")

                    # Extract PSM features if available
                    if psm_messages:
                        psm_features = extract_psm_features(
                            psm_messages,
                            mapdata_list=mapdata_list,
                            interval_minutes=1
                        )
                        print(f"✓ Extracted PSM features: {len(psm_features)} intervals")
                    else:
                        psm_features = pd.DataFrame()

                    # Detect conflicts
                    vru_conflicts = pd.DataFrame()
                    if psm_messages:
                        vru_conflicts = detect_vru_vehicle_conflicts(
                            bsm_messages,
                            psm_messages,
                            mapdata_list=mapdata_list,
                            interval_minutes=1
                        )

                    vehicle_conflicts = pd.DataFrame()
                    if len(bsm_messages) >= 2:
                        vehicle_conflicts = detect_vehicle_vehicle_conflicts(
                            bsm_messages,
                            mapdata_list=mapdata_list,
                            interval_minutes=1
                        )

                    # Create master feature table
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

                    # Compute safety indices
                    indices_df = compute_safety_indices(master_features, norm_constants)

                    # Save indices using triple-write (Parquet + PostgreSQL + GCS)
                    print(f"\nSaving {len(indices_df)} computed safety indices...")
                    parquet_ok, db_ok, gcs_ok = self.save_safety_indices_dual_write(indices_df)

                    # Report results
                    if parquet_ok and db_ok and gcs_ok:
                        print("✓ Triple-write successful (Parquet + PostgreSQL + GCS)")
                    elif parquet_ok and db_ok:
                        print("✓ Dual-write successful (Parquet + PostgreSQL)")
                    elif parquet_ok and gcs_ok:
                        print("✓ Dual-write successful (Parquet + GCS)")
                    elif parquet_ok:
                        print("✓ Parquet write successful (Database/GCS write failed or disabled)")
                    elif db_ok:
                        print("✓ PostgreSQL write successful (Parquet/GCS write failed)")
                    else:
                        print("✗ All writes failed!")

            except Exception as e:
                print(f"⚠ Error during real-time processing: {e}")
                import traceback
                traceback.print_exc()

            print("\n✓ Data collection cycle completed successfully")

            self.stats['collections'] += 1

            # Print statistics
            self.print_statistics()

            return True

        except Exception as e:
            print(f"✗ Error during collection cycle: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'] += 1
            return False

    def print_statistics(self):
        """Print collection statistics"""
        print(f"\n{'='*80}")
        print("COLLECTION STATISTICS")
        print(f"{'='*80}")
        print(f"Total Collections: {self.stats['collections']}")
        print(f"Total BSM Messages: {self.stats['total_bsm']:,}")
        print(f"Total PSM Messages: {self.stats['total_psm']:,}")
        print(f"Total MapData: {self.stats['total_mapdata']}")
        print(f"Errors: {self.stats['errors']}")

        # Storage statistics
        if self.db_initialized or self.gcs_initialized:
            print(f"\nStorage Statistics:")
            print(f"  Parquet Writes: {self.stats['parquet_writes']}")
            if self.db_initialized:
                print(f"  PostgreSQL Writes: {self.stats['db_writes']}")
                print(f"  Dual-Write Errors: {self.stats['dual_write_errors']}")
            if self.gcs_initialized:
                print(f"  GCS Uploads: {self.stats['gcs_uploads']}")
                print(f"  GCS Errors: {self.stats['gcs_errors']}")

        if self.stats['last_collection']:
            print(f"\nLast Collection: {self.stats['last_collection'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")

    def run(self):
        """Run the data collector continuously"""
        self.running = True
        self.setup_signal_handlers()

        print("\n" + "="*80)
        print("VCC DATA COLLECTOR SERVICE")
        print("="*80)
        print(f"Collection Interval: {self.collection_interval} seconds")
        print(f"Realtime Mode: {self.realtime_mode}")
        print(f"Storage Path: {self.storage_path}")
        print(f"VCC Base URL: {settings.VCC_BASE_URL}")

        print(f"\nPostgreSQL Dual-Write: {'✓ ENABLED' if self.db_initialized else '✗ DISABLED'}")
        if self.db_initialized:
            print(f"  Database URL: {settings.DATABASE_URL}")
            print(f"  Fallback to Parquet: {settings.FALLBACK_TO_PARQUET}")

        print(f"\nGCS Cloud Archive: {'✓ ENABLED' if self.gcs_initialized else '✗ DISABLED'}")
        if self.gcs_initialized:
            print(f"  Bucket: gs://{settings.GCS_BUCKET_NAME}")
            if settings.GCS_PROJECT_ID:
                print(f"  Project ID: {settings.GCS_PROJECT_ID}")

        print("="*80 + "\n")

        # Verify VCC credentials
        try:
            token = vcc_client.get_access_token()
            if token:
                print("✓ VCC API authentication successful\n")
            else:
                print("✗ VCC API authentication failed - check credentials\n")
                return
        except Exception as e:
            print(f"✗ VCC API authentication error: {e}\n")
            return

        print("Starting collection loop (Press Ctrl+C to stop)...\n")

        while self.running:
            try:
                # Execute collection cycle
                success = self.collect_cycle()

                if not success:
                    print(f"⚠ Collection failed, retrying in {self.collection_interval} seconds...")

                # Wait for next cycle
                if self.running:
                    print(f"\n⏱ Waiting {self.collection_interval} seconds until next collection...")
                    time.sleep(self.collection_interval)

            except KeyboardInterrupt:
                print("\n⚠ Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                print(f"\n✗ Unexpected error: {e}")
                import traceback
                traceback.print_exc()

                if self.running:
                    print(f"Retrying in {self.collection_interval} seconds...")
                    time.sleep(self.collection_interval)

        print("\n" + "="*80)
        print("DATA COLLECTOR STOPPED")
        print("="*80)
        self.print_statistics()
        print("\nGoodbye!\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VCC Data Collector Service')
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Collection interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--realtime',
        action='store_true',
        help='Enable real-time WebSocket streaming (not yet implemented)'
    )
    parser.add_argument(
        '--storage-path',
        type=str,
        default='data/parquet',
        help='Path to store Parquet files (default: data/parquet)'
    )

    args = parser.parse_args()

    # Create and run collector
    collector = DataCollector(
        collection_interval=args.interval,
        realtime_mode=args.realtime,
        storage_path=args.storage_path
    )

    collector.run()


if __name__ == '__main__':
    main()
