"""
Backend tests – chat service unit tests
========================================
Tests cover:
  - TOOLS list structure (no live API call)
  - run_chat raises ValueError when API key is missing
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# TOOLS structure
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_tools_is_list(self):
        from app.services.chat_service import TOOLS
        assert isinstance(TOOLS, list)
        assert len(TOOLS) >= 4

    def test_each_tool_has_required_fields(self):
        from app.services.chat_service import TOOLS
        for tool in TOOLS:
            assert tool.get("type") == "function"
            fn = tool.get("function", {})
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_tool_names_are_unique(self):
        from app.services.chat_service import TOOLS
        names = [t["function"]["name"] for t in TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_expected_tools_present(self):
        from app.services.chat_service import TOOLS
        names = {t["function"]["name"] for t in TOOLS}
        expected = {
            "get_safety_score",
            "get_component_breakdown",
            "get_historical_baseline",
            "compare_intersections",
        }
        assert expected.issubset(names)


# ---------------------------------------------------------------------------
# run_chat guardrails
# ---------------------------------------------------------------------------

class TestRunChatGuardrails:
    def test_raises_value_error_when_key_empty(self):
        """run_chat must raise ValueError when OPENAI_API_KEY is ''."""
        with patch("app.services.chat_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.OPENAI_MAX_TOKENS = 1024

            from app.services.chat_service import run_chat
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                run_chat([{"role": "user", "content": "hello"}])
