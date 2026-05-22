"""
Backend tests – chat service unit tests
========================================
Tests cover:
  - TOOLS list structure (no live API call)
  - run_chat raises ValueError when API key is missing
  - compare_intersections time anchoring + RT-SI (regression for UC1 bug)
  - get_safety_score RT-SI integration
"""
from datetime import datetime, timedelta

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
            _execute_compare_intersections({"metric": "blended"})

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

    def test_batches_mcdm_rankings_for_non_rt_metrics(self):
        """
        Pure-MCDM rankings should collect and score the latest matrix once,
        instead of recalculating a 24-hour matrix for every intersection.
        """
        db = self._db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls, \
             patch("app.services.chat_service.RTSIService") as rtsi_cls:
            mcdm = mcdm_cls.return_value
            mcdm.calculate_latest_safety_scores.return_value = [
                {
                    "intersection": "birch_st-w_broad_st",
                    "mcdm_index": 50.0,
                    "vehicle_count": 100,
                    "vru_count": 10,
                    "incident_count": 2,
                    "near_miss_count": 1,
                    "avg_speed": 24.0,
                    "speed_variance": 12.0,
                    "time_bin": self.ANCHOR,
                },
                {
                    "intersection": "e_broad_st-n_washington_st",
                    "mcdm_index": 75.0,
                    "vehicle_count": 200,
                    "vru_count": 20,
                    "incident_count": 4,
                    "near_miss_count": 0,
                    "avg_speed": 22.0,
                    "speed_variance": 18.0,
                    "time_bin": self.ANCHOR,
                },
            ]

            from app.services.chat_service import _execute_compare_intersections
            result = _execute_compare_intersections({"metric": "mcdm"})

            mcdm.calculate_latest_safety_scores.assert_called_once()
            mcdm.calculate_safety_score_for_time.assert_not_called()
            rtsi_cls.return_value.calculate_rt_si.assert_not_called()
            assert result["rankings"][0]["intersection"] == "e_broad_st-n_washington_st"
            assert result["rankings"][0]["mcdm"] == 75.0

    def test_morning_briefing_uses_fast_path_without_openai(self):
        """
        When OpenAI is unavailable (here: no API key), the canonical UC1 query
        falls back to the deterministic latest-data ranking plus concise
        operator summary instead of erroring.
        """
        with patch(
            "app.services.chat_service._execute_compare_intersections",
            return_value={
                "rankings": [
                    {
                        "intersection": "e_broad_st-n_washington_st",
                        "mcdm": 75.0,
                        "vehicle_count": 200,
                        "vru_count": 20,
                        "incident_count": 4,
                        "speed_variance": 18.0,
                    },
                    {
                        "intersection": "birch_st-w_broad_st",
                        "mcdm": 50.0,
                        "vehicle_count": 100,
                        "vru_count": 10,
                        "incident_count": 2,
                        "speed_variance": 12.0,
                    },
                ],
                "data_time": str(self.ANCHOR),
            },
        ), patch("openai.OpenAI") as openai_cls:
            from app.services.chat_service import run_chat
            reply = run_chat([
                {
                    "role": "user",
                    "content": "Give me a morning safety briefing for all intersections.",
                }
            ])

            openai_cls.assert_not_called()
            assert "E Broad St & N Washington St" in reply
            assert "75.00" in reply


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


# ---------------------------------------------------------------------------
# Latest-data anchoring for the remaining tool handlers
# ---------------------------------------------------------------------------

ANCHOR = datetime(2025, 11, 1, 17, 0, 0)


def _db_at_anchor() -> MagicMock:
    db = MagicMock()
    db.execute_query.return_value = [
        {"max_ts": int(ANCHOR.timestamp() * 1_000_000)}
    ]
    return db


class TestGetComponentBreakdown:
    def test_anchors_to_latest_data_when_no_target_time(self):
        """Without target_time, scoring uses the latest-data timestamp."""
        db = _db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls:
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_for_time.return_value = {
                "mcdm_index": 50.0,
                "vehicle_count": 800,
                "vru_count": 5,
            }
            from app.services.chat_service import _execute_get_component_breakdown
            _execute_get_component_breakdown({"intersection": "birch"})
            _, scored_at = mcdm.calculate_safety_score_for_time.call_args[0]
            assert scored_at == ANCHOR


class TestGetTrendData:
    def test_anchors_end_time_to_latest_data(self):
        """The trend window's end pins to the latest-data timestamp."""
        db = _db_at_anchor()
        with patch("app.services.chat_service.get_db_client", return_value=db), \
             patch("app.services.chat_service.MCDMSafetyIndexService") as mcdm_cls:
            mcdm = mcdm_cls.return_value
            mcdm.get_available_intersections.return_value = ["birch_st-w_broad_st"]
            mcdm.calculate_safety_score_trend.return_value = [
                {"time_bin": ANCHOR - timedelta(hours=1), "mcdm_index": 50.0}
            ]
            from app.services.chat_service import _execute_get_trend_data
            _execute_get_trend_data({"intersection": "birch", "days_back": 7})
            args = mcdm.calculate_safety_score_trend.call_args[0]
            # signature: (intersection, start_time, end_time)
            _, start_time, end_time = args
            assert end_time == ANCHOR
            assert end_time - start_time == timedelta(days=7)


# ---------------------------------------------------------------------------
# Morning-briefing deterministic fallback
# ---------------------------------------------------------------------------

class TestMorningBriefingFallback:
    """
    The deterministic morning-briefing path is a *fallback* — it runs only
    when the OpenAI agent is unavailable, never as the default for the
    canonical UC1 query.
    """

    def _briefing_messages(self):
        return [{
            "role": "user",
            "content": "Give me a morning safety briefing for all intersections.",
        }]

    def _llm_response(self, text):
        """A mock OpenAI response carrying a final (non-tool-call) reply."""
        msg = MagicMock()
        msg.content = text
        msg.tool_calls = None
        msg.model_dump.return_value = {"role": "assistant", "content": text}
        choice = MagicMock()
        choice.finish_reason = "stop"
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    def test_briefing_uses_agent_when_openai_available(self):
        """With a working key, the briefing goes through the agent loop —
        not the deterministic template."""
        with patch("app.services.chat_service.settings") as mock_settings, \
             patch("openai.OpenAI") as openai_cls:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.OPENAI_MAX_TOKENS = 1024
            client = openai_cls.return_value
            client.chat.completions.create.return_value = self._llm_response(
                "Agent-generated briefing."
            )

            from app.services.chat_service import run_chat
            reply = run_chat(self._briefing_messages())

            client.chat.completions.create.assert_called()
            assert reply == "Agent-generated briefing."

    def test_briefing_falls_back_when_openai_errors(self):
        """If the OpenAI call fails, the briefing degrades to the
        deterministic fast path instead of erroring."""
        from openai import OpenAIError
        with patch("app.services.chat_service.settings") as mock_settings, \
             patch("openai.OpenAI") as openai_cls, \
             patch(
                 "app.services.chat_service._execute_compare_intersections",
                 return_value={
                     "rankings": [{
                         "intersection": "e_broad_st-n_washington_st",
                         "mcdm": 75.0, "vehicle_count": 200, "vru_count": 20,
                         "incident_count": 4, "speed_variance": 18.0,
                     }],
                     "data_time": "2025-11-01 17:00:00",
                 },
             ):
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.OPENAI_MAX_TOKENS = 1024
            client = openai_cls.return_value
            client.chat.completions.create.side_effect = OpenAIError(
                "insufficient_quota"
            )

            from app.services.chat_service import run_chat
            reply = run_chat(self._briefing_messages())

            client.chat.completions.create.assert_called()
            assert "Morning safety briefing" in reply
            assert "E Broad St & N Washington St" in reply

    def test_non_briefing_query_does_not_fall_back_on_openai_error(self):
        """A non-briefing query must surface OpenAI failures — the
        deterministic path can only answer the briefing."""
        from openai import OpenAIError
        with patch("app.services.chat_service.settings") as mock_settings, \
             patch("openai.OpenAI") as openai_cls:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.OPENAI_MAX_TOKENS = 1024
            client = openai_cls.return_value
            client.chat.completions.create.side_effect = OpenAIError("boom")

            from app.services.chat_service import run_chat
            with pytest.raises(OpenAIError):
                run_chat([{"role": "user", "content": "What is the weather?"}])


class TestMorningBriefingOutput:
    """Quality of the deterministic morning-briefing text."""

    def test_ranked_rows_use_distinct_wording(self):
        """Each ranked row must be described by its own position — only the
        first is 'highest'."""
        with patch(
            "app.services.chat_service._execute_compare_intersections",
            return_value={
                "rankings": [
                    {"intersection": "e_broad_st-n_washington_st", "mcdm": 75.0,
                     "vehicle_count": 200, "vru_count": 20, "incident_count": 4,
                     "speed_variance": 18.0},
                    {"intersection": "birch_st-w_broad_st", "mcdm": 50.0,
                     "vehicle_count": 100, "vru_count": 10, "incident_count": 2,
                     "speed_variance": 12.0},
                ],
                "data_time": "2025-11-01 17:00:00",
            },
        ):
            from app.services.chat_service import _run_morning_briefing_fast_path
            reply = _run_morning_briefing_fast_path()
            assert reply.count("ranks highest") == 1
            assert "ranks second" in reply

    def test_does_not_claim_false_causation(self):
        """The fast path lacks CRITIC-weighted contributions, so it must not
        claim a criterion 'drove' the score — it reports raw figures only."""
        with patch(
            "app.services.chat_service._execute_compare_intersections",
            return_value={
                "rankings": [
                    {"intersection": "e_broad_st-n_washington_st", "mcdm": 75.0,
                     "vehicle_count": 1089, "vru_count": 59, "incident_count": 11,
                     "speed_variance": 37.0},
                ],
                "data_time": "2025-11-01 17:00:00",
            },
        ):
            from app.services.chat_service import _run_morning_briefing_fast_path
            reply = _run_morning_briefing_fast_path()
            assert "driven by" not in reply.lower()
            # raw figures are still surfaced, just not as a causal claim
            assert "1,089 vehicles" in reply
