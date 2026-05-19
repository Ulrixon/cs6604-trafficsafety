"""
Backend tests – chat service unit tests
========================================
Tests cover:
  - TOOLS list structure (no live API call)
  - run_chat raises ValueError when API key is missing
  - compare_intersections time anchoring + RT-SI (regression for UC1 bug)
  - get_safety_score RT-SI integration
"""
from datetime import datetime

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


# ---------------------------------------------------------------------------
# compare_intersections tool handler
# ---------------------------------------------------------------------------

class TestCompareIntersections:
    """
    Regression tests for the compare_intersections tool — the tool behind the
    UC1 "morning briefing" demo use case.
    """

    # A latest-data timestamp deliberately far in the past, so it is clearly
    # distinguishable from datetime.now() (the server wall clock).
    ANCHOR = datetime(2025, 11, 1, 17, 0, 0)

    def _db_at_anchor(self):
        """A mock db whose MAX(publish_timestamp) query reports ANCHOR."""
        db = MagicMock()
        db.execute_query.return_value = [
            {"max_ts": int(self.ANCHOR.timestamp() * 1_000_000)}
        ]
        return db

    def test_anchors_to_latest_data_not_server_clock(self):
        """
        compare_intersections must score each intersection at the latest
        available data time. Using datetime.now() queries an empty window
        and reports every site as 0 — the UC1 morning-briefing bug.
        """
        db = self._db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService"):
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_for_time.return_value = {"mcdm_index": 52.0}

            from app.services.chat_service import _execute_compare_intersections
            _execute_compare_intersections({"metric": "mcdm"})

            assert mcdm.calculate_safety_score_for_time.called
            _, scored_at = mcdm.calculate_safety_score_for_time.call_args[0]
            assert scored_at == self.ANCHOR, (
                f"expected scoring at latest-data time {self.ANCHOR}, "
                f"got {scored_at}"
            )

    def test_includes_real_rt_si_for_blended_metric(self):
        """
        For metric='blended', each ranking row must carry the RT-SI score
        from the RT-SI service — not a hardcoded 0.0.
        """
        db = self._db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls, \
             patch("app.api.intersection.find_crash_intersection_for_bsm",
                   return_value=[{"crash_intersection_id": 101}]):
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_for_time.return_value = {"mcdm_index": 50.0}
            rtsi_cls.return_value.calculate_rt_si.return_value = {"RT_SI": 80.0}

            from app.services.chat_service import _execute_compare_intersections
            result = _execute_compare_intersections(
                {"metric": "blended", "alpha": 0.7}
            )

            row = result["rankings"][0]
            assert row["rt_si"] == 80.0
            # blended = 0.7 * 80 + 0.3 * 50 = 71.0
            assert row["blended"] == 71.0

    def test_skips_rt_si_for_non_blended_metric(self):
        """
        Ranking by a pure-MCDM metric must not trigger per-site RT-SI
        computation — that keeps the comparison fast for UC1 latency.
        """
        db = self._db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls, \
             patch("app.api.intersection.find_crash_intersection_for_bsm") as fcib:
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_for_time.return_value = {"mcdm_index": 50.0}

            from app.services.chat_service import _execute_compare_intersections
            _execute_compare_intersections({"metric": "vehicle_count"})

            fcib.assert_not_called()
            rtsi_cls.return_value.calculate_rt_si.assert_not_called()


# ---------------------------------------------------------------------------
# get_safety_score tool handler
# ---------------------------------------------------------------------------

class TestGetSafetyScore:
    """RT-SI integration for the get_safety_score tool."""

    def test_returns_rt_si_score_from_service(self):
        """get_safety_score must surface the RT-SI score computed for the site."""
        anchor = datetime(2025, 11, 1, 17, 0, 0)
        db = MagicMock()
        db.execute_query.return_value = [
            {"max_ts": int(anchor.timestamp() * 1_000_000)}
        ]
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls, \
             patch("app.api.intersection.find_crash_intersection_for_bsm",
                   return_value=[{"crash_intersection_id": 101}]):
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_for_time.return_value = {"mcdm_index": 40.0}
            rtsi_cls.return_value.calculate_rt_si.return_value = {"RT_SI": 60.0}

            from app.services.chat_service import _execute_get_safety_score
            result = _execute_get_safety_score(
                {"intersection": "birch", "alpha": 0.5}
            )

            assert result["rt_si_score"] == 60.0
            assert result["mcdm_score"] == 40.0
            # blended = 0.5 * 60 + 0.5 * 40 = 50.0
            assert result["blended_score"] == 50.0

    def test_top_factors_use_rt_si_service_keys(self):
        """
        top_factors must read the keys rt_si_service.calculate_rt_si actually
        returns: F_variance, F_conflict, VRU_index, VEH_index. An earlier
        version read F_var / F_conf / VRU_SI / VEH_SI which simply do not
        exist in the result dict — every factor silently defaulted to 0.0,
        so SafetyChat reported all-zero uplift breakdowns even when the
        underlying RT-SI computation had real values.
        """
        anchor = datetime(2025, 11, 1, 17, 0, 0)
        db = MagicMock()
        db.execute_query.return_value = [
            {"max_ts": int(anchor.timestamp() * 1_000_000)}
        ]
        # Use the exact key names from rt_si_service.calculate_rt_si.
        rt_result = {
            "RT_SI": 70.0,
            "F_speed": 0.5,
            "F_variance": 0.4,
            "F_conflict": 0.3,
            "VRU_index": 12.5,
            "VEH_index": 25.0,
            "timestamp": "2025-11-01T17:00:00",
        }
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls, \
             patch("app.api.intersection.find_crash_intersection_for_bsm",
                   return_value=[{"crash_intersection_id": 101}]):
            mcdm_cls.return_value.get_available_intersections.return_value = [
                "birch_st-w_broad_st"
            ]
            mcdm_cls.return_value.calculate_safety_score_for_time.return_value = {
                "mcdm_index": 30.0
            }
            rtsi_cls.return_value.calculate_rt_si.return_value = rt_result

            from app.services.chat_service import _execute_get_safety_score
            result = _execute_get_safety_score({"intersection": "birch"})

            tf = result["top_factors"]
            assert tf["speed_uplift"] == 0.5, "speed_uplift should read F_speed"
            assert tf["variance_uplift"] == 0.4, \
                "variance_uplift must read F_variance, not the non-existent F_var"
            assert tf["conflict_uplift"] == 0.3, \
                "conflict_uplift must read F_conflict, not the non-existent F_conf"
            assert tf["vru_sub_index"] == 12.5, \
                "vru_sub_index must read VRU_index, not the non-existent VRU_SI"
            assert tf["vehicle_sub_index"] == 25.0, \
                "vehicle_sub_index must read VEH_index, not the non-existent VEH_SI"


# ---------------------------------------------------------------------------
# get_historical_baseline tool handler
# ---------------------------------------------------------------------------

class TestGetHistoricalBaseline:
    """Regression: must query the table that actually exists."""

    def test_queries_existing_crashes_table_not_misspelled_singular(self):
        """
        The crash-history query must target ``vdot_crashes_with_intersections``
        (plural ``crashes``) — the table every other module uses. An earlier
        version queried ``vdot_crash_with_intersections`` (singular), which
        does not exist; the handler's blanket except swallowed the error and
        the LLM silently lost the historical-baseline data for UC2-style
        causal questions.
        """
        db = MagicMock()
        db.execute_query.return_value = [{
            "total_crashes": 5, "fatal": 1, "injury": 2, "pdo": 2,
            "earliest": "2020-01-01", "latest": "2024-12-01",
        }]
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls, \
             patch("app.api.intersection.find_crash_intersection_for_bsm",
                   return_value=[{"crash_intersection_id": 101}]):
            mcdm_cls.return_value.get_available_intersections.return_value = [
                "birch_st-w_broad_st"
            ]
            rtsi_cls.return_value.get_eb_params.return_value = {"lambda_star": 10000}

            from app.services.chat_service import _execute_get_historical_baseline
            _execute_get_historical_baseline({"intersection": "birch"})

            sql = db.execute_query.call_args[0][0]
            assert "vdot_crashes_with_intersections" in sql, (
                f"expected the plural table name, got SQL: {sql!r}"
            )
