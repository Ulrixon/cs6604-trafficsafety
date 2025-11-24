"""
VCC (Virginia Connected Corridors) data source plugin.

This plugin wraps the existing VCC client and feature engineering code,
providing VCC traffic data (BSM, PSM, conflicts) through the plugin interface.
"""

from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import logging
import time

from .base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from .exceptions import PluginCollectionError, PluginConfigError
from ..services.vcc_client import VCCClient

logger = logging.getLogger(__name__)


class VCCPlugin(DataSourcePlugin):
    """
    VCC data source plugin for traffic safety data.

    Collects Basic Safety Messages (BSM), Pedestrian Safety Messages (PSM),
    and MapData from VCC API, then extracts traffic safety features.

    Features provided:
    - vcc_conflict_count: Number of detected vehicle-vehicle and VRU-vehicle conflicts
    - vcc_ttc_min: Minimum time-to-collision across all detected conflicts
    - vcc_proximity_score: Proximity hazard score (0-1 scale)
    - vcc_speed_variance: Variance in vehicle speeds (indicator of unsafe behavior)
    - vcc_acceleration_events: Count of hard braking/acceleration events
    """

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="vcc",
            version="1.0.0",
            description="Virginia Connected Corridors traffic data source",
            author="Traffic Safety Team",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.70)
        )

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize VCC plugin.

        Args:
            config: Configuration dictionary with keys:
                - base_url (str): VCC API base URL
                - client_id (str): OAuth2 client ID
                - client_secret (str): OAuth2 client secret
                - enabled (bool, optional): Whether plugin is enabled
                - weight (float, optional): Feature weight (0.0-1.0)
        """
        super().__init__(config)

        # Initialize VCC client
        self.client = VCCClient(
            base_url=config.get('base_url'),
            client_id=config.get('client_id'),
            client_secret=config.get('client_secret')
        )

    def _validate_config(self) -> None:
        """Validate VCC plugin configuration."""
        required_keys = ['base_url', 'client_id', 'client_secret']

        for key in required_keys:
            if key not in self.config or not self.config[key]:
                raise PluginConfigError(
                    self.metadata.name,
                    f"Missing required configuration key: '{key}'"
                )

        # Validate base_url format
        if not self.config['base_url'].startswith('http'):
            raise PluginConfigError(
                self.metadata.name,
                f"Invalid base_url: must start with http:// or https://"
            )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Collect VCC data and extract traffic features.

        Note: VCC API currently only provides "current" data, not historical queries.
        The start_time and end_time parameters are accepted for interface compatibility
        but may not be fully utilized until VCC API adds historical querying.

        Args:
            start_time: Start of collection window (for future historical queries)
            end_time: End of collection window (for future historical queries)

        Returns:
            DataFrame with columns:
            - timestamp: Observation timestamp
            - intersection_id: Intersection identifier
            - vcc_conflict_count: Number of conflicts (normalized 0-1)
            - vcc_ttc_min: Minimum TTC in seconds (normalized 0-1, inverted: low TTC = high risk)
            - vcc_proximity_score: Proximity hazard (0-1)
            - vcc_speed_variance: Speed variance (normalized 0-1)
            - vcc_acceleration_events: Acceleration events count (normalized 0-1)

        Raises:
            PluginCollectionError: If data collection fails
        """
        try:
            logger.debug(f"VCC plugin collecting data for {start_time} to {end_time}")

            # Fetch current BSM messages (vehicles)
            bsm_messages = self.client.get_bsm_current()
            logger.debug(f"Fetched {len(bsm_messages)} BSM messages")

            # Fetch current PSM messages (pedestrians/cyclists)
            psm_messages = self.client.get_psm_current()
            logger.debug(f"Fetched {len(psm_messages)} PSM messages")

            # Fetch MapData (intersection geometry)
            mapdata = self.client.get_mapdata()
            logger.debug(f"Fetched {len(mapdata)} MapData messages")

            # Check if we have data
            if not bsm_messages and not psm_messages:
                logger.warning("No BSM or PSM messages available from VCC API")
                return pd.DataFrame()

            # Extract features from raw messages
            # Note: This uses existing feature engineering code
            features = self._extract_features(bsm_messages, psm_messages, mapdata)

            if features.empty:
                logger.warning("Feature extraction returned no data")
                return pd.DataFrame()

            # Normalize features to 0-1 scale
            features = self._normalize_features(features)

            logger.info(f"VCC plugin collected {len(features)} feature rows")

            return features

        except Exception as e:
            logger.error(f"VCC plugin collection failed: {e}", exc_info=True)
            raise PluginCollectionError(
                self.metadata.name,
                f"Failed to collect VCC data: {str(e)}",
                original_error=e
            )

    def _extract_features(
        self,
        bsm_messages: List[Dict],
        psm_messages: List[Dict],
        mapdata: List[Dict]
    ) -> pd.DataFrame:
        """
        Extract traffic features from VCC messages.

        This is a simplified implementation. For production, this should
        integrate with the existing vcc_feature_engineering module.

        Args:
            bsm_messages: Basic Safety Messages (vehicles)
            psm_messages: Personal Safety Messages (VRUs)
            mapdata: Map data (intersection geometry)

        Returns:
            DataFrame with extracted features
        """
        # TODO: Integrate with existing feature engineering code
        # For now, return simplified mock data structure
        # In production, this should call:
        # - parse_vcc_bsm_message() for each BSM
        # - detect_vehicle_vehicle_conflicts()
        # - detect_vru_vehicle_conflicts()
        # - aggregate_features_to_interval()

        # Simplified placeholder implementation
        if not bsm_messages:
            return pd.DataFrame()

        # Extract basic features from BSM messages
        features = []
        current_time = datetime.now()

        # Group messages by intersection (simplified)
        # In production, use actual intersection_id from MapData
        intersection_id = "I-001"  # Placeholder

        # Calculate simple metrics
        num_vehicles = len(bsm_messages)
        num_pedestrians = len(psm_messages)

        # Extract speeds (if available in BSM)
        speeds = []
        for bsm in bsm_messages:
            try:
                bsm_json = bsm.get('bsmJson', {})
                core_data = bsm_json.get('coreData', {})
                speed = core_data.get('speed', 0)  # m/s
                speeds.append(speed)
            except:
                pass

        # Calculate features
        conflict_count = num_vehicles + num_pedestrians  # Simplified
        ttc_min = 5.0  # Placeholder, should be calculated from actual trajectories
        proximity_score = min(conflict_count / 10.0, 1.0)  # Simplified
        speed_variance = pd.Series(speeds).var() if speeds else 0.0
        accel_events = 0  # Placeholder, needs brake status analysis

        features.append({
            'timestamp': current_time,
            'intersection_id': intersection_id,
            'vcc_conflict_count_raw': conflict_count,
            'vcc_ttc_min_raw': ttc_min,
            'vcc_proximity_score_raw': proximity_score,
            'vcc_speed_variance_raw': speed_variance,
            'vcc_acceleration_events_raw': accel_events
        })

        return pd.DataFrame(features)

    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize VCC features to 0-1 scale.

        Normalization strategy:
        - Conflict count: 0 conflicts = 0.0, 20+ conflicts = 1.0
        - TTC (time-to-collision): 10+ seconds = 0.0 (safe), 0 seconds = 1.0 (collision)
        - Proximity score: Already 0-1 scale
        - Speed variance: 0 variance = 0.0, 100+ variance = 1.0
        - Acceleration events: 0 events = 0.0, 10+ events = 1.0

        Args:
            df: DataFrame with raw feature values

        Returns:
            DataFrame with normalized features (0-1 scale)
        """
        df = df.copy()

        # Conflict count: normalize to 0-1 (more conflicts = higher risk)
        if 'vcc_conflict_count_raw' in df.columns:
            df['vcc_conflict_count'] = (df['vcc_conflict_count_raw'] / 20.0).clip(0, 1)

        # TTC: normalize and invert (lower TTC = higher risk)
        if 'vcc_ttc_min_raw' in df.columns:
            # Invert: 10s TTC = 0.0 risk, 0s TTC = 1.0 risk
            df['vcc_ttc_min'] = 1.0 - (df['vcc_ttc_min_raw'] / 10.0).clip(0, 1)

        # Proximity score: already 0-1 scale
        if 'vcc_proximity_score_raw' in df.columns:
            df['vcc_proximity_score'] = df['vcc_proximity_score_raw'].clip(0, 1)

        # Speed variance: normalize (higher variance = higher risk)
        if 'vcc_speed_variance_raw' in df.columns:
            df['vcc_speed_variance'] = (df['vcc_speed_variance_raw'] / 100.0).clip(0, 1)

        # Acceleration events: normalize
        if 'vcc_acceleration_events_raw' in df.columns:
            df['vcc_acceleration_events'] = (df['vcc_acceleration_events_raw'] / 10.0).clip(0, 1)

        # Select final columns
        return df[[
            'timestamp',
            'intersection_id',
            'vcc_conflict_count',
            'vcc_ttc_min',
            'vcc_proximity_score',
            'vcc_speed_variance',
            'vcc_acceleration_events'
        ]]

    def get_features(self) -> List[str]:
        """Return list of feature names this plugin provides."""
        return [
            'vcc_conflict_count',
            'vcc_ttc_min',
            'vcc_proximity_score',
            'vcc_speed_variance',
            'vcc_acceleration_events'
        ]

    def health_check(self) -> PluginHealthStatus:
        """
        Verify VCC API is accessible.

        Checks:
        1. Can obtain OAuth2 access token
        2. API endpoint is reachable

        Returns:
            PluginHealthStatus with result and diagnostic info
        """
        start_time = time.time()

        try:
            # Test authentication
            logger.debug("VCC plugin: Testing authentication...")
            token = self.client.get_access_token()

            latency_ms = (time.time() - start_time) * 1000

            if token:
                return PluginHealthStatus(
                    healthy=True,
                    message="VCC API authentication successful",
                    last_check=datetime.now(),
                    latency_ms=latency_ms,
                    details={
                        'base_url': self.config['base_url'],
                        'token_obtained': True,
                        'token_length': len(token)
                    }
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message="Failed to obtain VCC API access token",
                    last_check=datetime.now(),
                    latency_ms=latency_ms,
                    details={
                        'base_url': self.config['base_url'],
                        'token_obtained': False
                    }
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            return PluginHealthStatus(
                healthy=False,
                message=f"VCC API error: {str(e)}",
                last_check=datetime.now(),
                latency_ms=latency_ms,
                details={
                    'base_url': self.config['base_url'],
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )


# Convenience function for creating VCC plugin from settings
def create_vcc_plugin_from_settings():
    """
    Create VCC plugin instance from application settings.

    Returns:
        VCCPlugin instance configured from settings

    Example:
        from app.core.config import settings
        from app.plugins.vcc_plugin import create_vcc_plugin_from_settings

        if settings.USE_VCC_PLUGIN:
            vcc_plugin = create_vcc_plugin_from_settings()
            registry.register('vcc', vcc_plugin)
    """
    from ..core.config import settings

    config = {
        'base_url': settings.VCC_BASE_URL,
        'client_id': settings.VCC_CLIENT_ID,
        'client_secret': settings.VCC_CLIENT_SECRET,
        'enabled': True,
        'weight': settings.VCC_PLUGIN_WEIGHT
    }

    return VCCPlugin(config)
