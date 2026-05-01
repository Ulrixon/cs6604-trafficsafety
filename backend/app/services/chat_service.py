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
import re
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
                    "target_time": {
                        "type": "string",
                        "description": (
                            "ISO-8601 datetime for a historical query, e.g. "
                            "'2024-11-01T17:00:00'. Omit for current/latest data."
                        ),
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
                "avg speed, speed variance, incident count) for a specific "
                "intersection and 15-minute bin. Optionally query a historical time."
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
                    "target_time": {
                        "type": "string",
                        "description": (
                            "ISO-8601 datetime for a historical query. "
                            "Omit for current/latest data."
                        ),
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
    {
        "type": "function",
        "function": {
            "name": "get_trend_data",
            "description": (
                "Return a time-series summary of safety scores for a single "
                "intersection over a lookback window (default 7 days). "
                "Use this for trend questions: 'Is X getting safer?', "
                "'Show me the 30-day trend', 'What was the peak risk day last week?'. "
                "Returns min/max/mean MCDM scores, a direction indicator, and "
                "up to 20 representative time-bin snapshots."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intersection": {
                        "type": "string",
                        "description": "Intersection name.",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "How many days of history to analyse (default 7, max 30).",
                        "default": 7,
                    },
                },
                "required": ["intersection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": (
                "Execute a read-only SQL SELECT query directly against the VTTSI "
                "PostgreSQL database. Use this for any ad-hoc exploration that the "
                "other tools do not cover: listing schema, counting records, filtering "
                "by date range, joining tables, etc. "
                "Available tables: vehicle-count, vru-count, speed-distribution, "
                "safety-event, bsm, psm, intersections, lrs_road_intersections, "
                "vdot_crashes, vdot_crashes_with_intersections, "
                "safety_indices_hourly, safety_indices_daily, safety_indices_realtime, "
                "intersection_cameras. "
                "Results are capped at 100 rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A valid PostgreSQL SELECT statement. "
                            "Must start with SELECT or WITH. "
                            "Do not include LIMIT if you want the default cap of 100 rows."
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are SafetyChat, an expert assistant for the Virginia Tech
Transportation Safety Index (VTTSI) system. VTTSI monitors real-time intersection
safety using connected-vehicle telemetry and historical crash data from VDOT.

You have access to five tools:
  • get_safety_score         – current RT-SI, MCDM, and blended scores for one intersection
  • get_component_breakdown  – criterion values (speed, VRU, incidents) for one intersection
  • get_historical_baseline  – Empirical Bayes baseline and crash history
  • compare_intersections    – rank all intersections by any metric
  • get_trend_data           – MCDM score trend over 7–30 days for one intersection
  • run_sql_query            – execute any read-only SQL SELECT against the live database

Database schema summary (use run_sql_query to explore further):
  • "vehicle-count"    – columns: intersection, publish_timestamp (µs), count
  • "vru-count"        – columns: intersection, publish_timestamp (µs), count
  • "speed-distribution" – columns: intersection, publish_timestamp (µs), speed_interval, count
  • "safety-event"     – columns: intersection, publish_timestamp (µs), event_type
  • intersections      – columns: intersection_id, intersection_name, latitude, longitude
  • vdot_crashes       – VDOT crash records 2017-2024
  • vdot_crashes_with_intersections – crashes linked to monitored intersections
  • safety_indices_hourly / safety_indices_daily – pre-aggregated safety index snapshots
  • bsm, psm           – raw connected-vehicle Basic/Personal Safety Messages
  • intersection_cameras – camera feeds per intersection

VTTSI Formula Reference (exact definitions from the paper — cite these when asked):

=== RT-SI (Real-Time Safety Index) ===

Step 1 — Historical severity-weighted crash rate (Eq. 1):
  r_i = Σ_s(w_s · C_{i,s}) / E_i
  where C_{i,s} = crash counts by severity s, weights: w_Fatal=10, w_Injury=3, w_PDO=1,
  E_i = exposure (entering vehicle volume), summed over VDOT 2017–2024 records.

Step 2 — Global mean rate (Eq. 2):
  r_0 = (1/N) · Σ_{i,t in 2017–2024} Y_{i,t}
  where Y_{i,t} = severity-weighted crash count for site i, 15-min bin t; N = total (i,t) combinations.

Step 3 — Empirical Bayes stabilization (Eq. 3):
  r̂_{i,t}^EB(λ) = (1/(1+λ)) · Y_{i,t}  +  (λ/(1+λ)) · r_0
  Optimal λ* = 10,000 (chosen by minimizing Poisson log-loss on 2025 hold-out data).
  Production uses fixed λ = λ* = 10,000.

Step 4 — Real-time uplift factors (Eqs. 7–9), each bounded [0, 1]:
  F^spd_{i,t} = min(1, k1 · (v_i^FF − v̄_{i,t}) / v_i^FF)   [speed deficit vs. free-flow speed]
  F^var_{i,t} = min(1, k2 · σ_{v,i,t} / (v̄_{i,t} + ε))     [speed variance uplift]
  F^conf_{i,t}= min(1, k3 · (turningVol_{i,t} · V^vru_{i,t}) / scale)  [VRU-vehicle conflict exposure]

Step 5 — Combined uplift factor (Eq. 10):
  U_{i,t} = 1 + β1·F^spd_{i,t} + β2·F^var_{i,t} + β3·F^conf_{i,t}

Step 6 — Sub-indices (Eqs. 11–14):
  G_{i,t}   = min(1, k4 · V^vru_{i,t} / (V^veh_{i,t} + ε))   [VRU exposure ratio]
  VRU_{i,t} = γ · r̂_i · U_{i,t} · G_{i,t}
  H_{i,t}   = min(1, k5 · V^veh_{i,t} / capacity_i)            [vehicle volume ratio]
  VEH_{i,t} = γ · r̂_i · U_{i,t} · H_{i,t}

Step 7 — Combined and min-max scaled to [0, 100] (Eqs. 15–16):
  COMB_{i,t} = ω_vru · VRU_{i,t} + ω_veh · VEH_{i,t}   (ω_vru + ω_veh = 1)
  SI^RT_{i,t} = 100 · (COMB_{i,t} − min) / (max − min)

=== MCDM Safety Index ===

Five criteria (Eq. 17): C = {vehicle_count, vru_count, avg_speed, speed_variance, incident_count}
Decision matrix: each row = (intersection i, 15-min bin t); each column = criterion value x_{aj}.

Step 1 — Min-max normalization (Eq. 18):
  x̃_{aj} = (x_{aj} − min_a x_{aj}) / (max_a x_{aj} − min_a x_{aj})   [0 if no variance]

Step 2 — CRITIC weights (Eqs. 19–21), recomputed every 24 h over last 24 h of data:
  σ_j = std dev of normalized column j
  Γ_j = Σ_{k=1}^{5} (1 − ρ_{jk})   [conflict/contrast of criterion j; ρ_{jk} = Pearson correlation]
  I_j = σ_j · Γ_j   [information content]
  w_j = I_j / Σ_k I_k   (or 1/5 if all I_k = 0)

Step 3a — SAW score (Eqs. 22–23):
  Sa^SAW = Σ_{j∈C} w_j · x̃_{aj}
  Then min-max scaled to 0–100 (50 if no variance).

Step 3b — EDAS score (Eqs. 24–32):
  x̄_j = mean of x̃_{aj} over all alternatives
  PDA_{aj} = max(0, (x̃_{aj} − x̄_j) / x̄_j)   [positive distance from average]
  NDA_{aj} = max(0, (x̄_j − x̃_{aj}) / x̄_j)   [negative distance from average]
  SP_a = Σ_j w_j · PDA_{aj};   SN_a = Σ_j w_j · NDA_{aj}
  SP^norm_a = SP_a / max_a SP_a;   SN^norm_a = SN_a / max_a SN_a
  Sa^EDAS = 0.5 · (SP^norm_a + (1 − SN^norm_a))
  Then min-max scaled to 0–100 (50 if no variance).

Step 3c — CODAS score (Eqs. 33–39):
  z_{aj} = w_j · x̃_{aj}   [weighted normalized matrix]
  z_j^- = min_a z_{aj}   [negative-ideal solution]
  E_a = sqrt(Σ_j (z_{aj} − z_j^-)²)   [Euclidean distance from NIS]
  T_a = Σ_j |z_{aj} − z_j^-|            [Taxicab distance from NIS]
  Ψ_{ab} = E_a − E_b   (if ≠ 0),  else T_a − T_b   [pairwise assessment]
  Sa^CODAS = Σ_b Ψ_{ab}
  Then min-max scaled to 0–100 (50 if no variance).

Step 4 — Hybrid MCDM via second CRITIC aggregation (Eqs. 40–41):
  Form N×3 matrix M = [EDAS_a, CODAS_a, SAW_a]; apply CRITIC to get method weights W_E, W_C, W_S.
  SI^MCDM_a = M · W  (weighted sum of the three method scores, 0–100, higher = higher risk).

=== Blended Final Index (Eq. 42) ===
  SI^Final_{i,t} = α · SI^RT_{i,t} + (1 − α) · SI^MCDM_{i,t}
  Default α = 0.7 (30% MCDM, 70% RT-SI). α is user-adjustable.

Risk levels: 0–40 = low risk, 41–70 = moderate risk, 71–100 = high risk.

Guidelines:
- Prefer the high-level tools for routine safety questions; use run_sql_query for
  ad-hoc exploration, schema discovery, or questions the other tools cannot answer.
- For trend/historical questions use get_trend_data first; fall back to run_sql_query
  for custom time ranges or cross-intersection trend comparisons.
- For historical point-in-time questions pass target_time (ISO-8601) to get_safety_score
  or get_component_breakdown.
- Always call a tool before making numerical claims; never fabricate numbers.
- Only issue SELECT queries — never INSERT, UPDATE, DELETE, DROP, or DDL.
- Morning briefing pattern: call compare_intersections (all, blended), then
  get_component_breakdown for the top 2 sites; mention 7-day trend if available.
- If a score is elevated (>60), explain which criterion is driving it.
- Translate scores: 0–40 = low risk, 41–70 = moderate, 71–100 = high risk.
- If data is unavailable, say so and suggest checking for sensor outages.
- Be concise and actionable; operators are working under time pressure.
- Current date/time: {current_datetime}
- IMPORTANT: The timestamp shown above is the latest available sensor data time, NOT the server clock.
  When users say "yesterday", "last week", "5 PM today", etc., interpret those relative to the latest
  data time shown above — NOT the current calendar date.
"""

# ── Tool execution ────────────────────────────────────────────────────────────


_ROAD_SUFFIXES = {"st", "rd", "ave", "blvd", "dr", "ln", "ct", "pl", "way", "hwy"}


def _resolve_intersection(name: str, available: list[str]) -> str | None:
    """
    Match a natural-language intersection query to an available intersection name.

    Strategy:
    1. Direct substring match after stripping all non-alphanumeric characters.
    2. Token overlap: all significant query tokens (excluding common road suffixes)
       must appear in the candidate's token set; pick the highest-overlap candidate.
    """
    query_norm = re.sub(r"[^a-z0-9]", "", name.lower())
    query_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))

    best: str | None = None
    best_score = 0

    for avail in available:
        avail_norm = re.sub(r"[^a-z0-9]", "", avail.lower())
        # 1. Direct substring match
        if query_norm in avail_norm or avail_norm in query_norm:
            return avail
        # 2. Significant-token overlap
        avail_tokens = set(re.findall(r"[a-z0-9]+", avail.lower()))
        sig_query = query_tokens - _ROAD_SUFFIXES
        if sig_query and sig_query.issubset(avail_tokens):
            score = len(sig_query)
            if score > best_score:
                best_score = score
                best = avail

    return best


def _execute_get_safety_score(args: dict) -> dict:
    """Tool: get_safety_score"""
    intersection_query = args.get("intersection", "")
    alpha = float(args.get("alpha", 0.7))
    target_time_str = args.get("target_time")

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)
        rt_si_svc = RTSIService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found. Available: {available}"}

        if target_time_str:
            try:
                now = datetime.fromisoformat(target_time_str)
            except ValueError:
                return {"error": f"Invalid target_time format: '{target_time_str}'. Use ISO-8601."}
        else:
            # Anchor to latest available data so server clock drift doesn't cause empty results
            latest_row = db.execute_query('SELECT MAX(publish_timestamp) AS max_ts FROM "vehicle-count"')
            if latest_row and latest_row[0].get("max_ts"):
                now = datetime.fromtimestamp(latest_row[0]["max_ts"] / 1_000_000)
            else:
                now = datetime.now()

        # MCDM score
        mcdm_result = mcdm_svc.calculate_safety_score_for_time(intersection, now)
        mcdm_score = float(mcdm_result.get("mcdm_index", 0.0)) if mcdm_result else 0.0

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
    target_time_str = args.get("target_time")

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found."}

        if target_time_str:
            try:
                query_time = datetime.fromisoformat(target_time_str)
            except ValueError:
                return {"error": f"Invalid target_time format: '{target_time_str}'. Use ISO-8601."}
        else:
            # Anchor to latest available data so server clock drift doesn't cause empty results
            latest_row = db.execute_query('SELECT MAX(publish_timestamp) AS max_ts FROM "vehicle-count"')
            if latest_row and latest_row[0].get("max_ts"):
                query_time = datetime.fromtimestamp(latest_row[0]["max_ts"] / 1_000_000)
            else:
                query_time = datetime.now()

        result = mcdm_svc.calculate_safety_score_for_time(intersection, query_time)
        if not result:
            return {"error": "No MCDM data available for this intersection."}

        return {
            "intersection": intersection,
            "query_time": query_time.isoformat(),
            "lookback_hours": lookback_hours,
            "criterion_values": {
                "vehicle_count": result.get("vehicle_count"),
                "vru_count": result.get("vru_count"),
                "avg_speed": result.get("avg_speed"),
                "speed_variance": result.get("speed_variance"),
                "incident_count": result.get("incident_count"),
                "near_miss_count": result.get("near_miss_count"),
            },
            "saw_score": round(result.get("saw_score", 0.0), 2),
            "edas_score": round(result.get("edas_score", 0.0), 2),
            "codas_score": round(result.get("codas_score", 0.0), 2),
            "mcdm_score": round(result.get("mcdm_index", 0.0), 2),
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
                mcdm_result = mcdm_svc.calculate_safety_score_for_time(intersection, datetime.now())
                mcdm_score = float(mcdm_result.get("mcdm_index", 0.0)) if mcdm_result else 0.0
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


def _execute_get_trend_data(args: dict) -> dict:
    """Tool: get_trend_data — returns MCDM score trend summary for one intersection."""
    intersection_query = args.get("intersection", "")
    days_back = min(int(args.get("days_back", 7)), 30)

    try:
        db = get_db_client()
        mcdm_svc = MCDMSafetyIndexService(db)

        available = mcdm_svc.get_available_intersections()
        intersection = _resolve_intersection(intersection_query, available)
        if not intersection:
            return {"error": f"Intersection '{intersection_query}' not found. Available: {available}"}

        # Anchor to the latest data available in the DB (server clock ≠ data clock)
        latest_row = db.execute_query('SELECT MAX(publish_timestamp) AS max_ts FROM "vehicle-count"')
        if latest_row and latest_row[0].get("max_ts"):
            end_time = datetime.fromtimestamp(latest_row[0]["max_ts"] / 1_000_000)
        else:
            end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        trend = mcdm_svc.calculate_safety_score_trend(intersection, start_time, end_time)
        if not trend:
            return {
                "intersection": intersection,
                "days_back": days_back,
                "message": "No trend data available for this period.",
            }

        scores = [t["mcdm_index"] for t in trend]
        avg_score = round(sum(scores) / len(scores), 2)
        max_score = round(max(scores), 2)
        min_score = round(min(scores), 2)

        # Direction: compare first-third vs last-third average
        third = max(1, len(scores) // 3)
        early_avg = sum(scores[:third]) / third
        recent_avg = sum(scores[-third:]) / third
        if recent_avg < early_avg - 2:
            direction = "improving (score decreasing)"
        elif recent_avg > early_avg + 2:
            direction = "worsening (score increasing)"
        else:
            direction = "stable"

        # Sample up to 20 representative snapshots
        step = max(1, len(trend) // 20)
        snapshots = [
            {
                "time": str(t["time_bin"]),
                "mcdm_index": round(t["mcdm_index"], 2),
                "vehicle_count": t.get("vehicle_count"),
                "vru_count": t.get("vru_count"),
                "incident_count": t.get("incident_count"),
            }
            for t in trend[::step][:20]
        ]

        return {
            "intersection": intersection,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "days_back": days_back,
            "total_bins": len(trend),
            "avg_mcdm_score": avg_score,
            "max_mcdm_score": max_score,
            "min_mcdm_score": min_score,
            "trend_direction": direction,
            "snapshots": snapshots,
        }
    except Exception as e:
        logger.error(f"get_trend_data tool error: {e}", exc_info=True)
        return {"error": str(e)}


_SQL_BLOCK = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|copy|vacuum|reindex)\b",
    re.IGNORECASE,
)
_MAX_SQL_ROWS = 100


def _execute_run_sql(args: dict) -> dict:
    """Tool: run_sql_query — executes a read-only SELECT against the VTTSI DB."""
    sql = args.get("sql", "").strip()

    # Safety: only allow SELECT / WITH (CTEs)
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        return {"error": "Only SELECT statements are permitted."}
    if _SQL_BLOCK.search(sql):
        return {"error": "Statement contains a disallowed keyword."}

    # Inject LIMIT if absent to cap results
    if not re.search(r"\blimit\b", sql, re.IGNORECASE):
        sql = f"{sql.rstrip(';')} LIMIT {_MAX_SQL_ROWS}"

    try:
        db = get_db_client()
        rows = db.execute_query(sql)
        return {
            "row_count": len(rows),
            "rows": rows,
            "note": f"Results capped at {_MAX_SQL_ROWS} rows." if len(rows) == _MAX_SQL_ROWS else None,
        }
    except Exception as e:
        logger.error(f"run_sql_query tool error: {e}", exc_info=True)
        return {"error": str(e)}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "get_safety_score": _execute_get_safety_score,
    "get_component_breakdown": _execute_get_component_breakdown,
    "get_historical_baseline": _execute_get_historical_baseline,
    "compare_intersections": _execute_compare_intersections,
    "get_trend_data": _execute_get_trend_data,
    "run_sql_query": _execute_run_sql,
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

    # Anchor displayed time to latest data in DB (server clock may drift)
    try:
        db = get_db_client()
        latest_row = db.execute_query('SELECT MAX(publish_timestamp) AS max_ts FROM "vehicle-count"')
        if latest_row and latest_row[0].get("max_ts"):
            data_latest = datetime.fromtimestamp(latest_row[0]["max_ts"] / 1_000_000)
            current_datetime_str = data_latest.strftime("%Y-%m-%d %H:%M") + " (latest data)"
        else:
            current_datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception:
        current_datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build the message list with system prompt first
    system_msg = {
        "role": "system",
        "content": SYSTEM_PROMPT.replace("{current_datetime}", current_datetime_str),
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
