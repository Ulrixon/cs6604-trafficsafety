#!/usr/bin/env python3
"""
VTTSI-Chat Demo Verification Harness  (SIGSPATIAL '26)
======================================================
Exercises the four demonstration use cases from the demo paper against a
running deployment, then reports on three things the paper claims but does
not measure:

  1. Functionality  – does each use case return a coherent answer (HTTP 200,
     non-empty, mentions the expected intersections)?
  2. Groundedness   – does the answer contain concrete numbers, and do they
     fall within the range of the live /api/v1/safety/index ground truth?
     (We cannot see tool calls through the public API, so this is a proxy:
     numbers present + no "I don't have access" style disclaimers.)
  3. Latency        – UC1 claims "under five seconds"; every call is timed.

This is a smoke test, not a correctness proof. Pair it with
verification_checklist.md for the judgments a human still has to make.

Usage
-----
    python tests/demo/verify_demo.py                 # hit the live deployment
    python tests/demo/verify_demo.py --base http://localhost:8000
    python tests/demo/verify_demo.py --json report.json   # also dump raw JSON

Exit code is non-zero if any FAIL-level check trips.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field

try:
    import requests
except ImportError:
    sys.exit(
        "verify_demo.py needs the 'requests' package.\n"
        "Run it inside the project environment, or: pip install requests"
    )

DEFAULT_BASE = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app"

# Soft latency budget (seconds). Over budget is a WARN, not a FAIL — the
# agentic loop can chain up to 6 tool calls, so cold starts will exceed this.
DEFAULT_LATENCY_BUDGET = 5.0

# Phrases that suggest the model fell back to ungrounded generation instead
# of calling a tool. Their presence is a groundedness red flag.
HALLUCINATION_FLAGS = [
    "i don't have access",
    "i do not have access",
    "i cannot access",
    "as an ai language model",
    "i'm unable to retrieve",
    "i do not have real-time",
    "i don't have real-time",
    "i cannot provide real-time",
]

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class UseCase:
    uid: str
    name: str
    user_role: str
    query: str
    # Intersection names (or distinctive fragments) the answer should mention.
    expect_intersections: list[str]
    # Tool calls the paper says this UC exercises — informational only,
    # the public API does not expose tool traces.
    expect_tools: list[str]
    latency_budget: float = DEFAULT_LATENCY_BUDGET
    notes: str = ""


# The four canonical use cases from Table 2 of the demo paper.
USE_CASES: list[UseCase] = [
    UseCase(
        uid="UC1",
        name="TMC Operator Morning Briefing",
        user_role="TMC Operator",
        query="Give me a morning safety briefing for all intersections.",
        expect_intersections=[],  # ranks all sites; no fixed name to assert
        expect_tools=["compare_intersections", "get_component_breakdown"],
        notes="Paper claims a multi-intersection answer in under five seconds.",
    ),
    UseCase(
        uid="UC2",
        name="Causal Safety Explanation for Planners",
        user_role="Planner",
        query=(
            "Why did E. Broad & N. Washington score above 70 yesterday at 5 PM? "
            "Explain which criteria drove the elevated score."
        ),
        expect_intersections=["Broad", "Washington"],
        expect_tools=["get_safety_score", "get_component_breakdown"],
        notes="Answer must name a driving criterion (speed variance, VRU, incidents).",
    ),
    UseCase(
        uid="UC3",
        name="Emergency Responder Routing",
        user_role="Dispatcher",
        query=(
            "Which of Glebe & Potomac or Birch & W. Broad has lower current risk? "
            "Recommend the safer crossing for emergency vehicle routing."
        ),
        expect_intersections=["Glebe", "Birch"],
        expect_tools=["get_safety_score"],
        notes="Recommendation must agree with the lower blended score (verify vs ground truth).",
    ),
    UseCase(
        uid="UC4",
        name="Public Stakeholder Trend Engagement",
        user_role="Official / Public",
        query="Is the Glebe & Potomac intersection getting safer over time?",
        expect_intersections=["Glebe"],
        expect_tools=["get_trend_data"],
        notes="Answer must give a trend direction (improving / worsening / stable).",
    ),
]


# ── Result types ──────────────────────────────────────────────────────────────

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_MARK = {PASS: "  ok ", WARN: " warn", FAIL: " FAIL"}


@dataclass
class Check:
    level: str
    message: str


@dataclass
class UCResult:
    uc: UseCase
    status_code: int | None = None
    latency_s: float | None = None
    reply: str = ""
    error: str = ""
    checks: list[Check] = field(default_factory=list)

    @property
    def worst(self) -> str:
        levels = [c.level for c in self.checks]
        if FAIL in levels:
            return FAIL
        if WARN in levels:
            return WARN
        return PASS


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def check_health(base: str) -> bool:
    """Confirm the deployment is up before running use cases."""
    for path in ("/health", "/docs"):
        try:
            r = requests.get(base + path, timeout=30)
            if r.ok:
                print(f"  health: {base}{path} -> {r.status_code}")
                return True
        except requests.RequestException as exc:
            print(f"  health: {base}{path} -> {exc}")
    return False


def get_tools(base: str) -> list[str]:
    """Fetch the LLM tool definitions; the paper says there are six."""
    try:
        r = requests.get(f"{base}/api/v1/chat/tools", timeout=30)
        r.raise_for_status()
        tools = r.json().get("tools", [])
        return [t.get("function", {}).get("name", "?") for t in tools]
    except requests.RequestException as exc:
        print(f"  WARN: could not fetch /api/v1/chat/tools: {exc}")
        return []


def get_ground_truth(base: str) -> list[dict]:
    """
    Ground truth from the live /api/v1/safety/index/ endpoint. Each row of that
    endpoint looks like:

        {"intersection_name": "birch_st-w_broad_st", "safety_index": 15.55,
         "index_type": "Blended", "mcdm_index": 51.82, "rt_si_index": 0.0,
         "traffic_volume": 873, ...}

    Returns a normalised list of dicts: name / blended / mcdm / rt_si / type /
    volume. An empty list just disables the numeric cross-check (UCs still run).
    """
    try:
        r = requests.get(f"{base}/api/v1/safety/index/", timeout=120)
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  WARN: could not fetch ground truth /safety/index/: {exc}")
        return []

    rows = payload if isinstance(payload, list) else payload.get("intersections", [])
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or "intersection_name" not in row:
            continue
        out.append(
            {
                "name": str(row["intersection_name"]),
                "blended": float(row.get("safety_index", 0.0) or 0.0),
                "mcdm": float(row.get("mcdm_index", 0.0) or 0.0),
                "rt_si": float(row.get("rt_si_index", 0.0) or 0.0),
                "type": str(row.get("index_type", "")),
                "volume": row.get("traffic_volume"),
            }
        )
    return out


def score_envelope(gt: list[dict]) -> tuple[float, float] | None:
    """
    Plausible 0-100 score band across sites that actually have data — spans
    blended *and* MCDM, since an answer may legitimately cite either.
    """
    vals = [
        v
        for row in gt
        if row["type"] != "No Data"
        for v in (row["blended"], row["mcdm"])
    ]
    return (min(vals), max(vals)) if vals else None


def _site_mentioned(gt_name: str, text_lower: str) -> bool:
    """
    True if the significant tokens of a ground-truth intersection name
    (road suffixes and 1-char tokens dropped) all appear in the answer text.
    """
    suffixes = {"st", "rd", "ave", "blvd", "dr", "ln", "ct", "pl", "way", "hwy"}
    tokens = {t for t in re.split(r"[^a-z0-9]+", gt_name.lower()) if t}
    significant = {t for t in tokens - suffixes if len(t) > 1}
    norm = re.sub(r"[^a-z0-9]", "", text_lower)
    return bool(significant) and all(tok in norm for tok in significant)


def ask(base: str, query: str) -> tuple[int | None, float, str, str]:
    """POST a single-turn query to SafetyChat. Returns (status, latency, reply, error)."""
    url = f"{base}/api/v1/chat/"
    body = {"messages": [{"role": "user", "content": query}]}
    started = time.perf_counter()
    try:
        r = requests.post(url, json=body, timeout=300)
        latency = time.perf_counter() - started
    except requests.RequestException as exc:
        return None, time.perf_counter() - started, "", str(exc)

    if not r.ok:
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except ValueError:
            detail = r.text[:200]
        return r.status_code, latency, "", detail
    try:
        return r.status_code, latency, r.json().get("reply", ""), ""
    except ValueError:
        return r.status_code, latency, "", "response was not JSON"


# ── Evaluation ────────────────────────────────────────────────────────────────


def evaluate(res: UCResult, gt: list[dict]) -> None:
    """Populate res.checks based on the response and live ground truth."""
    uc = res.uc
    c = res.checks.append
    envelope = score_envelope(gt)

    # --- Functionality -------------------------------------------------------
    if res.error and res.status_code is None:
        c(Check(FAIL, f"request failed: {res.error}"))
        return
    if res.status_code == 503:
        c(Check(FAIL, "503 — OPENAI_API_KEY not configured on the backend"))
        return
    if res.status_code == 402:
        c(Check(FAIL, "402 — OpenAI quota exceeded; add billing before the demo"))
        return
    if res.status_code != 200:
        c(Check(FAIL, f"HTTP {res.status_code}: {res.error}"))
        return
    c(Check(PASS, "HTTP 200"))

    reply = res.reply.strip()
    if not reply:
        c(Check(FAIL, "empty reply body"))
        return
    if len(reply) < 40:
        c(Check(WARN, f"reply suspiciously short ({len(reply)} chars)"))
    else:
        c(Check(PASS, f"reply returned ({len(reply)} chars)"))

    low = reply.lower()

    # --- Groundedness --------------------------------------------------------
    flags = [f for f in HALLUCINATION_FLAGS if f in low]
    if flags:
        c(Check(FAIL, f"ungrounded-disclaimer phrase present: {flags[0]!r}"))
    else:
        c(Check(PASS, "no ungrounded-fallback disclaimers"))

    numbers = NUMBER_RE.findall(reply)
    if not numbers:
        c(Check(WARN, "no numeric values in answer — likely not tool-grounded"))
    else:
        c(Check(PASS, f"{len(numbers)} numeric value(s) present"))
        if envelope:
            gt_min, gt_max = envelope
            scores = [float(n) for n in numbers if 0.0 <= float(n) <= 100.0]
            out_of_range = [s for s in scores if not (gt_min - 15 <= s <= gt_max + 15)]
            # 0-100 numbers wildly outside the live score envelope are suspect.
            if scores and len(out_of_range) == len(scores):
                c(Check(WARN, f"0-100 values {scores} fall outside live score range "
                               f"[{gt_min:.0f}, {gt_max:.0f}] — verify manually"))
            else:
                c(Check(PASS, f"0-100 values consistent with live range "
                               f"[{gt_min:.0f}, {gt_max:.0f}]"))

    # --- Mentions the expected intersections --------------------------------
    for frag in uc.expect_intersections:
        if frag.lower() in low:
            c(Check(PASS, f"mentions {frag!r}"))
        else:
            c(Check(WARN, f"does not mention expected intersection {frag!r}"))

    # --- UC-specific content checks -----------------------------------------
    if uc.uid == "UC1":
        # The morning briefing must reflect live risk. If the answer claims
        # everything is zero / no concern while the ground truth shows sites
        # with real scores, the briefing is wrong — not merely suboptimal.
        with_data = [r for r in gt if r["type"] != "No Data"]
        all_safe_phrases = (
            "score of 0", "scores of 0", "safety score of 0", "are at zero",
            "is at zero", "all zero", "no current risk", "no risk factors",
            "no specific concerns", "no further action",
        )
        if with_data and any(p in low for p in all_safe_phrases):
            worst = max(r["mcdm"] for r in with_data)
            c(Check(FAIL, f"briefing reports zero / no risk, but live data has "
                          f"{len(with_data)} site(s) scoring up to mcdm={worst:.0f} "
                          f"— compare_intersections is not anchoring to latest data"))
        elif with_data:
            top = max(with_data, key=lambda r: max(r["blended"], r["mcdm"]))
            if _site_mentioned(top["name"], low):
                c(Check(PASS, f"names the live top-risk site ({top['name']})"))
            else:
                c(Check(WARN, f"briefing does not clearly name the live "
                              f"top-risk site ({top['name']})"))
    if uc.uid == "UC2":
        criteria = ("speed variance", "vru", "incident", "vehicle volume", "vehicle count")
        if any(k in low for k in criteria):
            c(Check(PASS, "names a driving criterion"))
        else:
            c(Check(WARN, "no driving criterion named — UC2 needs a causal factor"))
    if uc.uid == "UC4":
        directions = ("improv", "worsen", "stable", "increas", "decreas", "safer", "trend")
        if any(k in low for k in directions):
            c(Check(PASS, "states a trend direction"))
        else:
            c(Check(WARN, "no trend direction stated — UC4 needs improving/worsening/stable"))
    if uc.uid == "UC3":
        c(Check(WARN, "MANUAL: confirm the recommended crossing is the lower-scored "
                      "one in the ground-truth table printed above"))

    # --- Latency -------------------------------------------------------------
    if res.latency_s is not None:
        if res.latency_s <= uc.latency_budget:
            c(Check(PASS, f"latency {res.latency_s:.1f}s (budget {uc.latency_budget:.0f}s)"))
        else:
            c(Check(WARN, f"latency {res.latency_s:.1f}s exceeds {uc.latency_budget:.0f}s "
                          f"budget (cold start? agentic chaining?)"))


# ── Reporting ─────────────────────────────────────────────────────────────────


def print_uc(res: UCResult) -> None:
    uc = res.uc
    print()
    print("=" * 78)
    print(f"{uc.uid}: {uc.name}   [{uc.user_role}]")
    print("=" * 78)
    print(f"  query : {uc.query}")
    print(f"  tools : {', '.join(uc.expect_tools)}  (paper-stated; not API-visible)")
    if res.latency_s is not None:
        print(f"  time  : {res.latency_s:.2f}s    http: {res.status_code}")
    print()
    if res.reply:
        snippet = res.reply.strip()
        if len(snippet) > 600:
            snippet = snippet[:600] + " […]"
        print("  --- reply " + "-" * 64)
        for line in snippet.splitlines():
            print(f"  | {line}")
        print("  " + "-" * 74)
        print()
    for chk in res.checks:
        print(f"  [{_MARK[chk.level]}] {chk.message}")
    print(f"\n  => {uc.uid} verdict: {res.worst}")


def main() -> int:
    ap = argparse.ArgumentParser(description="VTTSI-Chat demo verification harness")
    ap.add_argument("--base", default=DEFAULT_BASE, help="backend base URL")
    ap.add_argument("--json", metavar="FILE", help="also write a raw JSON report")
    ap.add_argument("--only", metavar="UC", help="run a single use case, e.g. UC2")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    print("VTTSI-Chat Demo Verification")
    print(f"target: {base}\n")

    print("[1] Health check")
    if not check_health(base):
        print("\nFAIL: deployment is not reachable. Aborting.")
        return 2

    print("\n[2] Tool inventory")
    tools = get_tools(base)
    print(f"  tools exposed ({len(tools)}): {', '.join(tools) or '(none)'}")
    if tools and len(tools) != 6:
        print(f"  WARN: paper describes 6 tools, deployment exposes {len(tools)}")

    print("\n[3] Ground truth (live /api/v1/safety/index/)")
    ground_truth = get_ground_truth(base)
    envelope = score_envelope(ground_truth)
    if ground_truth:
        print(f"  {'blended':>8} {'mcdm':>8} {'rt_si':>8}  intersection")
        for row in sorted(ground_truth, key=lambda r: -r["blended"]):
            tag = "" if row["type"] != "No Data" else "  (no data)"
            print(f"  {row['blended']:8.2f} {row['mcdm']:8.2f} {row['rt_si']:8.2f}  "
                  f"{row['name']}{tag}")
        if envelope:
            print(f"  score envelope (sites with data): "
                  f"[{envelope[0]:.1f}, {envelope[1]:.1f}]")
    else:
        print("  (unavailable — numeric range cross-check disabled)")

    cases = USE_CASES
    if args.only:
        cases = [u for u in USE_CASES if u.uid.lower() == args.only.lower()]
        if not cases:
            print(f"\nFAIL: unknown use case {args.only!r}")
            return 2

    print("\n[4] Use cases")
    results: list[UCResult] = []
    for uc in cases:
        status, latency, reply, error = ask(base, uc.query)
        res = UCResult(uc=uc, status_code=status, latency_s=latency,
                       reply=reply, error=error)
        evaluate(res, ground_truth)
        print_uc(res)
        results.append(res)

    # --- summary -------------------------------------------------------------
    print()
    print("#" * 78)
    print("SUMMARY")
    print("#" * 78)
    n_fail = sum(1 for r in results if r.worst == FAIL)
    n_warn = sum(1 for r in results if r.worst == WARN)
    n_pass = sum(1 for r in results if r.worst == PASS)
    for r in results:
        lat = f"{r.latency_s:5.1f}s" if r.latency_s is not None else "  n/a"
        print(f"  {r.uc.uid}  {_MARK[r.worst]}  {lat}   {r.uc.name}")
    print(f"\n  {n_pass} pass / {n_warn} warn / {n_fail} fail")
    print("\n  WARN items and every UC3 routing claim still need a human eye —")
    print("  work through tests/demo/verification_checklist.md before the demo.")

    if args.json:
        report = {
            "base": base,
            "tools": tools,
            "ground_truth": ground_truth,
            "results": [
                {
                    "uc": r.uc.uid,
                    "name": r.uc.name,
                    "query": r.uc.query,
                    "status_code": r.status_code,
                    "latency_s": r.latency_s,
                    "verdict": r.worst,
                    "reply": r.reply,
                    "error": r.error,
                    "checks": [{"level": c.level, "message": c.message} for c in r.checks],
                }
                for r in results
            ],
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\n  raw report written to {args.json}")

    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
