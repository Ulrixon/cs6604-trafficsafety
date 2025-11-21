"""
Validation Script for Dual-Write Migration

Compares data between Parquet storage and PostgreSQL database to ensure
consistency during the dual-write migration phase.

Usage:
    python scripts/validate_dual_write.py [--detailed] [--date YYYY-MM-DD]
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from sqlalchemy import text

from app.services.parquet_storage import ParquetStorage
from app.db.connection import init_db, db_session
from app.core.config import settings


class DualWriteValidator:
    """Validates data consistency between Parquet and PostgreSQL"""

    def __init__(self, storage_path: str = "data/parquet"):
        """Initialize validator"""
        self.storage = ParquetStorage(storage_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # Initialize database
        init_db(
            database_url=settings.DATABASE_URL,
            pool_size=2,
            max_overflow=0
        )

    def validate_row_counts(self, target_date: date) -> Tuple[int, int]:
        """
        Compare row counts between Parquet and PostgreSQL.

        Args:
            target_date: Date to check

        Returns:
            Tuple of (parquet_count, db_count)
        """
        print(f"\n{'='*80}")
        print(f"VALIDATING ROW COUNTS FOR {target_date}")
        print(f"{'='*80}")

        # Count Parquet rows
        try:
            parquet_df = self.storage.load_indices(
                start_date=target_date,
                end_date=target_date
            )
            parquet_count = len(parquet_df)
            print(f"✓ Parquet: {parquet_count:,} records")
        except Exception as e:
            self.errors.append(f"Failed to load Parquet data: {e}")
            parquet_count = 0
            print(f"✗ Parquet load failed: {e}")

        # Count PostgreSQL rows
        try:
            with db_session() as session:
                query = text("""
                    SELECT COUNT(*) as count
                    FROM safety_indices_realtime
                    WHERE timestamp::date = :target_date
                """)
                result = session.execute(query, {"target_date": target_date})
                db_count = result.fetchone()[0]
                print(f"✓ PostgreSQL: {db_count:,} records")
        except Exception as e:
            self.errors.append(f"Failed to query PostgreSQL: {e}")
            db_count = 0
            print(f"✗ PostgreSQL query failed: {e}")

        # Compare
        if parquet_count != db_count:
            diff = abs(parquet_count - db_count)
            pct = (diff / max(parquet_count, db_count, 1)) * 100
            self.warnings.append(
                f"Row count mismatch: Parquet={parquet_count}, PostgreSQL={db_count} "
                f"(diff={diff}, {pct:.1f}%)"
            )
            print(f"\n⚠ Row count mismatch: {diff} records ({pct:.1f}% difference)")
        else:
            print(f"\n✓ Row counts match: {parquet_count} records")

        return parquet_count, db_count

    def validate_sample_data(
        self,
        target_date: date,
        sample_size: int = 100
    ) -> Dict[str, float]:
        """
        Compare sample data values between Parquet and PostgreSQL.

        Args:
            target_date: Date to check
            sample_size: Number of samples to compare

        Returns:
            Dictionary with comparison statistics
        """
        print(f"\n{'='*80}")
        print(f"VALIDATING SAMPLE DATA (n={sample_size})")
        print(f"{'='*80}")

        # Load Parquet data
        try:
            parquet_df = self.storage.load_indices(
                start_date=target_date,
                end_date=target_date
            )
            if parquet_df.empty:
                self.warnings.append("No Parquet data to compare")
                return {}

            # Sample rows
            sample_size = min(sample_size, len(parquet_df))
            parquet_sample = parquet_df.sample(n=sample_size).copy()
            parquet_sample['timestamp'] = pd.to_datetime(parquet_sample['time_15min'])

            print(f"✓ Loaded {len(parquet_sample)} Parquet samples")
        except Exception as e:
            self.errors.append(f"Failed to load Parquet samples: {e}")
            return {}

        # Load matching PostgreSQL data
        try:
            with db_session() as session:
                # Get data for same timestamps
                timestamps = parquet_sample['timestamp'].tolist()
                timestamp_strs = [ts.strftime('%Y-%m-%d %H:%M:%S') for ts in timestamps]

                query = text("""
                    SELECT
                        intersection_id,
                        timestamp,
                        combined_index,
                        combined_index_eb,
                        traffic_volume
                    FROM safety_indices_realtime
                    WHERE timestamp::date = :target_date
                    ORDER BY timestamp
                """)

                result = session.execute(query, {"target_date": target_date})
                db_df = pd.DataFrame(result.fetchall(), columns=result.keys())
                db_df['timestamp'] = pd.to_datetime(db_df['timestamp'])

                print(f"✓ Loaded {len(db_df)} PostgreSQL records")
        except Exception as e:
            self.errors.append(f"Failed to load PostgreSQL samples: {e}")
            return {}

        # Merge and compare
        merged = pd.merge(
            parquet_sample,
            db_df,
            left_on=['intersection', 'timestamp'],
            right_on=['intersection_id', 'timestamp'],
            suffixes=('_parquet', '_db'),
            how='inner'
        )

        if len(merged) == 0:
            self.warnings.append("No matching timestamps found for comparison")
            return {}

        print(f"✓ Matched {len(merged)} records for comparison")

        # Calculate differences
        stats = {}

        # Combined Index comparison
        if 'Combined_Index' in merged.columns and 'combined_index' in merged.columns:
            diff = merged['Combined_Index'] - merged['combined_index']
            stats['combined_index'] = {
                'mean_diff': diff.mean(),
                'max_diff': diff.abs().max(),
                'matches': (diff.abs() < 0.01).sum(),
                'total': len(diff)
            }

            print(f"\nCombined Index:")
            print(f"  Mean difference: {stats['combined_index']['mean_diff']:.6f}")
            print(f"  Max difference: {stats['combined_index']['max_diff']:.6f}")
            print(f"  Exact matches: {stats['combined_index']['matches']}/{stats['combined_index']['total']}")

            if stats['combined_index']['max_diff'] > 1.0:
                self.errors.append(
                    f"Large difference in Combined_Index: {stats['combined_index']['max_diff']:.2f}"
                )

        # Traffic volume comparison
        if 'traffic_volume_parquet' in merged.columns and 'traffic_volume_db' in merged.columns:
            diff = merged['traffic_volume_parquet'] - merged['traffic_volume_db']
            stats['traffic_volume'] = {
                'mean_diff': diff.mean(),
                'max_diff': diff.abs().max(),
                'matches': (diff == 0).sum(),
                'total': len(diff)
            }

            print(f"\nTraffic Volume:")
            print(f"  Mean difference: {stats['traffic_volume']['mean_diff']:.2f}")
            print(f"  Max difference: {stats['traffic_volume']['max_diff']:.0f}")
            print(f"  Exact matches: {stats['traffic_volume']['matches']}/{stats['traffic_volume']['total']}")

        return stats

    def validate_latest_data(self) -> bool:
        """
        Validate the most recent data points.

        Returns:
            True if validation passes
        """
        print(f"\n{'='*80}")
        print("VALIDATING LATEST DATA")
        print(f"{'='*80}")

        # Get latest timestamp from Parquet
        try:
            parquet_df = self.storage.load_indices(
                start_date=date.today() - timedelta(days=1),
                end_date=date.today()
            )

            if parquet_df.empty:
                self.warnings.append("No recent Parquet data found")
                return False

            latest_parquet = pd.to_datetime(parquet_df['time_15min']).max()
            print(f"✓ Latest Parquet timestamp: {latest_parquet}")
        except Exception as e:
            self.errors.append(f"Failed to get latest Parquet data: {e}")
            return False

        # Get latest timestamp from PostgreSQL
        try:
            with db_session() as session:
                query = text("SELECT MAX(timestamp) as latest FROM safety_indices_realtime")
                result = session.execute(query)
                latest_db = result.fetchone()[0]

                if latest_db:
                    latest_db = latest_db.replace(tzinfo=None)  # Remove timezone for comparison
                    print(f"✓ Latest PostgreSQL timestamp: {latest_db}")
                else:
                    self.warnings.append("No data in PostgreSQL")
                    return False
        except Exception as e:
            self.errors.append(f"Failed to get latest PostgreSQL data: {e}")
            return False

        # Compare timestamps
        time_diff = abs((latest_parquet - latest_db).total_seconds())

        if time_diff > 300:  # More than 5 minutes difference
            self.errors.append(
                f"Latest timestamps differ by {time_diff/60:.1f} minutes: "
                f"Parquet={latest_parquet}, DB={latest_db}"
            )
            return False
        else:
            print(f"\n✓ Latest timestamps match (within {time_diff:.0f} seconds)")
            return True

    def print_report(self):
        """Print validation report"""
        print(f"\n{'='*80}")
        print("VALIDATION REPORT")
        print(f"{'='*80}")

        if not self.errors and not self.warnings:
            print("✓ All validations passed!")
            print("\nDual-write is working correctly.")
        else:
            if self.errors:
                print(f"\n✗ {len(self.errors)} ERROR(S) FOUND:")
                for i, error in enumerate(self.errors, 1):
                    print(f"  {i}. {error}")

            if self.warnings:
                print(f"\n⚠ {len(self.warnings)} WARNING(S):")
                for i, warning in enumerate(self.warnings, 1):
                    print(f"  {i}. {warning}")

        print(f"{'='*80}\n")

        return len(self.errors) == 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate dual-write data consistency")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Run detailed validation with sample data comparison"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date to validate (YYYY-MM-DD), defaults to today"
    )

    args = parser.parse_args()

    # Parse target date
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    print("\n" + "="*80)
    print("DUAL-WRITE VALIDATION SCRIPT")
    print("="*80)
    print(f"Target Date: {target_date}")
    print(f"Detailed Mode: {args.detailed}")
    print("="*80)

    # Initialize validator
    validator = DualWriteValidator()

    # Run validations
    try:
        # 1. Validate row counts
        parquet_count, db_count = validator.validate_row_counts(target_date)

        # 2. Validate latest data
        validator.validate_latest_data()

        # 3. Validate sample data (if detailed mode)
        if args.detailed and parquet_count > 0 and db_count > 0:
            validator.validate_sample_data(target_date, sample_size=100)

        # Print report
        success = validator.print_report()

        # Exit code
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n✗ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
