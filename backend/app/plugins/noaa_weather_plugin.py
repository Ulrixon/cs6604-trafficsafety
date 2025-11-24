"""
NOAA/NWS weather data source plugin.

This plugin collects weather observations from the NOAA/NWS API
and provides weather features for safety index calculation.

NOAA API Documentation: https://www.weather.gov/documentation/services-web-api
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import requests
import time
import logging

from .base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from .exceptions import PluginCollectionError, PluginConfigError

logger = logging.getLogger(__name__)


class NOAAWeatherPlugin(DataSourcePlugin):
    """
    NOAA/NWS weather data source plugin.

    Collects weather observations from NOAA API for a specified weather station.
    Free to use, no API key required (just User-Agent header).

    Features provided:
    - weather_precipitation: Precipitation amount (0=none, 1=heavy rain >20mm/hr)
    - weather_visibility: Visibility distance (0=good >10km, 1=zero visibility)
    - weather_wind_speed: Wind speed (0=calm, 1=high wind >25m/s)
    - weather_temperature: Temperature extremes (0=optimal 15-25°C, 1=extreme <0°C or >35°C)

    Station examples:
    - KRIC: Richmond International Airport, VA
    - KDCA: Reagan National Airport, Washington DC
    - Find more at: https://www.weather.gov/
    """

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="noaa_weather",
            version="1.0.0",
            description="NOAA/NWS weather observation data source",
            author="Traffic Safety Team",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.15)
        )

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize NOAA weather plugin.

        Args:
            config: Configuration dictionary with keys:
                - station_id (str): NOAA weather station ID (e.g., 'KRIC')
                - api_base (str, optional): API base URL (default: https://api.weather.gov)
                - user_agent (str, optional): User-Agent header for API requests
                - timeout (int, optional): Request timeout in seconds (default: 10)
                - retry_attempts (int, optional): Number of retry attempts (default: 3)
                - enabled (bool, optional): Whether plugin is enabled
                - weight (float, optional): Feature weight (0.0-1.0)
        """
        super().__init__(config)

        self.api_base = config.get('api_base', 'https://api.weather.gov')
        self.station_id = config['station_id']
        self.user_agent = config.get('user_agent', 'TrafficSafetyIndex/1.0 (https://github.com/traffic-safety)')
        self.timeout = config.get('timeout', 10)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 2)

    def _validate_config(self) -> None:
        """Validate NOAA weather plugin configuration."""
        if 'station_id' not in self.config or not self.config['station_id']:
            raise PluginConfigError(
                self.metadata.name,
                "Missing required configuration key: 'station_id'"
            )

        # Validate station_id format (should be 4 characters, starts with K for US)
        station_id = self.config['station_id']
        if not isinstance(station_id, str) or len(station_id) != 4:
            raise PluginConfigError(
                self.metadata.name,
                f"Invalid station_id format: '{station_id}' (should be 4 characters, e.g., 'KRIC')"
            )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Collect weather observations from NOAA API.

        Args:
            start_time: Start of collection window
            end_time: End of collection window

        Returns:
            DataFrame with columns:
            - timestamp: Observation timestamp
            - weather_precipitation: Precipitation risk (0-1)
            - weather_visibility: Visibility risk (0-1)
            - weather_wind_speed: Wind speed risk (0-1)
            - weather_temperature: Temperature risk (0-1)

        Raises:
            PluginCollectionError: If data collection fails
        """
        try:
            logger.debug(f"NOAA plugin collecting data for station {self.station_id} from {start_time} to {end_time}")

            # Fetch observations from NOAA API
            observations = self._fetch_observations(start_time, end_time)

            if not observations:
                logger.warning(f"No weather observations available for station {self.station_id}")
                return pd.DataFrame()

            # Parse observations into DataFrame
            df = self._parse_observations(observations)

            if df.empty:
                logger.warning("Weather observation parsing returned no data")
                return pd.DataFrame()

            # Normalize features to 0-1 scale
            df = self._normalize_features(df)

            logger.info(f"NOAA plugin collected {len(df)} weather observations")

            return df

        except Exception as e:
            logger.error(f"NOAA plugin collection failed: {e}", exc_info=True)
            raise PluginCollectionError(
                self.metadata.name,
                f"Failed to collect weather data: {str(e)}",
                original_error=e
            )

    def _fetch_observations(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Fetch observations from NOAA API with retry logic.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of observation dictionaries

        Raises:
            requests.RequestException: If all retry attempts fail
        """
        url = f"{self.api_base}/stations/{self.station_id}/observations"
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat()
        }

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Fetching NOAA observations (attempt {attempt + 1}/{self.retry_attempts})")

                response = self._make_request(url, params=params)
                response.raise_for_status()

                data = response.json()
                observations = data.get('features', [])

                logger.debug(f"Fetched {len(observations)} observations from NOAA API")

                return observations

            except requests.exceptions.RequestException as e:
                logger.warning(f"NOAA API request failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")

                if attempt < self.retry_attempts - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    delay = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # All retries exhausted
                    raise

    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """
        Make HTTP request to NOAA API with required headers.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Response object
        """
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/geo+json'
        }

        return requests.get(url, params=params, headers=headers, timeout=self.timeout)

    def _parse_observations(self, observations: List[Dict]) -> pd.DataFrame:
        """
        Parse NOAA API observations into DataFrame.

        NOAA API returns observations in GeoJSON format with nested structure:
        {
            "type": "Feature",
            "properties": {
                "timestamp": "2024-11-21T14:00:00Z",
                "temperature": {"value": 18.3, "unitCode": "wmoUnit:degC"},
                "precipitationLastHour": {"value": 0.0, "unitCode": "wmoUnit:mm"},
                ...
            }
        }

        Args:
            observations: List of observation features from NOAA API

        Returns:
            DataFrame with parsed weather data
        """
        data = []

        for obs in observations:
            props = obs.get('properties', {})

            # Extract timestamp
            timestamp = props.get('timestamp')
            if not timestamp:
                continue

            # Extract weather values (NOAA uses nested "value" objects)
            data.append({
                'timestamp': pd.to_datetime(timestamp),
                'temperature_c': self._extract_value(props.get('temperature')),
                'precipitation_mm': self._extract_value(props.get('precipitationLastHour')),
                'visibility_m': self._extract_value(props.get('visibility')),
                'wind_speed_ms': self._extract_value(props.get('windSpeed')),
                'wind_direction_deg': self._extract_value(props.get('windDirection')),
                'weather_condition': props.get('textDescription', 'Unknown')
            })

        return pd.DataFrame(data)

    def _extract_value(self, value_obj: Optional[Dict]) -> Optional[float]:
        """
        Extract numeric value from NOAA value object.

        NOAA API returns values as: {"value": 18.3, "unitCode": "wmoUnit:degC"}
        This function extracts just the numeric value.

        Args:
            value_obj: NOAA value object or None

        Returns:
            Numeric value or None
        """
        if value_obj is None:
            return None

        if isinstance(value_obj, dict):
            return value_obj.get('value')

        # If it's already a number, return it
        return value_obj

    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize weather features to 0-1 scale.

        Normalization strategy (higher value = higher risk):
        - Precipitation: 0 mm = 0.0 (no rain), 20+ mm/hour = 1.0 (heavy rain)
        - Visibility: 10+ km = 0.0 (good), 0 m = 1.0 (zero visibility) [inverted]
        - Wind speed: 0 m/s = 0.0 (calm), 25+ m/s = 1.0 (high wind)
        - Temperature: 20°C = 0.0 (optimal), <0°C or >35°C = 1.0 (extreme)

        Args:
            df: DataFrame with raw weather measurements

        Returns:
            DataFrame with normalized features (0-1 scale)
        """
        df = df.copy()

        # Precipitation: normalize to 0-1 (higher = worse)
        if 'precipitation_mm' in df.columns:
            df['precipitation_mm'] = df['precipitation_mm'].fillna(0)
            df['weather_precipitation'] = (df['precipitation_mm'] / 20.0).clip(0, 1)
        else:
            df['weather_precipitation'] = 0.0

        # Visibility: normalize and invert (lower visibility = higher risk)
        if 'visibility_m' in df.columns:
            df['visibility_m'] = df['visibility_m'].fillna(10000)
            # Invert: 10km visibility = 0.0 risk, 0m visibility = 1.0 risk
            df['weather_visibility'] = 1.0 - (df['visibility_m'] / 10000.0).clip(0, 1)
        else:
            df['weather_visibility'] = 0.0

        # Wind speed: normalize to 0-1 (higher = worse)
        if 'wind_speed_ms' in df.columns:
            df['wind_speed_ms'] = df['wind_speed_ms'].fillna(0)
            df['weather_wind_speed'] = (df['wind_speed_ms'] / 25.0).clip(0, 1)
        else:
            df['weather_wind_speed'] = 0.0

        # Temperature: U-shaped risk curve (extremes = worse)
        if 'temperature_c' in df.columns:
            df['temperature_c'] = df['temperature_c'].fillna(20)
            # Optimal temperature: 20°C = 0.0 risk
            # Risk increases as temperature moves away from 20°C
            optimal_temp = 20.0
            df['weather_temperature'] = df['temperature_c'].apply(
                lambda t: min(abs(t - optimal_temp) / 20.0, 1.0)
            )
        else:
            df['weather_temperature'] = 0.0

        # Select final columns
        return df[[
            'timestamp',
            'weather_precipitation',
            'weather_visibility',
            'weather_wind_speed',
            'weather_temperature'
        ]]

    def get_features(self) -> List[str]:
        """Return list of feature names this plugin provides."""
        return [
            'weather_precipitation',
            'weather_visibility',
            'weather_wind_speed',
            'weather_temperature'
        ]

    def health_check(self) -> PluginHealthStatus:
        """
        Verify NOAA API and weather station are accessible.

        Checks:
        1. NOAA API is reachable
        2. Weather station exists and is active

        Returns:
            PluginHealthStatus with result and diagnostic info
        """
        start_time = time.time()

        try:
            # Check station metadata endpoint
            logger.debug(f"NOAA plugin: Testing station {self.station_id} accessibility...")
            url = f"{self.api_base}/stations/{self.station_id}"
            response = self._make_request(url)

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                station_data = response.json()
                station_name = station_data.get('properties', {}).get('name', 'Unknown')

                return PluginHealthStatus(
                    healthy=True,
                    message=f"Station {self.station_id} ({station_name}) accessible",
                    last_check=datetime.now(),
                    latency_ms=latency_ms,
                    details={
                        'station_id': self.station_id,
                        'station_name': station_name,
                        'api_base': self.api_base
                    }
                )
            else:
                return PluginHealthStatus(
                    healthy=False,
                    message=f"Station returned HTTP {response.status_code}",
                    last_check=datetime.now(),
                    latency_ms=latency_ms,
                    details={
                        'station_id': self.station_id,
                        'status_code': response.status_code
                    }
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            return PluginHealthStatus(
                healthy=False,
                message=f"NOAA API error: {str(e)}",
                last_check=datetime.now(),
                latency_ms=latency_ms,
                details={
                    'station_id': self.station_id,
                    'api_base': self.api_base,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )


# Convenience function for creating weather plugin from settings
def create_weather_plugin_from_settings():
    """
    Create NOAA weather plugin instance from application settings.

    Returns:
        NOAAWeatherPlugin instance configured from settings

    Example:
        from app.core.config import settings
        from app.plugins.noaa_weather_plugin import create_weather_plugin_from_settings

        if settings.ENABLE_WEATHER_PLUGIN:
            weather_plugin = create_weather_plugin_from_settings()
            registry.register('weather', weather_plugin)
    """
    from ..core.config import settings

    config = {
        'station_id': settings.WEATHER_STATION_ID,
        'api_base': settings.WEATHER_API_BASE,
        'timeout': settings.WEATHER_API_TIMEOUT,
        'retry_attempts': settings.WEATHER_RETRY_ATTEMPTS,
        'enabled': True,
        'weight': settings.WEATHER_PLUGIN_WEIGHT
    }

    return NOAAWeatherPlugin(config)
