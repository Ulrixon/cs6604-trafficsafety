"""
Abstract base class for data source plugins.

All data sources that integrate with the Traffic Safety Index system
must implement this interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from pydantic import BaseModel, Field


class PluginMetadata(BaseModel):
    """
    Metadata describing a data source plugin.

    Attributes:
        name: Unique identifier for the plugin
        version: Plugin version (semantic versioning)
        description: Human-readable description
        author: Plugin author/maintainer
        enabled: Whether the plugin is active
        weight: Weight of this plugin's features in safety index (0.0-1.0)
    """

    name: str
    version: str = "1.0.0"
    description: str
    author: str = "Traffic Safety Team"
    enabled: bool = True
    weight: float = Field(ge=0.0, le=1.0, default=0.0)

    class Config:
        frozen = True  # Make immutable


class PluginHealthStatus(BaseModel):
    """
    Result of a plugin health check.

    Attributes:
        healthy: Whether the plugin is operational
        message: Human-readable status message
        last_check: Timestamp of the health check
        latency_ms: Response time in milliseconds (optional)
        details: Additional diagnostic information (optional)
    """

    healthy: bool
    message: str
    last_check: datetime
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class DataSourcePlugin(ABC):
    """
    Abstract base class for all data source plugins.

    All data sources (VCC, weather, crash data, etc.) must implement
    this interface to integrate with the Traffic Safety Index system.

    Example:
        class WeatherPlugin(DataSourcePlugin):
            def _init_metadata(self):
                return PluginMetadata(
                    name="weather",
                    description="Weather data from NOAA",
                    weight=0.15
                )

            def collect(self, start_time, end_time):
                # Fetch weather data
                return weather_dataframe

            def get_features(self):
                return ["precipitation", "visibility", "wind_speed"]

            def health_check(self):
                # Check API is accessible
                return PluginHealthStatus(healthy=True, ...)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plugin with configuration.

        Args:
            config: Plugin-specific configuration dictionary
                Common keys:
                - enabled (bool): Whether plugin is active
                - weight (float): Feature weight (0.0-1.0)
                - ... plugin-specific settings ...

        Raises:
            PluginConfigError: If configuration is invalid
        """
        self.config = config
        self.metadata = self._init_metadata()
        self._validate_config()

    @abstractmethod
    def _init_metadata(self) -> PluginMetadata:
        """
        Return plugin metadata.

        This method must be implemented by each plugin to provide
        identifying information.

        Returns:
            PluginMetadata instance with name, version, description, etc.

        Example:
            def _init_metadata(self):
                return PluginMetadata(
                    name="vcc",
                    version="1.0.0",
                    description="Virginia Connected Corridors traffic data",
                    weight=self.config.get('weight', 0.70)
                )
        """
        pass

    @abstractmethod
    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Collect data for the specified time range.

        This is the core method that retrieves data from the external source
        and returns it in a standardized format.

        Args:
            start_time: Start of collection window (inclusive)
            end_time: End of collection window (exclusive)

        Returns:
            DataFrame with columns:
            - timestamp (datetime): Observation timestamp
            - intersection_id (str): Intersection identifier (if applicable)
            - feature columns (float): Normalized features (0-1 scale)

            The DataFrame should have one row per observation time.

        Raises:
            PluginCollectionError: If data collection fails

        Example:
            def collect(self, start_time, end_time):
                data = self.api_client.fetch(start_time, end_time)
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['time'])
                df['feature1_normalized'] = normalize(df['feature1'])
                return df[['timestamp', 'feature1_normalized', ...]]

        Notes:
            - Features should be normalized to 0-1 scale where possible
            - Missing data should use NaN or plugin-appropriate defaults
            - Timestamps should be timezone-aware (UTC preferred)
        """
        pass

    @abstractmethod
    def get_features(self) -> List[str]:
        """
        Return list of feature names this plugin provides.

        Feature names are used for:
        - Safety index formula transparency (UI display)
        - Weight configuration
        - Debugging and validation

        Returns:
            List of feature column names (e.g., ['weather_precipitation', 'weather_visibility'])

        Example:
            def get_features(self):
                return [
                    'vcc_conflict_count',
                    'vcc_ttc_min',
                    'vcc_proximity_score'
                ]

        Notes:
            - Use descriptive names with plugin prefix (e.g., 'weather_precipitation')
            - Features returned here should match columns in collect() DataFrame
            - Order doesn't matter but should be consistent
        """
        pass

    @abstractmethod
    def health_check(self) -> PluginHealthStatus:
        """
        Verify plugin can connect to its data source.

        This method should perform a lightweight check (< 5 seconds)
        to verify the plugin is operational. It's used for:
        - Startup validation
        - Monitoring and alerting
        - Admin dashboard status display

        Returns:
            PluginHealthStatus with result and diagnostic info

        Example:
            def health_check(self):
                try:
                    response = requests.get(self.api_url, timeout=5)
                    if response.status_code == 200:
                        return PluginHealthStatus(
                            healthy=True,
                            message="API accessible",
                            last_check=datetime.now(),
                            latency_ms=response.elapsed.total_seconds() * 1000
                        )
                except Exception as e:
                    return PluginHealthStatus(
                        healthy=False,
                        message=f"Connection failed: {e}",
                        last_check=datetime.now()
                    )

        Notes:
            - Should NOT raise exceptions (return unhealthy status instead)
            - Keep check lightweight (prefer HEAD request over full data fetch)
            - Include latency measurement if possible
        """
        pass

    def _validate_config(self) -> None:
        """
        Validate plugin configuration.

        Override this method to add plugin-specific validation.
        Raise PluginConfigError if configuration is invalid.

        Example:
            def _validate_config(self):
                if 'api_key' not in self.config:
                    raise PluginConfigError(
                        self.metadata.name,
                        "Missing required 'api_key' in configuration"
                    )
        """
        pass

    def get_weight(self) -> float:
        """
        Return configured weight for this plugin's features.

        The weight determines how much this plugin contributes to
        the overall safety index score. All enabled plugin weights
        should sum to approximately 1.0.

        Returns:
            Weight value (0.0-1.0)

        Example:
            VCC plugin: 0.70 (70%)
            Weather plugin: 0.15 (15%)
            Future plugins: 0.15 (15%)
        """
        return self.metadata.weight

    def is_enabled(self) -> bool:
        """
        Check if plugin is enabled.

        Disabled plugins are skipped during data collection.

        Returns:
            True if plugin is active, False otherwise
        """
        return self.metadata.enabled

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<{self.__class__.__name__}("
            f"name='{self.metadata.name}', "
            f"enabled={self.is_enabled()}, "
            f"weight={self.get_weight():.2f})>"
        )
