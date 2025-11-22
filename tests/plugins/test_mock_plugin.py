"""
Mock plugin implementations for testing.

These mock plugins are used in unit tests to verify the plugin
framework behavior without requiring external API access.
"""

from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import time

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from app.plugins.base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from app.plugins.exceptions import PluginCollectionError, PluginConfigError


class MockSuccessPlugin(DataSourcePlugin):
    """Mock plugin that always succeeds."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_success",
            version="1.0.0",
            description="Mock plugin that always succeeds",
            author="Test Suite",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.5)
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Return mock data."""
        return pd.DataFrame({
            'timestamp': [start_time, end_time],
            'mock_feature1': [0.5, 0.6],
            'mock_feature2': [0.3, 0.4]
        })

    def get_features(self) -> List[str]:
        return ['mock_feature1', 'mock_feature2']

    def health_check(self) -> PluginHealthStatus:
        return PluginHealthStatus(
            healthy=True,
            message="Mock plugin is healthy",
            last_check=datetime.now(),
            latency_ms=10.0
        )


class MockFailurePlugin(DataSourcePlugin):
    """Mock plugin that always fails during collection."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_failure",
            version="1.0.0",
            description="Mock plugin that always fails",
            author="Test Suite",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.5)
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Always raise an error."""
        raise PluginCollectionError(
            "mock_failure",
            "Simulated collection failure",
            original_error=RuntimeError("Test error")
        )

    def get_features(self) -> List[str]:
        return ['mock_failure_feature']

    def health_check(self) -> PluginHealthStatus:
        return PluginHealthStatus(
            healthy=False,
            message="Mock plugin is unhealthy",
            last_check=datetime.now()
        )


class MockSlowPlugin(DataSourcePlugin):
    """Mock plugin that simulates slow API responses."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_slow",
            version="1.0.0",
            description="Mock plugin with slow responses",
            author="Test Suite",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.3)
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Simulate slow collection (sleeps for config-specified duration)."""
        delay = self.config.get('delay_seconds', 0.5)
        time.sleep(delay)

        return pd.DataFrame({
            'timestamp': [start_time],
            'mock_slow_feature': [0.7]
        })

    def get_features(self) -> List[str]:
        return ['mock_slow_feature']

    def health_check(self) -> PluginHealthStatus:
        start = time.time()
        time.sleep(self.config.get('health_check_delay', 0.1))
        latency = (time.time() - start) * 1000

        return PluginHealthStatus(
            healthy=True,
            message="Slow plugin is healthy",
            last_check=datetime.now(),
            latency_ms=latency
        )


class MockEmptyPlugin(DataSourcePlugin):
    """Mock plugin that returns no data."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_empty",
            version="1.0.0",
            description="Mock plugin that returns no data",
            author="Test Suite",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.2)
        )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Return empty DataFrame."""
        return pd.DataFrame()

    def get_features(self) -> List[str]:
        return ['mock_empty_feature']

    def health_check(self) -> PluginHealthStatus:
        return PluginHealthStatus(
            healthy=True,
            message="Empty plugin is healthy (but returns no data)",
            last_check=datetime.now()
        )


class MockConfigValidationPlugin(DataSourcePlugin):
    """Mock plugin that requires specific config values."""

    def _init_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_config_validation",
            version="1.0.0",
            description="Mock plugin with config validation",
            author="Test Suite",
            enabled=self.config.get('enabled', True),
            weight=self.config.get('weight', 0.1)
        )

    def _validate_config(self) -> None:
        """Require 'api_key' in config."""
        if 'api_key' not in self.config:
            raise PluginConfigError(
                "mock_config_validation",
                "Missing required 'api_key' in configuration"
            )

        if not isinstance(self.config['api_key'], str):
            raise PluginConfigError(
                "mock_config_validation",
                "'api_key' must be a string"
            )

    def collect(self, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        return pd.DataFrame({
            'timestamp': [start_time],
            'mock_config_feature': [0.8]
        })

    def get_features(self) -> List[str]:
        return ['mock_config_feature']

    def health_check(self) -> PluginHealthStatus:
        return PluginHealthStatus(
            healthy=True,
            message=f"Config validated (api_key: {self.config['api_key'][:4]}...)",
            last_check=datetime.now()
        )
