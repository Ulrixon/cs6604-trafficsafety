"""
GCP Cloud Storage service for archiving Parquet files.

Provides methods to upload, list, and download Parquet files from Google Cloud Storage
with proper directory structure and lifecycle management.
"""

import logging
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict
import os

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

logger = logging.getLogger(__name__)


class GCSStorage:
    """Google Cloud Storage client for Parquet file archival"""

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        """
        Initialize GCS storage client.

        Args:
            bucket_name: GCS bucket name (e.g., 'trafficsafety-prod-parquet')
            project_id: GCP project ID (optional, uses default from credentials)
        """
        self.bucket_name = bucket_name

        try:
            # Initialize client (uses GOOGLE_APPLICATION_CREDENTIALS env var)
            if project_id:
                self.client = storage.Client(project=project_id)
            else:
                self.client = storage.Client()

            # Get bucket reference
            self.bucket = self.client.bucket(bucket_name)

            logger.info(f"GCS Storage initialized: gs://{bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise

    def upload_parquet(
        self,
        local_path: Path,
        gcs_path: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload a Parquet file to GCS.

        Args:
            local_path: Path to local Parquet file
            gcs_path: Destination path in GCS (e.g., 'raw/bsm/2025/11/21/bsm_20251121.parquet')
            metadata: Optional metadata dictionary to attach to blob

        Returns:
            Full GCS URI (e.g., 'gs://bucket-name/path/to/file.parquet')

        Example:
            ```python
            gcs = GCSStorage('my-bucket')
            uri = gcs.upload_parquet(
                local_path=Path('/tmp/data.parquet'),
                gcs_path='raw/bsm/2025/11/21/bsm_20251121.parquet',
                metadata={'source': 'vcc', 'intersection': '0'}
            )
            ```
        """
        try:
            blob = self.bucket.blob(gcs_path)

            # Add metadata if provided
            if metadata:
                blob.metadata = metadata

            # Upload file
            blob.upload_from_filename(str(local_path))

            gs_uri = f"gs://{self.bucket_name}/{gcs_path}"
            logger.info(f"Uploaded: {local_path.name} → {gs_uri}")

            return gs_uri

        except GoogleCloudError as e:
            logger.error(f"GCS upload failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Upload error: {e}")
            raise

    def upload_bsm_batch(
        self,
        local_path: Path,
        target_date: date,
        intersection_id: Optional[int] = None
    ) -> str:
        """
        Upload BSM Parquet file to GCS with proper directory structure.

        Directory structure: raw/bsm/YYYY/MM/DD/bsm_YYYYMMDD_HHMMSS.parquet

        Args:
            local_path: Path to local BSM Parquet file
            target_date: Date of the data
            intersection_id: Optional intersection ID for metadata

        Returns:
            GCS URI
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gcs_path = (
            f"raw/bsm/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.day:02d}/bsm_{target_date.strftime('%Y%m%d')}_{timestamp}.parquet"
        )

        metadata = {
            'data_type': 'bsm',
            'collection_date': target_date.isoformat(),
            'upload_timestamp': datetime.now().isoformat()
        }

        if intersection_id is not None:
            metadata['intersection_id'] = str(intersection_id)

        return self.upload_parquet(local_path, gcs_path, metadata)

    def upload_psm_batch(
        self,
        local_path: Path,
        target_date: date,
        intersection_id: Optional[int] = None
    ) -> str:
        """
        Upload PSM Parquet file to GCS.

        Directory structure: raw/psm/YYYY/MM/DD/psm_YYYYMMDD_HHMMSS.parquet
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gcs_path = (
            f"raw/psm/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.day:02d}/psm_{target_date.strftime('%Y%m%d')}_{timestamp}.parquet"
        )

        metadata = {
            'data_type': 'psm',
            'collection_date': target_date.isoformat(),
            'upload_timestamp': datetime.now().isoformat()
        }

        if intersection_id is not None:
            metadata['intersection_id'] = str(intersection_id)

        return self.upload_parquet(local_path, gcs_path, metadata)

    def upload_mapdata_batch(
        self,
        local_path: Path,
        target_date: date,
        intersection_id: Optional[int] = None
    ) -> str:
        """
        Upload MapData Parquet file to GCS.

        Directory structure: raw/mapdata/YYYY/MM/DD/mapdata_YYYYMMDD_HHMMSS.parquet
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gcs_path = (
            f"raw/mapdata/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.day:02d}/mapdata_{target_date.strftime('%Y%m%d')}_{timestamp}.parquet"
        )

        metadata = {
            'data_type': 'mapdata',
            'collection_date': target_date.isoformat(),
            'upload_timestamp': datetime.now().isoformat()
        }

        if intersection_id is not None:
            metadata['intersection_id'] = str(intersection_id)

        return self.upload_parquet(local_path, gcs_path, metadata)

    def upload_weather_observations(
        self,
        local_path: Path,
        target_date: date,
        station_id: Optional[str] = None
    ) -> str:
        """
        Upload weather observations Parquet file to GCS.

        Directory structure: weather/YYYY/MM/DD/weather_YYYYMMDD.parquet

        Args:
            local_path: Path to local weather Parquet file
            target_date: Date of the weather observations
            station_id: Optional weather station ID for metadata

        Returns:
            GCS URI

        Example:
            ```python
            gcs = GCSStorage('trafficsafety-prod-parquet')
            uri = gcs.upload_weather_observations(
                local_path=Path('/tmp/weather_2024-11-21.parquet'),
                target_date=date(2024, 11, 21),
                station_id='KRIC'
            )
            # Returns: gs://bucket/weather/2024/11/21/weather_20241121.parquet
            ```
        """
        gcs_path = (
            f"weather/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.day:02d}/weather_{target_date.strftime('%Y%m%d')}.parquet"
        )

        metadata = {
            'data_type': 'weather',
            'collection_date': target_date.isoformat(),
            'upload_timestamp': datetime.now().isoformat()
        }

        if station_id:
            metadata['station_id'] = station_id

        return self.upload_parquet(local_path, gcs_path, metadata)

    def upload_indices(
        self,
        local_path: Path,
        target_date: date,
        intersection_id: Optional[int] = None
    ) -> str:
        """
        Upload safety indices Parquet file to GCS.

        Directory structure: processed/indices/YYYY/MM/DD/indices_YYYYMMDD_HHMMSS.parquet
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gcs_path = (
            f"processed/indices/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.day:02d}/indices_{target_date.strftime('%Y%m%d')}_{timestamp}.parquet"
        )

        metadata = {
            'data_type': 'indices',
            'collection_date': target_date.isoformat(),
            'upload_timestamp': datetime.now().isoformat()
        }

        if intersection_id is not None:
            metadata['intersection_id'] = str(intersection_id)

        return self.upload_parquet(local_path, gcs_path, metadata)

    def list_files(
        self,
        prefix: str,
        max_results: Optional[int] = None
    ) -> List[Dict[str, any]]:
        """
        List files in GCS bucket with given prefix.

        Args:
            prefix: Path prefix (e.g., 'raw/bsm/2025/11/')
            max_results: Maximum number of results to return

        Returns:
            List of dictionaries with file information:
            [
                {
                    'name': 'raw/bsm/2025/11/21/bsm_20251121.parquet',
                    'size': 1024,
                    'updated': datetime,
                    'storage_class': 'STANDARD'
                },
                ...
            ]
        """
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                max_results=max_results
            )

            files = []
            for blob in blobs:
                files.append({
                    'name': blob.name,
                    'size': blob.size,
                    'updated': blob.updated,
                    'storage_class': blob.storage_class,
                    'metadata': blob.metadata or {}
                })

            logger.info(f"Listed {len(files)} files with prefix: {prefix}")
            return files

        except GoogleCloudError as e:
            logger.error(f"Failed to list files: {e}")
            raise

    def download_parquet(
        self,
        gcs_path: str,
        local_path: Path
    ) -> Path:
        """
        Download Parquet file from GCS to local filesystem.

        Args:
            gcs_path: Path in GCS (e.g., 'raw/bsm/2025/11/21/file.parquet')
            local_path: Destination path on local filesystem

        Returns:
            Path to downloaded file
        """
        try:
            blob = self.bucket.blob(gcs_path)

            # Create parent directories if needed
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            blob.download_to_filename(str(local_path))

            logger.info(f"Downloaded: gs://{self.bucket_name}/{gcs_path} → {local_path}")
            return local_path

        except NotFound:
            logger.error(f"File not found in GCS: {gcs_path}")
            raise
        except GoogleCloudError as e:
            logger.error(f"GCS download failed: {e}")
            raise

    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.

        Args:
            gcs_path: Path in GCS

        Returns:
            True if file exists, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    def get_file_info(self, gcs_path: str) -> Optional[Dict]:
        """
        Get metadata and information about a file in GCS.

        Args:
            gcs_path: Path in GCS

        Returns:
            Dictionary with file information or None if not found
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.reload()  # Fetch metadata from GCS

            return {
                'name': blob.name,
                'size': blob.size,
                'created': blob.time_created,
                'updated': blob.updated,
                'storage_class': blob.storage_class,
                'metadata': blob.metadata or {},
                'content_type': blob.content_type
            }
        except NotFound:
            return None
        except GoogleCloudError as e:
            logger.error(f"Error getting file info: {e}")
            return None

    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS.

        Args:
            gcs_path: Path in GCS

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted: gs://{self.bucket_name}/{gcs_path}")
            return True
        except NotFound:
            logger.warning(f"File not found for deletion: {gcs_path}")
            return False
        except GoogleCloudError as e:
            logger.error(f"Error deleting file: {e}")
            return False


def test_gcs_connection(bucket_name: str, project_id: Optional[str] = None) -> bool:
    """
    Test GCS connection and permissions.

    Args:
        bucket_name: GCS bucket name
        project_id: Optional GCP project ID

    Returns:
        True if connection successful and bucket is accessible
    """
    try:
        gcs = GCSStorage(bucket_name, project_id)

        # Test bucket access by listing (limit to 1 result)
        files = gcs.list_files(prefix='', max_results=1)

        logger.info(f"✓ GCS connection test successful: gs://{bucket_name}")
        return True

    except Exception as e:
        logger.error(f"✗ GCS connection test failed: {e}")
        return False
