"""
Multi-source data collection service using plugin architecture.

Orchestrates data collection from multiple sources (VCC, Weather, etc.) in parallel,
stores results in triple-write architecture (PostgreSQL + Parquet + GCS), and
provides unified data for safety index calculation.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd

from app.plugins import PluginRegistry, create_vcc_plugin_from_settings, create_weather_plugin_from_settings
from app.services.db_service import (
    insert_weather_observations_batch,
    WeatherObservationRecord
)
from app.services.parquet_storage import parquet_storage
from app.services.gcs_storage import GCSStorage
from app.core.config import settings

logger = logging.getLogger(__name__)


class MultiSourceDataCollector:
    """
    Orchestrates multi-source data collection using plugin architecture.

    Features:
    - Parallel data collection from all enabled plugins
    - Triple-write storage (PostgreSQL + Parquet + GCS)
    - Unified data merging for safety index calculation
    - Graceful failure handling (one source fails, others continue)
    """

    def __init__(self, enable_gcs: bool = None):
        """
        Initialize multi-source data collector.

        Args:
            enable_gcs: Whether to enable GCS archiving (default: from settings)
        """
        # Initialize plugin registry
        self.registry = PluginRegistry()

        # Register plugins based on settings
        self._register_plugins()

        # GCS storage (optional)
        self.enable_gcs = enable_gcs if enable_gcs is not None else settings.ENABLE_GCS_UPLOAD
        self.gcs_storage = None
        if self.enable_gcs and settings.GCS_BUCKET_NAME:
            try:
                self.gcs_storage = GCSStorage(
                    bucket_name=settings.GCS_BUCKET_NAME,
                    project_id=settings.GCS_PROJECT_ID
                )
                logger.info(f"GCS storage initialized: gs://{settings.GCS_BUCKET_NAME}")
            except Exception as e:
                logger.warning(f"GCS storage initialization failed (continuing without GCS): {e}")
                self.gcs_storage = None

        logger.info(f"MultiSourceDataCollector initialized with {self.registry.count()} plugins")

    def _register_plugins(self):
        """Register all enabled plugins from settings."""
        # VCC Plugin
        if settings.USE_VCC_PLUGIN:
            try:
                vcc_plugin = create_vcc_plugin_from_settings()
                self.registry.register('vcc', vcc_plugin)
                logger.info("Registered VCC plugin")
            except Exception as e:
                logger.error(f"Failed to register VCC plugin: {e}")

        # Weather Plugin
        if settings.ENABLE_WEATHER_PLUGIN:
            try:
                weather_plugin = create_weather_plugin_from_settings()
                self.registry.register('weather', weather_plugin)
                logger.info("Registered Weather plugin")
            except Exception as e:
                logger.error(f"Failed to register Weather plugin: {e}")

        # Additional plugins can be registered here
        # Example:
        # if settings.ENABLE_CRASH_PLUGIN:
        #     crash_plugin = create_crash_plugin_from_settings()
        #     self.registry.register('crash', crash_plugin)

    def collect_all(
        self,
        start_time: datetime,
        end_time: datetime,
        fail_fast: bool = False
    ) -> pd.DataFrame:
        """
        Collect data from all enabled plugins in parallel.

        Args:
            start_time: Start of collection window
            end_time: End of collection window
            fail_fast: If True, raise on first plugin failure. If False, continue with other plugins.

        Returns:
            Merged DataFrame with data from all plugins (outer join on timestamp)

        Example:
            ```python
            collector = MultiSourceDataCollector()
            start = datetime(2024, 11, 21, 10, 0)
            end = datetime(2024, 11, 21, 10, 15)
            data = collector.collect_all(start, end)
            # Returns DataFrame with columns from all plugins:
            # timestamp, vcc_conflict_count, vcc_ttc_min, ...
            # weather_precipitation, weather_visibility, ...
            ```
        """
        logger.info(f"Collecting data from {self.registry.count()} plugins: {start_time} to {end_time}")

        # Collect from all plugins (in parallel)
        merged_data = self.registry.collect_all(start_time, end_time, fail_fast=fail_fast)

        logger.info(f"Collected {len(merged_data)} rows from all plugins")

        return merged_data

    def collect_and_store(
        self,
        start_time: datetime,
        end_time: datetime,
        store_postgresql: bool = True,
        store_parquet: bool = True,
        store_gcs: bool = None
    ) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Collect data from all plugins and store in triple-write architecture.

        Args:
            start_time: Start of collection window
            end_time: End of collection window
            store_postgresql: Write to PostgreSQL
            store_parquet: Write to Parquet files
            store_gcs: Upload to GCS (default: self.enable_gcs)

        Returns:
            Tuple of (collected_data_df, storage_paths_dict)

        Example:
            ```python
            collector = MultiSourceDataCollector()
            data, paths = collector.collect_and_store(
                start_time=datetime(2024, 11, 21, 10, 0),
                end_time=datetime(2024, 11, 21, 10, 15)
            )
            print(f"Stored to: {paths}")
            # {'postgresql': 'weather_observations (15 rows)',
            #  'parquet': '/data/parquet/weather/weather_2024-11-21.parquet',
            #  'gcs': 'gs://bucket/weather/2024/11/21/weather_20241121.parquet'}
            ```
        """
        storage_paths = {}

        # Collect from all plugins
        data = self.collect_all(start_time, end_time, fail_fast=False)

        if data.empty:
            logger.warning("No data collected from any plugin")
            return data, storage_paths

        # Store weather data (if weather plugin enabled)
        if 'weather_precipitation' in data.columns:
            weather_rows = self._store_weather_data(
                data,
                store_postgresql=store_postgresql,
                store_parquet=store_parquet,
                store_gcs=store_gcs if store_gcs is not None else self.enable_gcs
            )
            if weather_rows:
                storage_paths.update(weather_rows)

        # Store VCC data (if VCC plugin enabled)
        # VCC data storage would go here (using existing VCC storage methods)
        # For now, VCC plugin just returns features, not raw messages

        logger.info(f"Data collection and storage complete. Paths: {storage_paths}")

        return data, storage_paths

    def _store_weather_data(
        self,
        data: pd.DataFrame,
        store_postgresql: bool,
        store_parquet: bool,
        store_gcs: bool
    ) -> Dict[str, str]:
        """
        Store weather data in triple-write architecture.

        Args:
            data: DataFrame with weather columns
            store_postgresql: Write to PostgreSQL
            store_parquet: Write to Parquet
            store_gcs: Upload to GCS

        Returns:
            Dict of storage paths
        """
        paths = {}

        # Extract weather columns
        weather_cols = ['timestamp']
        for col in data.columns:
            if col.startswith('weather_'):
                weather_cols.append(col)

        if len(weather_cols) == 1:
            logger.debug("No weather data to store")
            return paths

        weather_data = data[weather_cols].copy()

        # Determine station_id (should be in config, but default to KRIC)
        station_id = settings.WEATHER_STATION_ID if hasattr(settings, 'WEATHER_STATION_ID') else 'KRIC'

        # 1. PostgreSQL storage
        if store_postgresql and settings.USE_POSTGRESQL:
            try:
                records = self._convert_weather_to_records(weather_data, station_id)
                count = insert_weather_observations_batch(records)
                paths['postgresql'] = f"weather_observations ({count} rows)"
                logger.info(f"Stored {count} weather observations to PostgreSQL")
            except Exception as e:
                logger.error(f"Failed to store weather data to PostgreSQL: {e}")

        # 2. Parquet storage
        if store_parquet:
            try:
                # Rename columns for Parquet storage
                parquet_data = weather_data.rename(columns={'timestamp': 'observation_time'}).copy()
                parquet_data['station_id'] = station_id

                # Determine target date
                target_date = pd.to_datetime(parquet_data['observation_time'].iloc[0]).date()

                filepath = parquet_storage.save_weather_observations(parquet_data, target_date)
                paths['parquet'] = filepath
                logger.info(f"Saved weather data to Parquet: {filepath}")
            except Exception as e:
                logger.error(f"Failed to store weather data to Parquet: {e}")

        # 3. GCS storage
        if store_gcs and self.gcs_storage:
            try:
                # Use Parquet file if available
                if 'parquet' in paths:
                    target_date = pd.to_datetime(weather_data['timestamp'].iloc[0]).date()
                    gcs_uri = self.gcs_storage.upload_weather_observations(
                        local_path=Path(paths['parquet']),
                        target_date=target_date,
                        station_id=station_id
                    )
                    paths['gcs'] = gcs_uri
                    logger.info(f"Uploaded weather data to GCS: {gcs_uri}")
            except Exception as e:
                logger.error(f"Failed to upload weather data to GCS: {e}")

        return paths

    def _convert_weather_to_records(
        self,
        weather_df: pd.DataFrame,
        station_id: str
    ) -> List[WeatherObservationRecord]:
        """
        Convert weather DataFrame to database records.

        Args:
            weather_df: DataFrame with weather columns
            station_id: Weather station ID

        Returns:
            List of WeatherObservationRecord
        """
        records = []

        for _, row in weather_df.iterrows():
            record = WeatherObservationRecord(
                station_id=station_id,
                observation_time=pd.to_datetime(row['timestamp']),
                temperature_normalized=row.get('weather_temperature'),
                precipitation_normalized=row.get('weather_precipitation'),
                visibility_normalized=row.get('weather_visibility'),
                wind_speed_normalized=row.get('weather_wind_speed')
            )
            records.append(record)

        return records

    def health_check_all(self) -> Dict[str, Dict]:
        """
        Run health checks on all registered plugins.

        Returns:
            Dictionary mapping plugin name to health status dict

        Example:
            ```python
            collector = MultiSourceDataCollector()
            health = collector.health_check_all()
            print(health)
            # {
            #   'vcc': {'healthy': True, 'message': 'VCC API accessible', ...},
            #   'weather': {'healthy': True, 'message': 'Station KRIC accessible', ...}
            # }
            ```
        """
        return self.registry.health_check_all()

    def get_plugin_info(self) -> Dict[str, Dict]:
        """
        Get information about all registered plugins.

        Returns:
            Dictionary mapping plugin name to metadata dict
        """
        plugins_info = {}

        for name in self.registry.list_plugins():
            plugin = self.registry.get_plugin(name)
            if plugin:
                plugins_info[name] = {
                    'name': plugin.metadata.name,
                    'version': plugin.metadata.version,
                    'description': plugin.metadata.description,
                    'enabled': plugin.metadata.enabled,
                    'weight': plugin.metadata.weight,
                    'features': plugin.get_features()
                }

        return plugins_info


# Global instance
multi_source_collector = MultiSourceDataCollector()
