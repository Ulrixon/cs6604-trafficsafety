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
import pandas as pd


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

        # Running flag
        self.running = False

        # Statistics
        self.stats = {
            'collections': 0,
            'total_bsm': 0,
            'total_psm': 0,
            'total_mapdata': 0,
            'last_collection': None,
            'errors': 0
        }

    def setup_signal_handlers(self):
        """Setup graceful shutdown on SIGINT/SIGTERM"""
        def shutdown_handler(signum, frame):
            print("\n\n⚠ Received shutdown signal, stopping collector...")
            self.running = False

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

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

            # Save raw data to Parquet
            print("\n[2/3] Saving data to Parquet storage...")
            if bsm_messages:
                self.storage.save_bsm_batch(bsm_messages)
                print(f"✓ Saved {len(bsm_messages)} BSM messages")

            if psm_messages:
                self.storage.save_psm_batch(psm_messages)
                print(f"✓ Saved {len(psm_messages)} PSM messages")

            if mapdata_list:
                self.storage.save_mapdata_batch(mapdata_list)
                print(f"✓ Saved {len(mapdata_list)} MapData messages")

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

                    # Save indices to Parquet
                    self.storage.save_indices(indices_df)
                    print(f"✓ Computed and saved safety indices for {len(indices_df)} intervals")

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
        if self.stats['last_collection']:
            print(f"Last Collection: {self.stats['last_collection'].strftime('%Y-%m-%d %H:%M:%S')}")
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
