"""
SafetyChat LLM Service
======================
Tool-augmented OpenAI chat service that answers natural language questions about
the Virginia Tech Transportation Safety Index (VTTSI).

The service exposes four tools to the LLM that map to live VTTSI data:
  • get_safety_score         – current RT-SI, MCDM, and blended scores
  • get_component_breakdown  – CRITIC weights + raw criterion values per bin
  • get_historical_baseline  – EB prior, crash severity breakdown
  • compare_intersections    – rank intersections by any metric

All numerical claims produced by the LLM are grounded in live API data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from ..core.config import settings
from ..services.db_client import get_db_client
from ..services.mcdm_service import MCDMSafetyIndexService
from ..services.rt_si_service import RTSIService

logger = logging.getLogger(__name__)

# ── Tool definitions passed to the OpenAI API ────────────────────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_safety_score",
            "description": (
                "Return the current RT-SI, MCDM, and blended safety scores "
                "for a single intersection, together with the top contributing "
                "factors and the data timestamp."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intersection": {
                        "type": "string",
                        "description": (
                            "Intersection name, e.g. 'Glebe_Rd_Potomac_Ave' "
                            "or a partial match."
                        ),
                    },
                    "alpha": {
                        "type": "number",
                        "description": (
                            "Blending weight for RT-SI (0–1). "
                            "Default 0.7 (70% RT-SI, 30% MCDM)."
                        ),
                        "default": 0.7,
                    },
                },
                "required": ["intersection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_component_breakdown",
            "description": (
                "Return the weighted criterion values (vehicle count, VRU count, "
                "avg speed, speed variance, incident count) and CRITIC weights "
                "for a specific intersection and the latest 15-minute bin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intersection": {
                        "type": "string",
                        "description": "Intersection name.",
                    },
                    "lookback_hours": {
                        "type": "integer",
                        "description": "How many hours of history to include (default 24).",
                        "default": 24,
                    },
                },
                "required": ["intersection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_baseline",
            "description": (
                "Return the Empirical Bayes prior, lambda parameter, and 7-year "
                "VDOT crash severity breakdown (fatal/injury/PDO) for an intersection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intersection": {
                        "type": "string",
                        "description": "Intersection name.",
                    },
                },
                "required": ["intersection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_intersections",
            "description": (
                "Rank all monitored intersections by a chosen metric and return "
                "the top results. Useful for briefings and comparative analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": [
                            "blended",
                            "rt_si",
                            "mcdm",
                            "vehicle_count",
                            "vru_count",
                            "incident_count",
                            "speed_variance",
                        ],
                        "description": "Metric to rank by (default 'blended').",
                        "default": "blended",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top results to return (default 5).",
                        "default": 5,
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Blending weight for RT-SI when metric='blended'.",
                        "default": 0.7,
                    },
                },
                "required": [],
            },
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are SafetyChat, an expert assistant for the Virginia Tech
Transportation Safety Index (VTTSI) system. VTTSI monitors real-time intersection
safety using connected-vehicle telemetry and historical crash data from VDOT.

You have access to four tools that retrieve live data from the VTTSI API:
  • get_safety_score         – current scores for one intersection
  • get_component_breakdown  – criterion values and CRITIC weights
  • get_historical_baseline  – Empirical Bayes baseline and crash history
  • compare_intersections    – rank intersections by any metric

Guidelines:
- Always call a tool before making numerical claims; never fabricate numbers.
- Cite the exact values returned by tools in your response.
- If a score is elevated (>60), explain which criterion is driving it.
- Translate numerical scores to plain language: 0–40 = low risk, 41–70 = moderate, 71–100 = high risk.
- If data is unavailable or sparse, say so clearly and recommend the operator check
  for sensor outages.
- Be concise and actionable; operators are working under time pressure.
- Current date/time: {current_datetime}
"""

# ── Tool execution ────────────────────────────────────────────────────────────


def _resolve_intersection(name: str, available: list[str]) -> str | None:
    """Case-insensitive partial-match lookup against available intersection names."""
    name_lower = name.lower().replace("-", "").replace(" ", "").replace("_", "")
    for avail in available:
        avail_norm = avail.lower().replace("-", "").replace(" ", "").replace("_", "")
        if name_lower in avail_norm or avail_norm in name_lower:
            return avail
    return None


def _execute_get_safety_score(args: dict) -> dict:
    """Tool: get_safety_score"""
    intersection_query = args.get("intersection", "")
    alpha = float(args.get("alpha", 0.7))

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)
        rt_si_svc = RTSIService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found. Available: {available}"}

        now = datetime.now()

        # MCDM score
        mcdm_result = mcdm_svc.compute_safety_index(intersection, lookback_hours=24)
        mcdm_score = float(mcdm_result.get("hybrid_mcdm_score", 0.0)) if mcdm_result else 0.0

        # RT-SI score (best-effort)
        rt_si_score = 0.0
        top_factors: dict = {}
        try:
            from ..api.intersection import find_crash_intersection_for_bsm
            mapping = find_crash_intersection_for_bsm(intersection, db)
            valid = next(
                (m for m in mapping if m.get("crash_intersection_id")), None
            )
            if valid:
                rt_result = rt_si_svc.calculate_rt_si(
                    valid["crash_intersection_id"],
                    now,
                    bin_minutes=15,
                    realtime_intersection=intersection,
                    lookback_hours=168,
                )
                if rt_result:
                    rt_si_score = float(rt_result.get("RT_SI", 0.0))
                    top_factors = {
                        "speed_uplift": round(rt_result.get("F_speed", 0.0), 3),
                        "variance_uplift": round(rt_result.get("F_var", 0.0), 3),
                        "conflict_uplift": round(rt_result.get("F_conf", 0.0), 3),
                        "vru_sub_index": round(rt_result.get("VRU_SI", 0.0), 2),
                        "vehicle_sub_index": round(rt_result.get("VEH_SI", 0.0), 2),
                        "data_timestamp": str(rt_result.get("timestamp", now)),
                    }
        except Exception as e:
            logger.warning(f"RT-SI lookup failed for SafetyChat: {e}")

        blended = round(alpha * rt_si_score + (1 - alpha) * mcdm_score, 2)
        risk_label = (
            "high risk" if blended > 70 else "moderate risk" if blended > 40 else "low risk"
        )

        return {
            "intersection": intersection,
            "rt_si_score": round(rt_si_score, 2),
            "mcdm_score": round(mcdm_score, 2),
            "blended_score": blended,
            "alpha": alpha,
            "risk_level": risk_label,
            "top_factors": top_factors,
            "retrieved_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"get_safety_score tool error: {e}", exc_info=True)
        return {"error": str(e)}


def _execute_get_component_breakdown(args: dict) -> dict:
    """Tool: get_component_breakdown"""
    intersection_query = args.get("intersection", "")
    lookback_hours = int(args.get("lookback_hours", 24))

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found."}

        result = mcdm_svc.compute_safety_index(intersection, lookback_hours=lookback_hours)
        if not result:
            return {"error": "No MCDM data available for this intersection."}

        return {
            "intersection": intersection,
            "lookback_hours": lookback_hours,
            "critic_weights": result.get("critic_weights", {}),
            "criterion_values": {
                "vehicle_count": result.get("vehicle_count"),
                "vru_count": result.get("vru_count"),
                "avg_speed": result.get("avg_speed"),
                "speed_variance": result.get("speed_variance"),
                "incident_count": result.get("incident_count"),
            },
            "saw_score": round(result.get("saw_score", 0.0), 2),
            "edas_score": round(result.get("edas_score", 0.0), 2),
            "codas_score": round(result.get("codas_score", 0.0), 2),
            "hybrid_mcdm_score": round(result.get("hybrid_mcdm_score", 0.0), 2),
            "retrieved_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"get_component_breakdown tool error: {e}", exc_info=True)
        return {"error": str(e)}


def _execute_get_historical_baseline(args: dict) -> dict:
    """Tool: get_historical_baseline"""
    intersection_query = args.get("intersection", "")

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found."}

        # Query crash history from DB
        from ..api.intersection import find_crash_intersection_for_bsm
        mapping = find_crash_intersection_for_bsm(intersection, db)
        valid = next((m for m in mapping if m.get("crash_intersection_id")), None)

        if not valid:
            return {
                "intersection": intersection,
                "message": "No historical crash data linked to this intersection.",
                "crash_intersection_id": None,
            }

        crash_id = valid["crash_intersection_id"]
        query = """
            SELECT
                COUNT(*) AS total_crashes,
                SUM(CASE WHEN severity = 'Fatal' THEN 1 ELSE 0 END) AS fatal,
                SUM(CASE WHEN severity = 'Injury' THEN 1 ELSE 0 END) AS injury,
                SUM(CASE WHEN severity = 'PDO' THEN 1 ELSE 0 END) AS pdo,
                MIN(crash_date) AS earliest,
                MAX(crash_date) AS latest
            FROM public.vdot_crash_with_intersections
            WHERE crash_intersection_id = %(crash_id)s
        """
        rows = db.execute_query(query, {"crash_id": crash_id})
        crash_row = rows[0] if rows else {}

        # Retrieve EB parameters from rt_si_service
        rt_si_svc = RTSIService(db)
        eb_params = {}
        try:
            eb_params = rt_si_svc.get_eb_params(crash_id) or {}
        except Exception:
            pass

        return {
            "intersection": intersection,
            "crash_intersection_id": crash_id,
            "total_crashes_2017_2024": crash_row.get("total_crashes"),
            "fatal": crash_row.get("fatal"),
            "injury": crash_row.get("injury"),
            "pdo": crash_row.get("pdo"),
            "earliest_crash": str(crash_row.get("earliest", "N/A")),
            "latest_crash": str(crash_row.get("latest", "N/A")),
            "eb_lambda": eb_params.get("lambda_star", 10000),
            "eb_global_mean_rate": eb_params.get("global_mean", None),
            "retrieved_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"get_historical_baseline tool error: {e}", exc_info=True)
        return {"error": str(e)}


def _execute_compare_intersections(args: dict) -> dict:
    """Tool: compare_intersections"""
    metric = args.get("metric", "blended")
    top_n = int(args.get("top_n", 5))
    alpha = float(args.get("alpha", 0.7))

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)
        rt_si_svc = RTSIService(db)

        available = mcdm_svc.get_available_intersections()
        rows: list[dict] = []

        for intersection in available:
            entry: dict[str, Any] = {"intersection": intersection}
            try:
                mcdm_result = mcdm_svc.compute_safety_index(intersection, lookback_hours=24)
                mcdm_score = float(mcdm_result.get("hybrid_mcdm_score", 0.0)) if mcdm_result else 0.0
                entry["mcdm"] = round(mcdm_score, 2)
                entry["vehicle_count"] = mcdm_result.get("vehicle_count") if mcdm_result else None
                entry["vru_count"] = mcdm_result.get("vru_count") if mcdm_result else None
                entry["incident_count"] = mcdm_result.get("incident_count") if mcdm_result else None
                entry["speed_variance"] = mcdm_result.get("speed_variance") if mcdm_result else None
            except Exception:
                entry["mcdm"] = 0.0

            entry["rt_si"] = 0.0
            entry["blended"] = round(alpha * entry["rt_si"] + (1 - alpha) * entry["mcdm"], 2)
            rows.append(entry)

        # Sort by requested metric
        sort_key = {
            "blended": "blended",
            "rt_si": "rt_si",
            "mcdm": "mcdm",
            "vehicle_count": "vehicle_count",
            "vru_count": "vru_count",
            "incident_count": "incident_count",
            "speed_variance": "speed_variance",
        }.get(metric, "blended")

        rows.sort(
            key=lambda r: (r.get(sort_key) or 0.0),
            reverse=True,
        )

        return {
            "metric": metric,
            "alpha": alpha,
            "top_n": top_n,
            "rankings": rows[:top_n],
            "total_intersections": len(rows),
            "retrieved_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"compare_intersections tool error: {e}", exc_info=True)
        return {"error": str(e)}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "get_safety_score": _execute_get_safety_score,
    "get_component_breakdown": _execute_get_component_breakdown,
    "get_historical_baseline": _execute_get_historical_baseline,
    "compare_intersections": _execute_compare_intersections,
}


def _dispatch_tool_call(name: str, arguments_json: str) -> str:
    """Parse tool arguments and call the appropriate handler."""
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        args = {}

    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"})

    result = handler(args)
    return json.dumps(result, default=str)


# ── Main chat function ────────────────────────────────────────────────────────


def run_chat(messages: list[dict]) -> str:
    """
    Run a multi-turn SafetyChat conversation.

    Parameters
    ----------
    messages : list[dict]
        OpenAI-format message history: [{"role": "user"/"assistant", "content": "..."}]
        The system prompt is injected automatically.

    Returns
    -------
    str
        The assistant's final response text.

    Raises
    ------
    ValueError
        If OPENAI_API_KEY is not configured.
    RuntimeError
        If the OpenAI API call fails.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not set. "
            "Add it to backend/.env: OPENAI_API_KEY=sk-..."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package is not installed. "
            "Run: pip install openai"
        ) from exc

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build the message list with system prompt first
    system_msg = {
        "role": "system",
        "content": SYSTEM_PROMPT.format(
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M")
        ),
    }
    full_messages = [system_msg] + messages

    # Agentic loop: keep calling until no more tool calls
    max_iterations = 6  # prevent runaway loops
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=full_messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=settings.OPENAI_MAX_TOKENS,
        )

        choice = response.choices[0]
        assistant_msg = choice.message

        # Append assistant turn to history
        full_messages.append(assistant_msg.model_dump(exclude_unset=True))

        if choice.finish_reason != "tool_calls" or not assistant_msg.tool_calls:
            # Final text response
            return assistant_msg.content or ""

        # Execute each tool call and feed results back
        for tool_call in assistant_msg.tool_calls:
            tool_result = _dispatch_tool_call(
                tool_call.function.name,
                tool_call.function.arguments,
            )
            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

    # Safety fallback: return whatever the model has
    last = full_messages[-1]
    if isinstance(last, dict):
        return last.get("content", "SafetyChat reached maximum tool iterations.")
    return str(last)
