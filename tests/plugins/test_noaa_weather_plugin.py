"""
Unit tests for NOAA Weather Plugin.

Tests the NOAA/NWS weather data source plugin with mocked API responses.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import requests
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from app.plugins.noaa_weather_plugin import NOAAWeatherPlugin, create_weather_plugin_from_settings
from app.plugins.base import PluginMetadata, PluginHealthStatus
from app.plugins.exceptions import PluginCollectionError, PluginConfigError


class TestNOAAWeatherPluginInitialization:
    """Tests for NOAA weather plugin initialization."""

    def test_plugin_initialization_with_minimal_config(self):
        """Test plugin can be initialized with minimal configuration."""
        config = {
            'station_id': 'KRIC'
        }
        plugin = NOAAWeatherPlugin(config)

        assert plugin.metadata.name == "noaa_weather"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.enabled is True
        assert plugin.metadata.weight == 0.15
        assert plugin.station_id == 'KRIC'
        assert plugin.api_base == 'https://api.weather.gov'

    def test_plugin_initialization_with_full_config(self):
        """Test plugin initialization with all configuration options."""
        config = {
            'station_id': 'KDCA',
            'api_base': 'https://custom.weather.api',
            'user_agent': 'CustomApp/1.0',
            'timeout': 20,
            'retry_attempts': 5,
            'retry_delay': 3,
            'enabled': False,
            'weight': 0.20
        }
        plugin = NOAAWeatherPlugin(config)

        assert plugin.station_id == 'KDCA'
        assert plugin.api_base == 'https://custom.weather.api'
        assert plugin.user_agent == 'CustomApp/1.0'
        assert plugin.timeout == 20
        assert plugin.retry_attempts == 5
        assert plugin.retry_delay == 3
        assert plugin.metadata.enabled is False
        assert plugin.metadata.weight == 0.20

    def test_plugin_metadata_fields(self):
        """Test plugin metadata contains expected fields."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        assert plugin.metadata.name == "noaa_weather"
        assert plugin.metadata.description == "NOAA/NWS weather observation data source"
        assert plugin.metadata.author == "Traffic Safety Team"
        assert isinstance(plugin.metadata.enabled, bool)
        assert isinstance(plugin.metadata.weight, float)

    def test_plugin_get_features(self):
        """Test plugin returns correct feature list."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        features = plugin.get_features()
        assert len(features) == 4
        assert 'weather_precipitation' in features
        assert 'weather_visibility' in features
        assert 'weather_wind_speed' in features
        assert 'weather_temperature' in features

    def test_plugin_is_enabled(self):
        """Test plugin enabled/disabled status."""
        config_enabled = {'station_id': 'KRIC', 'enabled': True}
        plugin_enabled = NOAAWeatherPlugin(config_enabled)
        assert plugin_enabled.is_enabled() is True

        config_disabled = {'station_id': 'KRIC', 'enabled': False}
        plugin_disabled = NOAAWeatherPlugin(config_disabled)
        assert plugin_disabled.is_enabled() is False

    def test_plugin_get_weight(self):
        """Test plugin weight retrieval."""
        config = {'station_id': 'KRIC', 'weight': 0.25}
        plugin = NOAAWeatherPlugin(config)
        assert plugin.get_weight() == 0.25


class TestNOAAWeatherPluginConfigValidation:
    """Tests for NOAA weather plugin configuration validation."""

    def test_missing_station_id_raises_error(self):
        """Test that missing station_id raises PluginConfigError."""
        config = {}
        with pytest.raises(PluginConfigError) as exc_info:
            NOAAWeatherPlugin(config)

        assert "Missing required configuration key: 'station_id'" in str(exc_info.value)
        assert exc_info.value.plugin_name == "noaa_weather"

    def test_empty_station_id_raises_error(self):
        """Test that empty station_id raises PluginConfigError."""
        config = {'station_id': ''}
        with pytest.raises(PluginConfigError) as exc_info:
            NOAAWeatherPlugin(config)

        assert "Missing required configuration key: 'station_id'" in str(exc_info.value)

    def test_invalid_station_id_length_raises_error(self):
        """Test that station_id with wrong length raises error."""
        # Too short
        config_short = {'station_id': 'KRI'}
        with pytest.raises(PluginConfigError) as exc_info:
            NOAAWeatherPlugin(config_short)
        assert "Invalid station_id format" in str(exc_info.value)

        # Too long
        config_long = {'station_id': 'KRICH'}
        with pytest.raises(PluginConfigError) as exc_info:
            NOAAWeatherPlugin(config_long)
        assert "Invalid station_id format" in str(exc_info.value)

    def test_non_string_station_id_raises_error(self):
        """Test that non-string station_id raises error."""
        config = {'station_id': 1234}
        with pytest.raises(PluginConfigError) as exc_info:
            NOAAWeatherPlugin(config)
        assert "Invalid station_id format" in str(exc_info.value)

    def test_valid_station_id_formats(self):
        """Test various valid station_id formats."""
        valid_ids = ['KRIC', 'KDCA', 'KJFK', 'KLAX']

        for station_id in valid_ids:
            config = {'station_id': station_id}
            plugin = NOAAWeatherPlugin(config)
            assert plugin.station_id == station_id


class TestNOAAWeatherPluginHealthCheck:
    """Tests for NOAA weather plugin health check."""

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_health_check_success(self, mock_get):
        """Test health check returns healthy status on success."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'properties': {
                'name': 'Richmond International Airport, VA',
                'stationIdentifier': 'KRIC'
            }
        }
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)
        status = plugin.health_check()

        assert isinstance(status, PluginHealthStatus)
        assert status.healthy is True
        assert 'KRIC' in status.message
        assert 'Richmond International Airport' in status.message
        assert status.last_check is not None
        assert status.latency_ms >= 0
        assert status.details['station_id'] == 'KRIC'
        assert status.details['station_name'] == 'Richmond International Airport, VA'

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_health_check_http_error(self, mock_get):
        """Test health check handles HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)
        status = plugin.health_check()

        assert status.healthy is False
        assert 'HTTP 404' in status.message
        assert status.details['status_code'] == 404

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_health_check_connection_error(self, mock_get):
        """Test health check handles connection errors."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)
        status = plugin.health_check()

        assert status.healthy is False
        assert 'NOAA API error' in status.message
        assert status.details['error_type'] == 'ConnectionError'
        assert 'Connection failed' in status.details['error_message']

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_health_check_timeout(self, mock_get):
        """Test health check handles timeout errors."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        config = {'station_id': 'KRIC', 'timeout': 5}
        plugin = NOAAWeatherPlugin(config)
        status = plugin.health_check()

        assert status.healthy is False
        assert 'NOAA API error' in status.message
        assert status.details['error_type'] == 'Timeout'


class TestNOAAWeatherPluginDataCollection:
    """Tests for NOAA weather plugin data collection."""

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_collect_success_with_data(self, mock_get):
        """Test data collection with valid NOAA API response."""
        # Mock NOAA API response (GeoJSON format)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        'timestamp': '2024-11-21T14:00:00Z',
                        'temperature': {'value': 18.3, 'unitCode': 'wmoUnit:degC'},
                        'precipitationLastHour': {'value': 2.5, 'unitCode': 'wmoUnit:mm'},
                        'visibility': {'value': 8000, 'unitCode': 'wmoUnit:m'},
                        'windSpeed': {'value': 5.2, 'unitCode': 'wmoUnit:m/s'},
                        'windDirection': {'value': 180, 'unitCode': 'wmoUnit:degree_(angle)'},
                        'textDescription': 'Light Rain'
                    }
                },
                {
                    'properties': {
                        'timestamp': '2024-11-21T14:15:00Z',
                        'temperature': {'value': 17.8, 'unitCode': 'wmoUnit:degC'},
                        'precipitationLastHour': {'value': 0.0, 'unitCode': 'wmoUnit:mm'},
                        'visibility': {'value': 10000, 'unitCode': 'wmoUnit:m'},
                        'windSpeed': {'value': 3.1, 'unitCode': 'wmoUnit:m/s'},
                        'windDirection': {'value': 190, 'unitCode': 'wmoUnit:degree_(angle)'},
                        'textDescription': 'Partly Cloudy'
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)
        df = plugin.collect(start_time, end_time)

        assert not df.empty
        assert len(df) == 2
        assert 'timestamp' in df.columns
        assert 'weather_precipitation' in df.columns
        assert 'weather_visibility' in df.columns
        assert 'weather_wind_speed' in df.columns
        assert 'weather_temperature' in df.columns

        # Check normalization (all values should be 0-1)
        assert df['weather_precipitation'].min() >= 0.0
        assert df['weather_precipitation'].max() <= 1.0
        assert df['weather_visibility'].min() >= 0.0
        assert df['weather_visibility'].max() <= 1.0

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_collect_empty_response(self, mock_get):
        """Test data collection with empty API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'features': []}
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)
        df = plugin.collect(start_time, end_time)

        assert df.empty

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_collect_api_error_raises_exception(self, mock_get):
        """Test data collection raises PluginCollectionError on API failure."""
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        config = {'station_id': 'KRIC', 'retry_attempts': 1}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)

        with pytest.raises(PluginCollectionError) as exc_info:
            plugin.collect(start_time, end_time)

        assert exc_info.value.plugin_name == "noaa_weather"
        assert "Failed to collect weather data" in str(exc_info.value)

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_collect_retry_logic(self, mock_get):
        """Test data collection retry logic with exponential backoff."""
        # First two attempts fail, third succeeds
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'features': []}

        mock_get.side_effect = [
            requests.exceptions.RequestException("Temporary error"),
            requests.exceptions.RequestException("Temporary error"),
            mock_response_success
        ]

        config = {'station_id': 'KRIC', 'retry_attempts': 3, 'retry_delay': 0.1}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)

        # Should succeed on third attempt
        df = plugin.collect(start_time, end_time)
        assert df.empty  # Empty but no error raised
        assert mock_get.call_count == 3

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_collect_missing_timestamp_skips_observation(self, mock_get):
        """Test that observations without timestamp are skipped."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        # Missing timestamp
                        'temperature': {'value': 18.3, 'unitCode': 'wmoUnit:degC'}
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)
        df = plugin.collect(start_time, end_time)

        assert df.empty


class TestNOAAWeatherPluginFeatureNormalization:
    """Tests for NOAA weather plugin feature normalization."""

    def test_precipitation_normalization(self):
        """Test precipitation feature normalization (0-1 scale)."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        # Create test data
        test_data = pd.DataFrame([
            {'timestamp': datetime.now(), 'precipitation_mm': 0.0},
            {'timestamp': datetime.now(), 'precipitation_mm': 10.0},
            {'timestamp': datetime.now(), 'precipitation_mm': 20.0},
            {'timestamp': datetime.now(), 'precipitation_mm': 30.0},  # Should clip to 1.0
        ])

        normalized = plugin._normalize_features(test_data)

        assert normalized['weather_precipitation'].iloc[0] == 0.0  # 0mm
        assert normalized['weather_precipitation'].iloc[1] == 0.5  # 10mm
        assert normalized['weather_precipitation'].iloc[2] == 1.0  # 20mm
        assert normalized['weather_precipitation'].iloc[3] == 1.0  # 30mm (clipped)

    def test_visibility_normalization_inverted(self):
        """Test visibility normalization is inverted (low visibility = high risk)."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        test_data = pd.DataFrame([
            {'timestamp': datetime.now(), 'visibility_m': 10000},  # Good visibility
            {'timestamp': datetime.now(), 'visibility_m': 5000},   # Moderate
            {'timestamp': datetime.now(), 'visibility_m': 0},      # Zero visibility
        ])

        normalized = plugin._normalize_features(test_data)

        assert normalized['weather_visibility'].iloc[0] == 0.0  # 10km = no risk
        assert normalized['weather_visibility'].iloc[1] == 0.5  # 5km = moderate risk
        assert normalized['weather_visibility'].iloc[2] == 1.0  # 0m = high risk

    def test_wind_speed_normalization(self):
        """Test wind speed normalization (0-1 scale)."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        test_data = pd.DataFrame([
            {'timestamp': datetime.now(), 'wind_speed_ms': 0.0},
            {'timestamp': datetime.now(), 'wind_speed_ms': 12.5},
            {'timestamp': datetime.now(), 'wind_speed_ms': 25.0},
            {'timestamp': datetime.now(), 'wind_speed_ms': 40.0},  # Should clip to 1.0
        ])

        normalized = plugin._normalize_features(test_data)

        assert normalized['weather_wind_speed'].iloc[0] == 0.0   # Calm
        assert normalized['weather_wind_speed'].iloc[1] == 0.5   # 12.5 m/s
        assert normalized['weather_wind_speed'].iloc[2] == 1.0   # 25 m/s
        assert normalized['weather_wind_speed'].iloc[3] == 1.0   # 40 m/s (clipped)

    def test_temperature_normalization_u_shaped(self):
        """Test temperature normalization uses U-shaped curve (extremes = high risk)."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        test_data = pd.DataFrame([
            {'timestamp': datetime.now(), 'temperature_c': 20.0},  # Optimal
            {'timestamp': datetime.now(), 'temperature_c': 10.0},  # Cool
            {'timestamp': datetime.now(), 'temperature_c': 30.0},  # Warm
            {'timestamp': datetime.now(), 'temperature_c': 0.0},   # Cold extreme
            {'timestamp': datetime.now(), 'temperature_c': 40.0},  # Hot extreme
            {'timestamp': datetime.now(), 'temperature_c': -10.0}, # Very cold (should clip)
        ])

        normalized = plugin._normalize_features(test_data)

        assert normalized['weather_temperature'].iloc[0] == 0.0  # 20°C = optimal
        assert normalized['weather_temperature'].iloc[1] == 0.5  # 10°C away from optimal
        assert normalized['weather_temperature'].iloc[2] == 0.5  # 10°C away from optimal
        assert normalized['weather_temperature'].iloc[3] == 1.0  # 0°C = high risk
        assert normalized['weather_temperature'].iloc[4] == 1.0  # 40°C = high risk (clipped)
        assert normalized['weather_temperature'].iloc[5] == 1.0  # -10°C = high risk (clipped)

    def test_missing_values_filled_with_defaults(self):
        """Test that missing values are filled with safe defaults."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        test_data = pd.DataFrame([
            {
                'timestamp': datetime.now(),
                'precipitation_mm': None,
                'visibility_m': None,
                'wind_speed_ms': None,
                'temperature_c': None
            }
        ])

        normalized = plugin._normalize_features(test_data)

        # Missing precipitation -> 0mm -> 0.0 risk
        assert normalized['weather_precipitation'].iloc[0] == 0.0

        # Missing visibility -> 10km -> 0.0 risk
        assert normalized['weather_visibility'].iloc[0] == 0.0

        # Missing wind -> 0 m/s -> 0.0 risk
        assert normalized['weather_wind_speed'].iloc[0] == 0.0

        # Missing temperature -> 20°C -> 0.0 risk
        assert normalized['weather_temperature'].iloc[0] == 0.0


class TestNOAAWeatherPluginFactoryFunction:
    """Tests for create_weather_plugin_from_settings factory function."""

    @patch('app.core.config.settings')
    def test_create_plugin_from_settings(self, mock_settings):
        """Test factory function creates plugin from settings."""
        mock_settings.WEATHER_STATION_ID = 'KDCA'
        mock_settings.WEATHER_API_BASE = 'https://api.weather.gov'
        mock_settings.WEATHER_API_TIMEOUT = 15
        mock_settings.WEATHER_RETRY_ATTEMPTS = 4
        mock_settings.WEATHER_PLUGIN_WEIGHT = 0.18

        plugin = create_weather_plugin_from_settings()

        assert isinstance(plugin, NOAAWeatherPlugin)
        assert plugin.station_id == 'KDCA'
        assert plugin.api_base == 'https://api.weather.gov'
        assert plugin.timeout == 15
        assert plugin.retry_attempts == 4
        assert plugin.metadata.enabled is True
        assert plugin.metadata.weight == 0.18


class TestNOAAWeatherPluginValueExtraction:
    """Tests for _extract_value helper method."""

    def test_extract_value_from_dict(self):
        """Test extracting value from NOAA value object."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        value_obj = {'value': 18.3, 'unitCode': 'wmoUnit:degC'}
        result = plugin._extract_value(value_obj)
        assert result == 18.3

    def test_extract_value_from_none(self):
        """Test extracting value from None returns None."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        result = plugin._extract_value(None)
        assert result is None

    def test_extract_value_from_number(self):
        """Test extracting value from direct number."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        result = plugin._extract_value(25.7)
        assert result == 25.7

    def test_extract_value_from_empty_dict(self):
        """Test extracting value from empty dict returns None."""
        config = {'station_id': 'KRIC'}
        plugin = NOAAWeatherPlugin(config)

        result = plugin._extract_value({})
        assert result is None


class TestNOAAWeatherPluginRequestHeaders:
    """Tests for NOAA API request headers."""

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_request_includes_user_agent(self, mock_get):
        """Test that requests include User-Agent header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'features': []}
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC', 'user_agent': 'CustomApp/2.0'}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)
        plugin.collect(start_time, end_time)

        # Verify headers were set
        call_kwargs = mock_get.call_args.kwargs
        assert 'headers' in call_kwargs
        assert call_kwargs['headers']['User-Agent'] == 'CustomApp/2.0'
        assert call_kwargs['headers']['Accept'] == 'application/geo+json'

    @patch('app.plugins.noaa_weather_plugin.requests.get')
    def test_request_includes_timeout(self, mock_get):
        """Test that requests include timeout parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'features': []}
        mock_get.return_value = mock_response

        config = {'station_id': 'KRIC', 'timeout': 25}
        plugin = NOAAWeatherPlugin(config)

        start_time = datetime(2024, 11, 21, 14, 0)
        end_time = datetime(2024, 11, 21, 14, 30)
        plugin.collect(start_time, end_time)

        # Verify timeout was set
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs['timeout'] == 25
