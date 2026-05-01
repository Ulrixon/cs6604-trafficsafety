"""
Backend tests – core configuration
====================================
Tests cover:
  - Settings can be instantiated with default values
  - OpenAI fields default correctly
  - Safety computation constants are sane
"""
import pytest


class TestSettings:
    def test_settings_instantiate_with_defaults(self):
        """Settings must instantiate without requiring any env vars."""
        from app.core.config import Settings
        s = Settings()
        assert s.PROJECT_NAME == "Traffic Safety API"
        assert s.VERSION == "0.1.0"

    def test_openai_defaults(self):
        """OpenAI settings must have safe defaults so app starts without a key."""
        from app.core.config import Settings
        s = Settings()
        # Key defaults to empty string (not None) – avoids AttributeError in checks
        assert isinstance(s.OPENAI_API_KEY, str)
        assert s.OPENAI_MODEL == "gpt-4o"
        assert s.OPENAI_MAX_TOKENS == 1024

    def test_empirical_bayes_k_positive(self):
        """Empirical Bayes tuning parameter must be positive."""
        from app.core.config import Settings
        s = Settings()
        assert s.EMPIRICAL_BAYES_K > 0

    def test_mcdm_defaults_positive(self):
        """MCDM computation windows must be positive integers."""
        from app.core.config import Settings
        s = Settings()
        assert s.MCDM_BIN_MINUTES > 0
        assert s.MCDM_LOOKBACK_HOURS > 0
