"""
Exception classes for the plugin system.
"""


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    pass


class PluginCollectionError(PluginError):
    """
    Raised when a plugin fails to collect data from its data source.

    This exception should be caught by the PluginRegistry to allow
    other plugins to continue operating even if one fails.
    """

    def __init__(self, plugin_name: str, message: str, original_error: Exception = None):
        self.plugin_name = plugin_name
        self.original_error = original_error
        super().__init__(f"Plugin '{plugin_name}' collection failed: {message}")


class PluginConfigError(PluginError):
    """
    Raised when a plugin has invalid or missing configuration.

    This is typically raised during plugin initialization.
    """

    def __init__(self, plugin_name: str, message: str):
        self.plugin_name = plugin_name
        super().__init__(f"Plugin '{plugin_name}' configuration error: {message}")


class PluginHealthCheckError(PluginError):
    """
    Raised when a plugin's health check fails.

    This indicates the plugin cannot connect to its data source.
    """

    def __init__(self, plugin_name: str, message: str):
        self.plugin_name = plugin_name
        super().__init__(f"Plugin '{plugin_name}' health check failed: {message}")
