"""
Unit tests for PluginRegistry.

Tests cover:
- Plugin registration and unregistration
- Parallel data collection
- Failure isolation and handling
- Data merging from multiple plugins
- Health checking
- Weight validation
"""

import pytest
from datetime import datetime
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from app.plugins.registry import PluginRegistry
from app.plugins.exceptions import PluginCollectionError
from test_mock_plugin import (
    MockSuccessPlugin,
    MockFailurePlugin,
    MockSlowPlugin,
    MockEmptyPlugin
)


class TestPluginRegistryBasics:
    """Test basic registry operations."""

    def test_registry_initialization(self):
        """Test registry can be initialized."""
        registry = PluginRegistry(max_workers=3)

        assert registry.max_workers == 3
        assert len(registry.plugins) == 0

    def test_register_plugin(self):
        """Test registering a single plugin."""
        registry = PluginRegistry()
        plugin = MockSuccessPlugin({'weight': 0.5})

        registry.register('success', plugin)

        assert 'success' in registry.plugins
        assert registry.get_plugin('success') == plugin

    def test_register_multiple_plugins(self):
        """Test registering multiple plugins."""
        registry = PluginRegistry()

        registry.register('plugin1', MockSuccessPlugin({'weight': 0.3}))
        registry.register('plugin2', MockSlowPlugin({'weight': 0.7}))

        assert len(registry.plugins) == 2
        assert 'plugin1' in registry.plugins
        assert 'plugin2' in registry.plugins

    def test_register_duplicate_name_fails(self):
        """Test registering same name twice raises error."""
        registry = PluginRegistry()
        plugin1 = MockSuccessPlugin({'weight': 0.5})
        plugin2 = MockSuccessPlugin({'weight': 0.5})

        registry.register('test', plugin1)

        with pytest.raises(ValueError) as exc_info:
            registry.register('test', plugin2)

        assert "already registered" in str(exc_info.value)

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        registry = PluginRegistry()
        registry.register('test', MockSuccessPlugin({}))

        assert 'test' in registry.plugins

        registry.unregister('test')

        assert 'test' not in registry.plugins

    def test_unregister_nonexistent_plugin(self):
        """Test unregistering non-existent plugin doesn't crash."""
        registry = PluginRegistry()

        # Should not raise error
        registry.unregister('nonexistent')

    def test_get_plugin_exists(self):
        """Test getting an existing plugin."""
        registry = PluginRegistry()
        plugin = MockSuccessPlugin({})
        registry.register('test', plugin)

        retrieved = registry.get_plugin('test')

        assert retrieved is plugin

    def test_get_plugin_not_exists(self):
        """Test getting a non-existent plugin returns None."""
        registry = PluginRegistry()

        result = registry.get_plugin('nonexistent')

        assert result is None

    def test_list_plugins(self):
        """Test listing all plugins."""
        registry = PluginRegistry()
        registry.register('plugin1', MockSuccessPlugin({'weight': 0.3}))
        registry.register('plugin2', MockSlowPlugin({'weight': 0.7}))

        plugins_list = registry.list_plugins()

        assert len(plugins_list) == 2
        assert any(p['name'] == 'mock_success' for p in plugins_list)
        assert any(p['name'] == 'mock_slow' for p in plugins_list)

        # Check structure
        assert all('name' in p for p in plugins_list)
        assert all('enabled' in p for p in plugins_list)
        assert all('weight' in p for p in plugins_list)
        assert all('features' in p for p in plugins_list)
        assert all('metadata' in p for p in plugins_list)

    def test_registry_repr(self):
        """Test registry __repr__ for debugging."""
        registry = PluginRegistry(max_workers=3)
        registry.register('test1', MockSuccessPlugin({'enabled': True}))
        registry.register('test2', MockSuccessPlugin({'enabled': False}))

        repr_str = repr(registry)

        assert 'PluginRegistry' in repr_str
        assert 'plugins=2' in repr_str
        assert 'enabled=1' in repr_str
        assert 'max_workers=3' in repr_str


class TestPluginRegistryCollection:
    """Test data collection from plugins."""

    def test_collect_single_plugin(self):
        """Test collecting from a single plugin."""
        registry = PluginRegistry()
        registry.register('success', MockSuccessPlugin({'enabled': True}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        assert not result.empty
        assert 'timestamp' in result.columns
        assert 'mock_feature1' in result.columns
        assert 'mock_feature2' in result.columns

    def test_collect_multiple_plugins(self):
        """Test collecting from multiple plugins in parallel."""
        registry = PluginRegistry(max_workers=3)

        registry.register('plugin1', MockSuccessPlugin({'enabled': True, 'weight': 0.5}))
        registry.register('plugin2', MockSlowPlugin({'enabled': True, 'weight': 0.3, 'delay_seconds': 0.1}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        assert not result.empty
        assert 'timestamp' in result.columns
        # Features from both plugins
        assert 'mock_feature1' in result.columns or 'mock_feature2' in result.columns
        assert 'mock_slow_feature' in result.columns

    def test_collect_disabled_plugin_skipped(self):
        """Test that disabled plugins are skipped."""
        registry = PluginRegistry()

        registry.register('enabled', MockSuccessPlugin({'enabled': True}))
        registry.register('disabled', MockSlowPlugin({'enabled': False}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        # Should only have features from enabled plugin
        assert 'mock_feature1' in result.columns
        assert 'mock_slow_feature' not in result.columns

    def test_collect_no_enabled_plugins(self):
        """Test collection with no enabled plugins returns empty."""
        registry = PluginRegistry()

        registry.register('disabled1', MockSuccessPlugin({'enabled': False}))
        registry.register('disabled2', MockSlowPlugin({'enabled': False}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        assert result.empty

    def test_collect_empty_registry(self):
        """Test collection from empty registry returns empty."""
        registry = PluginRegistry()

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        assert result.empty

    def test_collect_plugin_returns_empty(self):
        """Test handling plugin that returns no data."""
        registry = PluginRegistry()

        registry.register('empty', MockEmptyPlugin({'enabled': True}))
        registry.register('success', MockSuccessPlugin({'enabled': True}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end)

        # Should still have data from success plugin
        assert not result.empty
        assert 'mock_feature1' in result.columns


class TestPluginRegistryFailureHandling:
    """Test failure isolation and error handling."""

    def test_collect_plugin_failure_continues(self):
        """Test that one plugin failure doesn't stop others."""
        registry = PluginRegistry()

        registry.register('success', MockSuccessPlugin({'enabled': True}))
        registry.register('failure', MockFailurePlugin({'enabled': True}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        # Should not raise exception (default fail_fast=False)
        result = registry.collect_all(start, end, fail_fast=False)

        # Should have data from success plugin
        assert not result.empty
        assert 'mock_feature1' in result.columns

    def test_collect_all_plugins_fail(self):
        """Test collection when all plugins fail."""
        registry = PluginRegistry()

        registry.register('failure1', MockFailurePlugin({'enabled': True}))
        registry.register('failure2', MockFailurePlugin({'enabled': True}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        result = registry.collect_all(start, end, fail_fast=False)

        # Should return empty DataFrame, not crash
        assert result.empty

    def test_collect_fail_fast_mode(self):
        """Test fail_fast mode raises on first failure."""
        registry = PluginRegistry()

        registry.register('success', MockSuccessPlugin({'enabled': True}))
        registry.register('failure', MockFailurePlugin({'enabled': True}))

        start = datetime(2024, 11, 21, 10, 0)
        end = datetime(2024, 11, 21, 10, 15)

        # Should raise exception in fail_fast mode
        with pytest.raises(Exception):
            registry.collect_all(start, end, fail_fast=True)


class TestPluginRegistryHealthChecks:
    """Test health check functionality."""

    def test_health_check_all_healthy(self):
        """Test health check when all plugins are healthy."""
        registry = PluginRegistry()

        registry.register('plugin1', MockSuccessPlugin({'enabled': True}))
        registry.register('plugin2', MockSlowPlugin({'enabled': True}))

        health = registry.health_check_all()

        assert len(health) == 2
        assert health['plugin1'].healthy is True
        assert health['plugin2'].healthy is True

    def test_health_check_some_unhealthy(self):
        """Test health check with unhealthy plugins."""
        registry = PluginRegistry()

        registry.register('healthy', MockSuccessPlugin({'enabled': True}))
        registry.register('unhealthy', MockFailurePlugin({'enabled': True}))

        health = registry.health_check_all()

        assert health['healthy'].healthy is True
        assert health['unhealthy'].healthy is False

    def test_health_check_empty_registry(self):
        """Test health check on empty registry."""
        registry = PluginRegistry()

        health = registry.health_check_all()

        assert len(health) == 0

    def test_health_check_includes_latency(self):
        """Test health check includes latency measurement."""
        registry = PluginRegistry()

        registry.register('test', MockSlowPlugin({
            'enabled': True,
            'health_check_delay': 0.05
        }))

        health = registry.health_check_all()

        assert health['test'].latency_ms is not None
        assert health['test'].latency_ms > 0


class TestPluginRegistryWeightValidation:
    """Test plugin weight validation."""

    def test_validate_weights_sum_to_one(self):
        """Test validation passes when weights sum to 1.0."""
        registry = PluginRegistry()

        registry.register('plugin1', MockSuccessPlugin({'enabled': True, 'weight': 0.7}))
        registry.register('plugin2', MockSlowPlugin({'enabled': True, 'weight': 0.3}))

        validation = registry.validate_weights()

        assert validation['valid'] is True
        assert abs(validation['total_weight'] - 1.0) < 0.01

    def test_validate_weights_within_tolerance(self):
        """Test validation passes within 1% tolerance."""
        registry = PluginRegistry()

        registry.register('plugin1', MockSuccessPlugin({'enabled': True, 'weight': 0.70}))
        registry.register('plugin2', MockSlowPlugin({'enabled': True, 'weight': 0.295}))

        validation = registry.validate_weights()

        # 0.70 + 0.295 = 0.995, within 1% of 1.0
        assert validation['valid'] is True

    def test_validate_weights_sum_invalid(self):
        """Test validation fails when weights don't sum to 1.0."""
        registry = PluginRegistry()

        registry.register('plugin1', MockSuccessPlugin({'enabled': True, 'weight': 0.5}))
        registry.register('plugin2', MockSlowPlugin({'enabled': True, 'weight': 0.3}))

        validation = registry.validate_weights()

        # 0.5 + 0.3 = 0.8, not close to 1.0
        assert validation['valid'] is False
        assert validation['total_weight'] == 0.8

    def test_validate_weights_ignores_disabled(self):
        """Test validation only checks enabled plugins."""
        registry = PluginRegistry()

        registry.register('enabled1', MockSuccessPlugin({'enabled': True, 'weight': 0.6}))
        registry.register('enabled2', MockSlowPlugin({'enabled': True, 'weight': 0.4}))
        registry.register('disabled', MockEmptyPlugin({'enabled': False, 'weight': 0.5}))

        validation = registry.validate_weights()

        # Should only count enabled: 0.6 + 0.4 = 1.0
        assert validation['valid'] is True
        assert 'disabled' not in validation['plugins']

    def test_validate_weights_empty_registry(self):
        """Test validation on empty registry."""
        registry = PluginRegistry()

        validation = registry.validate_weights()

        assert validation['total_weight'] == 0.0
        assert validation['valid'] is False  # 0.0 != 1.0


class TestPluginRegistryShutdown:
    """Test registry shutdown and cleanup."""

    def test_shutdown(self):
        """Test registry shutdown closes thread pool."""
        registry = PluginRegistry()

        # Should not raise error
        registry.shutdown()

    def test_shutdown_multiple_times(self):
        """Test calling shutdown multiple times doesn't error."""
        registry = PluginRegistry()

        registry.shutdown()
        registry.shutdown()  # Should not crash


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
