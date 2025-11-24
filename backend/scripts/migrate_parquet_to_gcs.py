"""
Parquet to GCS Migration Script

Uploads all local Parquet files to Google Cloud Storage with proper directory structure.
Supports dry-run mode and resume capability.

Usage:
    python scripts/migrate_parquet_to_gcs.py [--dry-run] [--force] [--type TYPE]
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.gcs_storage import GCSStorage
from app.core.config import settings


class ParquetMigrator:
    """Migrates local Parquet files to GCS"""

    def __init__(
        self,
        local_base: Path,
        bucket_name: str,
        project_id: str = None,
        dry_run: bool = False
    ):
        """
        Initialize migrator.

        Args:
            local_base: Base path for local Parquet files
            bucket_name: GCS bucket name
            project_id: GCP project ID
            dry_run: If True, only simulate uploads
        """
        self.local_base = Path(local_base)
        self.dry_run = dry_run

        # Initialize GCS client
        if not dry_run:
            try:
                self.gcs = GCSStorage(bucket_name, project_id)
                print(f"✓ Connected to GCS bucket: {bucket_name}")
            except Exception as e:
                print(f"✗ Failed to connect to GCS: {e}")
                raise
        else:
            print(f"[DRY RUN] Would connect to bucket: {bucket_name}")

        # Migration state
        self.stats = {
            'total_files': 0,
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
            'total_bytes': 0
        }

        # State file for resume capability
        self.state_file = Path('migration_state.json')
        self.uploaded_files = self._load_state()

    def _load_state(self) -> set:
        """Load previously uploaded files from state file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    uploaded = set(state.get('uploaded_files', []))
                    print(f"✓ Loaded state: {len(uploaded)} files already uploaded")
                    return uploaded
            except Exception as e:
                print(f"⚠ Failed to load state file: {e}")
                return set()
        return set()

    def _save_state(self):
        """Save current upload state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'uploaded_files': list(self.uploaded_files),
                    'last_updated': datetime.now().isoformat(),
                    'stats': self.stats
                }, f, indent=2)
        except Exception as e:
            print(f"⚠ Failed to save state: {e}")

    def _extract_date_from_filename(self, filename: str) -> date:
        """
        Extract date from Parquet filename.

        Supports formats:
        - bsm_20251121_143000.parquet → 2025-11-21
        - indices_2025-11-21.parquet → 2025-11-21
        """
        try:
            # Try YYYYMMDD format
            if '_' in filename:
                date_part = filename.split('_')[1][:8]
                return datetime.strptime(date_part, '%Y%m%d').date()
            # Try YYYY-MM-DD format
            elif filename.startswith('indices_'):
                date_part = filename.replace('indices_', '').replace('.parquet', '')
                return datetime.strptime(date_part, '%Y-%m-%d').date()
        except Exception:
            pass

        # Default to today if can't extract
        return date.today()

    def migrate_bsm_files(self, force: bool = False) -> None:
        """Migrate BSM Parquet files"""
        print(f"\n{'='*80}")
        print("MIGRATING BSM FILES")
        print(f"{'='*80}")

        bsm_path = self.local_base / "raw" / "bsm"
        if not bsm_path.exists():
            print(f"⚠ No BSM directory found: {bsm_path}")
            return

        parquet_files = list(bsm_path.rglob("*.parquet"))
        print(f"Found {len(parquet_files)} BSM Parquet files")

        for parquet_file in parquet_files:
            self._migrate_file(parquet_file, 'bsm', force)

    def migrate_psm_files(self, force: bool = False) -> None:
        """Migrate PSM Parquet files"""
        print(f"\n{'='*80}")
        print("MIGRATING PSM FILES")
        print(f"{'='*80}")

        psm_path = self.local_base / "raw" / "psm"
        if not psm_path.exists():
            print(f"⚠ No PSM directory found: {psm_path}")
            return

        parquet_files = list(psm_path.rglob("*.parquet"))
        print(f"Found {len(parquet_files)} PSM Parquet files")

        for parquet_file in parquet_files:
            self._migrate_file(parquet_file, 'psm', force)

    def migrate_mapdata_files(self, force: bool = False) -> None:
        """Migrate MapData Parquet files"""
        print(f"\n{'='*80}")
        print("MIGRATING MAPDATA FILES")
        print(f"{'='*80}")

        mapdata_path = self.local_base / "raw" / "mapdata"
        if not mapdata_path.exists():
            print(f"⚠ No MapData directory found: {mapdata_path}")
            return

        parquet_files = list(mapdata_path.rglob("*.parquet"))
        print(f"Found {len(parquet_files)} MapData Parquet files")

        for parquet_file in parquet_files:
            self._migrate_file(parquet_file, 'mapdata', force)

    def migrate_indices_files(self, force: bool = False) -> None:
        """Migrate safety indices Parquet files"""
        print(f"\n{'='*80}")
        print("MIGRATING INDICES FILES")
        print(f"{'='*80}")

        indices_path = self.local_base / "indices"
        if not indices_path.exists():
            print(f"⚠ No indices directory found: {indices_path}")
            return

        parquet_files = list(indices_path.glob("*.parquet"))
        print(f"Found {len(parquet_files)} indices Parquet files")

        for parquet_file in parquet_files:
            self._migrate_file(parquet_file, 'indices', force)

    def _migrate_file(self, local_path: Path, data_type: str, force: bool = False):
        """
        Migrate a single Parquet file to GCS.

        Args:
            local_path: Local file path
            data_type: Type of data (bsm, psm, mapdata, indices)
            force: If True, upload even if already uploaded
        """
        self.stats['total_files'] += 1

        # Skip if already uploaded (unless force=True)
        file_key = str(local_path.relative_to(self.local_base))
        if file_key in self.uploaded_files and not force:
            print(f"  ⏭ Skipped (already uploaded): {local_path.name}")
            self.stats['skipped'] += 1
            return

        # Extract date from filename
        target_date = self._extract_date_from_filename(local_path.name)

        # Get file size
        file_size = local_path.stat().st_size
        self.stats['total_bytes'] += file_size

        # Upload based on type
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would upload: {local_path.name} ({file_size:,} bytes) → {data_type}/")
                self.stats['uploaded'] += 1
            else:
                if data_type == 'bsm':
                    gcs_uri = self.gcs.upload_bsm_batch(local_path, target_date)
                elif data_type == 'psm':
                    gcs_uri = self.gcs.upload_psm_batch(local_path, target_date)
                elif data_type == 'mapdata':
                    gcs_uri = self.gcs.upload_mapdata_batch(local_path, target_date)
                elif data_type == 'indices':
                    gcs_uri = self.gcs.upload_indices(local_path, target_date)
                else:
                    raise ValueError(f"Unknown data type: {data_type}")

                print(f"  ✓ Uploaded: {local_path.name} → {gcs_uri}")
                self.stats['uploaded'] += 1
                self.uploaded_files.add(file_key)

                # Save state every 10 files
                if self.stats['uploaded'] % 10 == 0:
                    self._save_state()

        except Exception as e:
            print(f"  ✗ Failed to upload {local_path.name}: {e}")
            self.stats['failed'] += 1

    def print_summary(self):
        """Print migration summary"""
        print(f"\n{'='*80}")
        print("MIGRATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total files found: {self.stats['total_files']}")
        print(f"  ✓ Uploaded: {self.stats['uploaded']}")
        print(f"  ⏭ Skipped: {self.stats['skipped']}")
        print(f"  ✗ Failed: {self.stats['failed']}")
        print(f"Total data: {self.stats['total_bytes'] / (1024**2):.2f} MB")
        print(f"{'='*80}\n")

        if not self.dry_run:
            # Save final state
            self._save_state()
            print(f"State saved to: {self.state_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Migrate local Parquet files to GCS")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without actually uploading"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force upload even if files were previously uploaded"
    )
    parser.add_argument(
        "--type",
        choices=['bsm', 'psm', 'mapdata', 'indices', 'all'],
        default='all',
        help="Type of files to migrate (default: all)"
    )
    parser.add_argument(
        "--local-path",
        type=str,
        default="data/parquet",
        help="Local Parquet storage path (default: data/parquet)"
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("PARQUET TO GCS MIGRATION")
    print("="*80)
    print(f"Local path: {args.local_path}")
    print(f"GCS bucket: {settings.GCS_BUCKET_NAME}")
    print(f"Dry run: {args.dry_run}")
    print(f"Force upload: {args.force}")
    print(f"Data type: {args.type}")
    print("="*80)

    # Validate settings
    if not settings.GCS_BUCKET_NAME:
        print("\n✗ ERROR: GCS_BUCKET_NAME not configured")
        print("Please set GCS_BUCKET_NAME in .env file")
        sys.exit(1)

    if not args.dry_run:
        # Check for GCP credentials
        gcp_creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not gcp_creds:
            print("\n✗ ERROR: GOOGLE_APPLICATION_CREDENTIALS not set")
            print("Please set environment variable pointing to service account key")
            sys.exit(1)

        if not Path(gcp_creds).exists():
            print(f"\n✗ ERROR: Credentials file not found: {gcp_creds}")
            sys.exit(1)

        print(f"✓ Using credentials: {gcp_creds}")

    # Initialize migrator
    try:
        migrator = ParquetMigrator(
            local_base=Path(args.local_path),
            bucket_name=settings.GCS_BUCKET_NAME,
            project_id=settings.GCS_PROJECT_ID or None,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"\n✗ Failed to initialize migrator: {e}")
        sys.exit(1)

    # Run migration
    try:
        if args.type in ['bsm', 'all']:
            migrator.migrate_bsm_files(force=args.force)

        if args.type in ['psm', 'all']:
            migrator.migrate_psm_files(force=args.force)

        if args.type in ['mapdata', 'all']:
            migrator.migrate_mapdata_files(force=args.force)

        if args.type in ['indices', 'all']:
            migrator.migrate_indices_files(force=args.force)

        # Print summary
        migrator.print_summary()

        # Exit with error code if any failures
        if migrator.stats['failed'] > 0:
            sys.exit(1)

        print("✓ Migration completed successfully")

    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        migrator.print_summary()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
