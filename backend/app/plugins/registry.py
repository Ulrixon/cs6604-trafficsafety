"""
Plugin registry for managing data source plugins.

The PluginRegistry coordinates multiple data source plugins,
handling parallel data collection, failure isolation, and
feature aggregation.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import DataSourcePlugin, PluginHealthStatus
from .exceptions import PluginCollectionError

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Centralized registry for managing data source plugins.

    The registry:
    - Stores and manages plugin instances
    - Orchestrates parallel data collection from multiple sources
    - Handles plugin failures gracefully (one failure doesn't stop others)
    - Aggregates features from multiple plugins
    - Validates plugin weights

    Example:
        registry = PluginRegistry(max_workers=5)

        # Register plugins
        registry.register('vcc', VCCPlugin(config))
        registry.register('weather', WeatherPlugin(config))

        # Collect from all plugins
        data = registry.collect_all(start_time, end_time)

        # Check health
        health = registry.health_check_all()
    """

    def __init__(self, max_workers: int = 5):
        """
        Initialize the plugin registry.

        Args:
            max_workers: Maximum number of concurrent plugin collection threads.
                More workers = faster collection but more resource usage.
                Default: 5 workers for I/O-bound plugin operations.
        """
        self.plugins: Dict[str, DataSourcePlugin] = {}
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def register(self, name: str, plugin: DataSourcePlugin) -> None:
        """
        Register a plugin instance.

        Args:
            name: Unique plugin identifier (e.g., 'vcc', 'weather')
            plugin: Plugin instance implementing DataSourcePlugin

        Raises:
            ValueError: If plugin name already registered

        Example:
            registry.register('vcc', VCCPlugin(config))
        """
        if name in self.plugins:
            raise ValueError(f"Plugin '{name}' already registered")

        self.plugins[name] = plugin
        logger.info(
            f"✓ Registered plugin: {name} "
            f"(enabled={plugin.is_enabled()}, weight={plugin.get_weight():.2f})"
        )

    def unregister(self, name: str) -> None:
        """
        Unregister a plugin.

        Args:
            name: Plugin identifier to remove

        Example:
            registry.unregister('weather')  # Disable weather plugin
        """
        if name in self.plugins:
            del self.plugins[name]
            logger.info(f"✓ Unregistered plugin: {name}")
        else:
            logger.warning(f"⚠ Plugin '{name}' not found in registry")

    def get_plugin(self, name: str) -> Optional[DataSourcePlugin]:
        """
        Get plugin by name.

        Args:
            name: Plugin identifier

        Returns:
            Plugin instance or None if not found

        Example:
            vcc = registry.get_plugin('vcc')
            if vcc:
                health = vcc.health_check()
        """
        return self.plugins.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all registered plugins with metadata.

        Returns:
            List of plugin info dictionaries

        Example:
            plugins = registry.list_plugins()
            for plugin in plugins:
                print(f"{plugin['name']}: {plugin['enabled']}")
        """
        return [
            {
                "name": name,
                "enabled": plugin.is_enabled(),
                "weight": plugin.get_weight(),
                "features": plugin.get_features(),
                "metadata": plugin.metadata.dict(),
            }
            for name, plugin in self.plugins.items()
        ]

    def collect_all(
        self,
        start_time: datetime,
        end_time: datetime,
        fail_fast: bool = False,
    ) -> pd.DataFrame:
        """
        Collect data from all enabled plugins in parallel.

        This method:
        1. Submits collection tasks to thread pool for all enabled plugins
        2. Waits for all tasks to complete
        3. Merges results from all plugins into single DataFrame
        4. Handles individual plugin failures gracefully

        Args:
            start_time: Start of collection window
            end_time: End of collection window
            fail_fast: If True, raise exception on first plugin failure.
                If False (default), log errors but continue with other plugins.

        Returns:
            DataFrame with merged features from all plugins.
            Columns: ['timestamp', 'intersection_id', plugin_feature1, ...]

        Raises:
            PluginCollectionError: If fail_fast=True and any plugin fails

        Example:
            data = registry.collect_all(
                start_time=datetime(2024, 11, 21, 10, 0),
                end_time=datetime(2024, 11, 21, 10, 15)
            )
            # data contains VCC features + weather features
        """
        futures = {}
        results = {}

        # Submit collection tasks for enabled plugins
        for name, plugin in self.plugins.items():
            if not plugin.is_enabled():
                logger.debug(f"⊘ Skipping disabled plugin: {name}")
                continue

            logger.debug(f"→ Submitting collection task for plugin: {name}")
            future = self._executor.submit(
                self._collect_with_error_handling, name, plugin, start_time, end_time
            )
            futures[future] = name

        if not futures:
            logger.warning("No enabled plugins to collect from")
            return pd.DataFrame()

        # Gather results as they complete
        for future in as_completed(futures):
            plugin_name = futures[future]
            try:
                data = future.result()
                if data is not None and not data.empty:
                    results[plugin_name] = data
                    logger.info(
                        f"✓ Plugin '{plugin_name}' collected {len(data)} rows"
                    )
                else:
                    logger.warning(f"⚠ Plugin '{plugin_name}' returned no data")
            except Exception as e:
                logger.error(
                    f"✗ Plugin '{plugin_name}' collection failed: {e}", exc_info=True
                )
                if fail_fast:
                    raise

        # Merge all plugin data
        if not results:
            logger.warning("No plugin data collected successfully")
            return pd.DataFrame()

        return self._merge_plugin_data(results)

    def _collect_with_error_handling(
        self,
        name: str,
        plugin: DataSourcePlugin,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[pd.DataFrame]:
        """
        Wrapper for plugin collection with error handling.

        This ensures individual plugin failures don't crash the entire
        collection process.

        Args:
            name: Plugin name (for error messages)
            plugin: Plugin instance
            start_time: Collection start time
            end_time: Collection end time

        Returns:
            DataFrame or None if collection fails
        """
        try:
            logger.debug(
                f"Plugin '{name}' collecting data from {start_time} to {end_time}"
            )
            return plugin.collect(start_time, end_time)
        except Exception as e:
            logger.error(
                f"Plugin '{name}' collection failed: {e}",
                exc_info=True,
                extra={"plugin_name": name, "error": str(e)},
            )
            return None

    def _merge_plugin_data(self, results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Merge data from multiple plugins.

        Merge strategy:
        - Outer join on 'timestamp' column (keep all timestamps from all plugins)
        - Fill missing values with NaN (handled downstream)
        - Preserve all feature columns from all plugins

        Args:
            results: Dictionary mapping plugin name to DataFrame

        Returns:
            Merged DataFrame with all features

        Example:
            results = {
                'vcc': DataFrame with [timestamp, vcc_feature1, vcc_feature2],
                'weather': DataFrame with [timestamp, weather_feature1, weather_feature2]
            }
            merged = _merge_plugin_data(results)
            # merged has [timestamp, vcc_feature1, vcc_feature2, weather_feature1, weather_feature2]
        """
        if len(results) == 1:
            # Single plugin - no merge needed
            return list(results.values())[0]

        merged = None
        for plugin_name, df in results.items():
            if "timestamp" not in df.columns:
                logger.warning(
                    f"Plugin '{plugin_name}' data missing 'timestamp' column, skipping"
                )
                continue

            if merged is None:
                merged = df
                logger.debug(f"Merge base: plugin '{plugin_name}' with {len(df)} rows")
            else:
                # Outer join to keep all timestamps
                before_count = len(merged)
                merged = pd.merge(
                    merged,
                    df,
                    on="timestamp",
                    how="outer",
                    suffixes=("", f"_{plugin_name}"),
                )
                logger.debug(
                    f"Merged plugin '{plugin_name}': {before_count} + {len(df)} = {len(merged)} rows"
                )

        if merged is None:
            logger.warning("No valid plugin data to merge")
            return pd.DataFrame()

        # Sort by timestamp for consistency
        merged = merged.sort_values("timestamp").reset_index(drop=True)

        return merged

    def health_check_all(self) -> Dict[str, PluginHealthStatus]:
        """
        Run health checks on all plugins.

        Returns:
            Dictionary mapping plugin name to PluginHealthStatus

        Example:
            health = registry.health_check_all()
            for name, status in health.items():
                if not status.healthy:
                    print(f"Plugin {name} is unhealthy: {status.message}")
        """
        results = {}
        for name, plugin in self.plugins.items():
            try:
                logger.debug(f"Running health check for plugin: {name}")
                status = plugin.health_check()
                results[name] = status

                if status.healthy:
                    logger.debug(
                        f"✓ Plugin '{name}' healthy "
                        f"({status.latency_ms:.0f}ms)"
                        if status.latency_ms
                        else f"✓ Plugin '{name}' healthy"
                    )
                else:
                    logger.warning(
                        f"⚠ Plugin '{name}' unhealthy: {status.message}"
                    )
            except Exception as e:
                logger.error(f"✗ Plugin '{name}' health check error: {e}")
                results[name] = PluginHealthStatus(
                    healthy=False,
                    message=f"Health check exception: {str(e)}",
                    last_check=datetime.now(),
                )
        return results

    def validate_weights(self) -> Dict[str, Any]:
        """
        Validate that enabled plugin weights sum to approximately 1.0.

        This ensures the safety index is properly normalized and all
        plugins contribute their expected proportion.

        Returns:
            Validation result dictionary with:
            - valid (bool): Whether weights sum to ~1.0
            - total_weight (float): Actual sum of weights
            - expected (float): Expected sum (1.0)
            - plugins (dict): Individual plugin weights

        Example:
            validation = registry.validate_weights()
            if not validation['valid']:
                print(f"Warning: weights sum to {validation['total_weight']}, expected 1.0")
        """
        enabled_plugins = [p for p in self.plugins.values() if p.is_enabled()]
        total_weight = sum(p.get_weight() for p in enabled_plugins)

        # Allow 1% tolerance for floating point comparison
        is_valid = abs(total_weight - 1.0) < 0.01

        result = {
            "valid": is_valid,
            "total_weight": total_weight,
            "expected": 1.0,
            "tolerance": 0.01,
            "plugins": {
                name: plugin.get_weight()
                for name, plugin in self.plugins.items()
                if plugin.is_enabled()
            },
        }

        if not is_valid:
            logger.warning(
                f"⚠ Plugin weights sum to {total_weight:.3f}, expected 1.0 ± 0.01"
            )
        else:
            logger.debug(f"✓ Plugin weights validated: {total_weight:.3f}")

        return result

    def shutdown(self) -> None:
        """
        Shutdown the plugin registry and cleanup resources.

        This should be called on application shutdown to ensure
        the thread pool is properly closed.

        Example:
            # In FastAPI lifespan shutdown
            registry.shutdown()
        """
        logger.info("Shutting down plugin registry...")
        self._executor.shutdown(wait=True)
        logger.info("✓ Plugin registry shut down")

    def __repr__(self) -> str:
        """String representation for debugging."""
        enabled_count = sum(1 for p in self.plugins.values() if p.is_enabled())
        return (
            f"<PluginRegistry("
            f"plugins={len(self.plugins)}, "
            f"enabled={enabled_count}, "
            f"max_workers={self.max_workers})>"
        )
