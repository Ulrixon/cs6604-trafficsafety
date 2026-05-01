"""
Frontend tests – configuration module
=======================================
Tests cover:
  - Default values load without a .env file
  - API_URL is a non-empty string
  - Color thresholds are logically consistent (low < high)
  - Risk level dict structure
  - Map defaults are in valid geographic range
"""
import sys
import os
import pytest
import types

# Stub streamlit before importing config
streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.cache_data = lambda *a, **kw: (lambda f: f)
sys.modules.setdefault("streamlit", streamlit_stub)


class TestFrontendConfig:
    @pytest.fixture(autouse=True)
    def _import_config(self):
        # Force re-import so each test gets defaults, not env-overridden values
        import importlib
        import app.utils.config as cfg_module
        importlib.reload(cfg_module)
        self.cfg = cfg_module

    def test_api_url_is_string(self):
        assert isinstance(self.cfg.API_URL, str)
        assert len(self.cfg.API_URL) > 0

    def test_api_timeout_positive(self):
        assert self.cfg.API_TIMEOUT > 0

    def test_api_max_retries_non_negative(self):
        assert self.cfg.API_MAX_RETRIES >= 0

    def test_color_thresholds_logical(self):
        """Low threshold must be less than high threshold."""
        assert self.cfg.COLOR_LOW_THRESHOLD < self.cfg.COLOR_HIGH_THRESHOLD

    def test_risk_levels_dict_complete(self):
        assert set(self.cfg.RISK_LEVELS.keys()) == {"Low", "Medium", "High"}
        for level, meta in self.cfg.RISK_LEVELS.items():
            assert "color" in meta
            assert "threshold" in meta
            lo, hi = meta["threshold"]
            assert lo <= hi, f"{level}: threshold lo > hi"

    def test_map_defaults_valid_coords(self):
        assert -90 <= self.cfg.DEFAULT_LATITUDE <= 90
        assert -180 <= self.cfg.DEFAULT_LONGITUDE <= 180

    def test_map_height_positive(self):
        assert self.cfg.MAP_HEIGHT > 0

    def test_radius_range_valid(self):
        assert self.cfg.MIN_RADIUS_PX < self.cfg.MAX_RADIUS_PX
