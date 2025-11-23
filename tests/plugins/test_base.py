"""
Unit tests for plugin base classes.

Tests cover:
- PluginMetadata validation
- PluginHealthStatus validation
- DataSourcePlugin abstract interface
- Plugin initialization and configuration
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from app.plugins.base import PluginMetadata, PluginHealthStatus, DataSourcePlugin
from app.plugins.exceptions import PluginConfigError
from test_mock_plugin import (
    MockSuccessPlugin,
    MockFailurePlugin,
    MockConfigValidationPlugin
)


class TestPluginMetadata:
    """Test PluginMetadata Pydantic model."""

    def test_metadata_creation_minimal(self):
        """Test creating metadata with minimal required fields."""
        metadata = PluginMetadata(
            name="test",
            description="Test plugin"
        )

        assert metadata.name == "test"
        assert metadata.description == "Test plugin"
        assert metadata.version == "1.0.0"  # Default
        assert metadata.author == "Traffic Safety Team"  # Default
        assert metadata.enabled is True  # Default
        assert metadata.weight == 0.0  # Default

    def test_metadata_creation_full(self):
        """Test creating metadata with all fields."""
        metadata = PluginMetadata(
            name="weather",
            version="2.1.0",
            description="Weather data plugin",
            author="Weather Team",
            enabled=False,
            weight=0.25
        )

        assert metadata.name == "weather"
        assert metadata.version == "2.1.0"
        assert metadata.description == "Weather data plugin"
        assert metadata.author == "Weather Team"
        assert metadata.enabled is False
        assert metadata.weight == 0.25

    def test_metadata_weight_validation_valid(self):
        """Test weight validation accepts valid values."""
        # Lower bound
        metadata = PluginMetadata(name="test", description="test", weight=0.0)
        assert metadata.weight == 0.0

        # Upper bound
        metadata = PluginMetadata(name="test", description="test", weight=1.0)
        assert metadata.weight == 1.0

        # Middle value
        metadata = PluginMetadata(name="test", description="test", weight=0.5)
        assert metadata.weight == 0.5

    def test_metadata_weight_validation_invalid(self):
        """Test weight validation rejects invalid values."""
        # Below lower bound
        with pytest.raises(ValidationError):
            PluginMetadata(name="test", description="test", weight=-0.1)

        # Above upper bound
        with pytest.raises(ValidationError):
            PluginMetadata(name="test", description="test", weight=1.1)

    def test_metadata_immutable(self):
        """Test that metadata is frozen (immutable)."""
        metadata = PluginMetadata(name="test", description="test")

        with pytest.raises(ValidationError):
            metadata.weight = 0.5


class TestPluginHealthStatus:
    """Test PluginHealthStatus Pydantic model."""

    def test_health_status_healthy(self):
        """Test creating healthy status."""
        now = datetime.now()
        status = PluginHealthStatus(
            healthy=True,
            message="All systems operational",
            last_check=now,
            latency_ms=123.45
        )

        assert status.healthy is True
        assert status.message == "All systems operational"
        assert status.last_check == now
        assert status.latency_ms == 123.45

    def test_health_status_unhealthy(self):
        """Test creating unhealthy status."""
        now = datetime.now()
        status = PluginHealthStatus(
            healthy=False,
            message="Connection timeout",
            last_check=now
        )

        assert status.healthy is False
        assert status.message == "Connection timeout"
        assert status.latency_ms is None  # Optional

    def test_health_status_with_details(self):
        """Test health status with additional details."""
        now = datetime.now()
        status = PluginHealthStatus(
            healthy=True,
            message="Operational",
            last_check=now,
            details={"api_version": "2.0", "requests_today": 1234}
        )

        assert status.details["api_version"] == "2.0"
        assert status.details["requests_today"] == 1234


class TestDataSourcePlugin:
    """Test DataSourcePlugin abstract base class."""

    def test_plugin_initialization(self):
        """Test plugin can be initialized with config."""
        config = {'enabled': True, 'weight': 0.7}
        plugin = MockSuccessPlugin(config)

        assert plugin.config == config
        assert plugin.metadata.name == "mock_success"
        assert plugin.metadata.enabled is True
        assert plugin.metadata.weight == 0.7

    def test_plugin_get_weight(self):
        """Test get_weight() returns metadata weight."""
        plugin = MockSuccessPlugin({'weight': 0.33})
        assert plugin.get_weight() == 0.33

    def test_plugin_is_enabled(self):
        """Test is_enabled() returns metadata enabled state."""
        plugin_enabled = MockSuccessPlugin({'enabled': True})
        assert plugin_enabled.is_enabled() is True

        plugin_disabled = MockSuccessPlugin({'enabled': False})
        assert plugin_disabled.is_enabled() is False

    def test_plugin_collect(self):
        """Test plugin collect() returns DataFrame."""
        plugin = MockSuccessPlugin({})
        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        df = plugin.collect(start, end)

        assert not df.empty
        assert 'timestamp' in df.columns
        assert 'mock_feature1' in df.columns
        assert 'mock_feature2' in df.columns
        assert len(df) == 2

    def test_plugin_get_features(self):
        """Test plugin get_features() returns feature list."""
        plugin = MockSuccessPlugin({})
        features = plugin.get_features()

        assert isinstance(features, list)
        assert 'mock_feature1' in features
        assert 'mock_feature2' in features

    def test_plugin_health_check(self):
        """Test plugin health_check() returns status."""
        plugin = MockSuccessPlugin({})
        status = plugin.health_check()

        assert isinstance(status, PluginHealthStatus)
        assert status.healthy is True
        assert status.message == "Mock plugin is healthy"
        assert status.latency_ms == 10.0

    def test_plugin_unhealthy_health_check(self):
        """Test unhealthy plugin health_check()."""
        plugin = MockFailurePlugin({})
        status = plugin.health_check()

        assert status.healthy is False
        assert "unhealthy" in status.message.lower()

    def test_plugin_config_validation_success(self):
        """Test plugin with valid config passes validation."""
        config = {'api_key': 'test_key_12345'}
        plugin = MockConfigValidationPlugin(config)

        assert plugin.config['api_key'] == 'test_key_12345'

    def test_plugin_config_validation_failure_missing(self):
        """Test plugin with missing required config fails."""
        config = {}  # Missing 'api_key'

        with pytest.raises(PluginConfigError) as exc_info:
            MockConfigValidationPlugin(config)

        assert "api_key" in str(exc_info.value)

    def test_plugin_config_validation_failure_wrong_type(self):
        """Test plugin with wrong config type fails."""
        config = {'api_key': 12345}  # Should be string

        with pytest.raises(PluginConfigError) as exc_info:
            MockConfigValidationPlugin(config)

        assert "string" in str(exc_info.value).lower()

    def test_plugin_repr(self):
        """Test plugin __repr__ for debugging."""
        plugin = MockSuccessPlugin({'enabled': True, 'weight': 0.5})
        repr_str = repr(plugin)

        assert 'MockSuccessPlugin' in repr_str
        assert 'mock_success' in repr_str
        assert 'enabled=True' in repr_str
        assert '0.50' in repr_str  # Weight formatted to 2 decimals

    def test_plugin_cannot_instantiate_abstract(self):
        """Test that DataSourcePlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataSourcePlugin({})


class TestPluginInheritance:
    """Test plugin inheritance and customization."""

    def test_multiple_plugins_different_configs(self):
        """Test multiple instances with different configs."""
        plugin1 = MockSuccessPlugin({'weight': 0.3})
        plugin2 = MockSuccessPlugin({'weight': 0.7})

        assert plugin1.get_weight() == 0.3
        assert plugin2.get_weight() == 0.7
        assert plugin1.metadata.name == plugin2.metadata.name  # Same class

    def test_plugin_default_validate_config(self):
        """Test that default _validate_config does nothing."""
        # MockSuccessPlugin doesn't override _validate_config
        # Should not raise any errors
        plugin = MockSuccessPlugin({'random_key': 'random_value'})
        assert plugin.config['random_key'] == 'random_value'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
