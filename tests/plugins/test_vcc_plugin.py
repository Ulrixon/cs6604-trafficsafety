"""
Unit tests for VCC plugin.

Tests cover:
- VCC plugin initialization
- Configuration validation
- Data collection (with mocked VCC client)
- Feature extraction and normalization
- Health checks
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from app.plugins.vcc_plugin import VCCPlugin, create_vcc_plugin_from_settings
from app.plugins.base import PluginHealthStatus
from app.plugins.exceptions import PluginConfigError


class TestVCCPluginInitialization:
    """Test VCC plugin initialization and configuration."""

    def test_plugin_initialization_valid_config(self):
        """Test plugin can be initialized with valid config."""
        config = {
            'base_url': 'https://api.vcc.vtti.vt.edu',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'enabled': True,
            'weight': 0.70
        }

        plugin = VCCPlugin(config)

        assert plugin.metadata.name == "vcc"
        assert plugin.metadata.enabled is True
        assert plugin.metadata.weight == 0.70
        assert plugin.client is not None

    def test_plugin_metadata(self):
        """Test plugin metadata is correct."""
        config = {
            'base_url': 'https://api.vcc.vtti.vt.edu',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        }

        plugin = VCCPlugin(config)

        assert plugin.metadata.name == "vcc"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.description == "Virginia Connected Corridors traffic data source"
        assert plugin.metadata.author == "Traffic Safety Team"

    def test_plugin_get_weight(self):
        """Test get_weight returns configured weight."""
        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret',
            'weight': 0.65
        })

        assert plugin.get_weight() == 0.65

    def test_plugin_is_enabled(self):
        """Test is_enabled returns correct state."""
        plugin_enabled = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret',
            'enabled': True
        })

        plugin_disabled = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret',
            'enabled': False
        })

        assert plugin_enabled.is_enabled() is True
        assert plugin_disabled.is_enabled() is False

    def test_plugin_get_features(self):
        """Test get_features returns expected feature list."""
        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret'
        })

        features = plugin.get_features()

        assert isinstance(features, list)
        assert 'vcc_conflict_count' in features
        assert 'vcc_ttc_min' in features
        assert 'vcc_proximity_score' in features
        assert 'vcc_speed_variance' in features
        assert 'vcc_acceleration_events' in features
        assert len(features) == 5


class TestVCCPluginConfigValidation:
    """Test VCC plugin configuration validation."""

    def test_config_validation_missing_base_url(self):
        """Test validation fails when base_url is missing."""
        config = {
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        }

        with pytest.raises(PluginConfigError) as exc_info:
            VCCPlugin(config)

        assert "base_url" in str(exc_info.value)

    def test_config_validation_missing_client_id(self):
        """Test validation fails when client_id is missing."""
        config = {
            'base_url': 'https://test.com',
            'client_secret': 'test_secret'
        }

        with pytest.raises(PluginConfigError) as exc_info:
            VCCPlugin(config)

        assert "client_id" in str(exc_info.value)

    def test_config_validation_missing_client_secret(self):
        """Test validation fails when client_secret is missing."""
        config = {
            'base_url': 'https://test.com',
            'client_id': 'test_id'
        }

        with pytest.raises(PluginConfigError) as exc_info:
            VCCPlugin(config)

        assert "client_secret" in str(exc_info.value)

    def test_config_validation_invalid_base_url(self):
        """Test validation fails for invalid base_url format."""
        config = {
            'base_url': 'not-a-url',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        }

        with pytest.raises(PluginConfigError) as exc_info:
            VCCPlugin(config)

        assert "base_url" in str(exc_info.value)
        assert "http" in str(exc_info.value).lower()

    def test_config_validation_empty_credentials(self):
        """Test validation fails for empty credentials."""
        config = {
            'base_url': 'https://test.com',
            'client_id': '',
            'client_secret': ''
        }

        with pytest.raises(PluginConfigError):
            VCCPlugin(config)


class TestVCCPluginHealthCheck:
    """Test VCC plugin health check functionality."""

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_health_check_success(self, mock_vcc_client_class):
        """Test health check when VCC API is accessible."""
        # Mock VCC client
        mock_client = Mock()
        mock_client.get_access_token.return_value = "test_token_abc123"
        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        status = plugin.health_check()

        assert isinstance(status, PluginHealthStatus)
        assert status.healthy is True
        assert "successful" in status.message.lower()
        assert status.latency_ms is not None
        assert status.latency_ms >= 0
        assert status.details['token_obtained'] is True

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_health_check_failure_no_token(self, mock_vcc_client_class):
        """Test health check when token cannot be obtained."""
        mock_client = Mock()
        mock_client.get_access_token.return_value = None
        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        status = plugin.health_check()

        assert status.healthy is False
        assert "failed" in status.message.lower()
        assert status.details['token_obtained'] is False

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_health_check_failure_exception(self, mock_vcc_client_class):
        """Test health check when exception occurs."""
        mock_client = Mock()
        mock_client.get_access_token.side_effect = Exception("Connection timeout")
        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        status = plugin.health_check()

        assert status.healthy is False
        assert "error" in status.message.lower()
        assert status.details['error_type'] == "Exception"


class TestVCCPluginDataCollection:
    """Test VCC plugin data collection."""

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_collect_with_data(self, mock_vcc_client_class):
        """Test data collection when VCC API returns data."""
        # Mock VCC client responses
        mock_client = Mock()

        # Mock BSM messages
        mock_client.get_bsm_current.return_value = [
            {
                'bsmJson': {
                    'coreData': {
                        'speed': 15.0,
                        'heading': 90.0
                    }
                },
                'timestamp': 1700580000000
            },
            {
                'bsmJson': {
                    'coreData': {
                        'speed': 20.0,
                        'heading': 95.0
                    }
                },
                'timestamp': 1700580001000
            }
        ]

        # Mock PSM messages
        mock_client.get_psm_current.return_value = [
            {
                'psmJson': {
                    'position': {
                        'lat': 37.0,
                        'lon': -77.0
                    }
                },
                'timestamp': 1700580000000
            }
        ]

        # Mock MapData
        mock_client.get_mapdata.return_value = [
            {
                'mapData': {
                    'intersections': []
                }
            }
        ]

        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        start_time = datetime(2024, 11, 21, 10, 0)
        end_time = datetime(2024, 11, 21, 10, 15)

        df = plugin.collect(start_time, end_time)

        assert not df.empty
        assert 'timestamp' in df.columns
        assert 'intersection_id' in df.columns
        assert 'vcc_conflict_count' in df.columns
        assert 'vcc_ttc_min' in df.columns
        assert 'vcc_proximity_score' in df.columns

        # Verify features are normalized (0-1 scale)
        assert df['vcc_conflict_count'].between(0, 1).all()
        assert df['vcc_ttc_min'].between(0, 1).all()
        assert df['vcc_proximity_score'].between(0, 1).all()

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_collect_no_data(self, mock_vcc_client_class):
        """Test collection when VCC API returns no data."""
        mock_client = Mock()
        mock_client.get_bsm_current.return_value = []
        mock_client.get_psm_current.return_value = []
        mock_client.get_mapdata.return_value = []
        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        start_time = datetime(2024, 11, 21, 10, 0)
        end_time = datetime(2024, 11, 21, 10, 15)

        df = plugin.collect(start_time, end_time)

        # Should return empty DataFrame, not crash
        assert df.empty

    @patch('app.plugins.vcc_plugin.VCCClient')
    def test_collect_api_failure(self, mock_vcc_client_class):
        """Test collection when VCC API fails."""
        from app.plugins.exceptions import PluginCollectionError

        mock_client = Mock()
        mock_client.get_bsm_current.side_effect = Exception("API Error")
        mock_vcc_client_class.return_value = mock_client

        plugin = VCCPlugin({
            'base_url': 'https://test.com',
            'client_id': 'test_id',
            'client_secret': 'test_secret'
        })

        start_time = datetime(2024, 11, 21, 10, 0)
        end_time = datetime(2024, 11, 21, 10, 15)

        with pytest.raises(PluginCollectionError):
            plugin.collect(start_time, end_time)


class TestVCCPluginFeatureNormalization:
    """Test VCC plugin feature normalization."""

    def test_normalize_conflict_count(self):
        """Test conflict count normalization."""
        config = {
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret'
        }
        plugin = VCCPlugin(config)

        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'intersection_id': ['I-001'],
            'vcc_conflict_count_raw': [10],
            'vcc_ttc_min_raw': [5.0],
            'vcc_proximity_score_raw': [0.5],
            'vcc_speed_variance_raw': [50.0],
            'vcc_acceleration_events_raw': [5]
        })

        normalized = plugin._normalize_features(df)

        # 10 conflicts / 20 max = 0.5
        assert normalized['vcc_conflict_count'].iloc[0] == pytest.approx(0.5)

    def test_normalize_ttc_inverted(self):
        """Test TTC normalization is inverted (low TTC = high risk)."""
        config = {
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret'
        }
        plugin = VCCPlugin(config)

        df = pd.DataFrame({
            'timestamp': [datetime.now(), datetime.now()],
            'intersection_id': ['I-001', 'I-001'],
            'vcc_conflict_count_raw': [0, 0],
            'vcc_ttc_min_raw': [10.0, 0.0],  # 10s TTC vs 0s TTC
            'vcc_proximity_score_raw': [0, 0],
            'vcc_speed_variance_raw': [0, 0],
            'vcc_acceleration_events_raw': [0, 0]
        })

        normalized = plugin._normalize_features(df)

        # 10s TTC should be low risk (0.0)
        assert normalized['vcc_ttc_min'].iloc[0] == pytest.approx(0.0)

        # 0s TTC should be high risk (1.0)
        assert normalized['vcc_ttc_min'].iloc[1] == pytest.approx(1.0)

    def test_normalize_features_clipped(self):
        """Test features are clipped to 0-1 range."""
        config = {
            'base_url': 'https://test.com',
            'client_id': 'id',
            'client_secret': 'secret'
        }
        plugin = VCCPlugin(config)

        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'intersection_id': ['I-001'],
            'vcc_conflict_count_raw': [100],  # Way over max
            'vcc_ttc_min_raw': [0.0],
            'vcc_proximity_score_raw': [2.0],  # Over 1.0
            'vcc_speed_variance_raw': [1000.0],  # Way over max
            'vcc_acceleration_events_raw': [50]  # Way over max
        })

        normalized = plugin._normalize_features(df)

        # All values should be clipped to max 1.0
        assert normalized['vcc_conflict_count'].iloc[0] == 1.0
        assert normalized['vcc_proximity_score'].iloc[0] == 1.0
        assert normalized['vcc_speed_variance'].iloc[0] == 1.0
        assert normalized['vcc_acceleration_events'].iloc[0] == 1.0


class TestVCCPluginFactoryFunction:
    """Test VCC plugin factory function."""

    @patch('app.core.config.settings')
    def test_create_from_settings(self, mock_settings):
        """Test creating VCC plugin from settings."""
        mock_settings.VCC_BASE_URL = 'https://api.vcc.vtti.vt.edu'
        mock_settings.VCC_CLIENT_ID = 'test_client_id'
        mock_settings.VCC_CLIENT_SECRET = 'test_client_secret'
        mock_settings.VCC_PLUGIN_WEIGHT = 0.75

        with patch('app.plugins.vcc_plugin.VCCClient'):
            plugin = create_vcc_plugin_from_settings()

            assert plugin.metadata.name == "vcc"
            assert plugin.get_weight() == 0.75
            assert plugin.is_enabled() is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
