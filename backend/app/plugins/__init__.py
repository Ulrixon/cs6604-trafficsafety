"""
Data source plugin system for the Traffic Safety Index.

This module provides a framework for integrating multiple data sources
(VCC, weather, crash data, etc.) into the safety index calculation.

Usage:
    from app.plugins import DataSourcePlugin, PluginRegistry
    from app.plugins.vcc_plugin import VCCPlugin

    registry = PluginRegistry()
    registry.register('vcc', VCCPlugin(config))
    data = registry.collect_all(start_time, end_time)
"""

from .base import DataSourcePlugin, PluginMetadata, PluginHealthStatus
from .registry import PluginRegistry
from .exceptions import (
    PluginError,
    PluginCollectionError,
    PluginConfigError,
    PluginHealthCheckError,
)

__all__ = [
    "DataSourcePlugin",
    "PluginMetadata",
    "PluginHealthStatus",
    "PluginRegistry",
    "PluginError",
    "PluginCollectionError",
    "PluginConfigError",
    "PluginHealthCheckError",
]
