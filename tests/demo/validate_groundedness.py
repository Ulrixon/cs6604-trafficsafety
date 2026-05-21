#!/usr/bin/env python3
"""
SafetyChat groundedness validation
==================================
Runs a fixed battery of questions through SafetyChat and checks each numeric
claim against the live /api/v1/safety/index ground truth. Emits both a raw
JSON record and a paper-ready Markdown table.

This converts the paper's claim "avoids hallucination by grounding all LLM
outputs in six typed API calls" from rhetoric to measurement: each row pairs
a model answer with the ground-truth value and an automated verdict.

Usage
-----
    python tests/demo/validate_groundedness.py
    python tests/demo/validate_groundedness.py --base http://localhost:8000
    python tests/demo/validate_groundedness.py --out tests/demo/validation_table.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time

try:
    import requests
except ImportError:
    sys.exit(
        "validate_groundedness.py needs the 'requests' package.\n"
        "Run it inside the project environment, or: pip install requests"
    )

DEFAULT_BASE = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app"
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# A score tolerance: SafetyChat may round, blend snapshots, or use a slightly
# different time anchor than the dashboard. ±2.0 on a 0-100 scale is the
# largest gap we'd accept as "same answer".
SCORE_TOLERANCE = 2.0

# ── Validation battery ────────────────────────────────────────────────────

# Each entry is a *checkable* question — one whose correct answer can be read
# directly from /api/v1/safety/index/. We deliberately avoid trend / historical
# questions here because their ground truth requires a second tool call, which
# would obscure the cleanliness of the comparison.

VALIDATIONS: list[dict] = [
    {
        "id": "V1",
        "question": "What is the current MCDM safety score for Birch & W. Broad?",
        "expect": "value",
        "site": "birch_st-w_broad_st",
        "field": "mcdm",
    },
    {
        "id": "V2",
        "question": "What is the current MCDM safety score for E. Broad & N. Washington?",
        "expect": "value",
        "site": "e_broad_st-n_washington_st",
        "field": "mcdm",
    },
    {
        "id": "V3",
        "question": "What is the current MCDM safety score for Glebe & Potomac?",
        "expect": "value",
        "site": "glebe-potomac",
        "field": "mcdm",
    },
    {
        "id": "V4",
        "question": "Which intersection currently has the highest MCDM safety score?",
        "expect": "argmax",
        "field": "mcdm",
    },
    {
        "id": "V5",
        "question": "Is Glebe & Potomac currently higher or lower risk than Birch & W. Broad?",
        "expect": "compare",
        "site_a": "glebe-potomac",
        "site_b": "birch_st-w_broad_st",
        "field": "mcdm",
    },
    {
        "id": "V6",
        "question": "Are there any intersections currently scoring above 70 on the MCDM index?",
        "expect": "threshold_above",
        "field": "mcdm",
        "threshold": 70,
    },
    {
        "id": "V7",
        "question": "How many monitored intersections currently have live telemetry data?",
        "expect": "count_with_data",
    },
    {
        "id": "V8",
        "question": "What is the current blended safety index for Birch & W. Broad at alpha=0.7?",
        "expect": "value",
        "site": "birch_st-w_broad_st",
        "field": "blended",
    },
]


# ── HTTP helpers ──────────────────────────────────────────────────────────


def _call_with_deadline(fn, deadline_s: float):
    """
    Run ``fn()`` under a hard wall-clock deadline. ``requests``' own ``timeout``
    is per-socket-operation, not total — a server holding the connection open
    can wedge a call far past it. The worker is a daemon thread, so a hung
    call leaks one thread but never blocks script exit.

    Raises TimeoutError if ``fn`` does not return within ``deadline_s``.
    """
    box: dict = {}

    def runner() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - re-raised on the caller thread
            box["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(deadline_s)
    if t.is_alive():
        raise TimeoutError(f"call exceeded {deadline_s:.0f}s hard deadline")
    if "error" in box:
        raise box["error"]
    return box["value"]


def fetch_gt(base: str, gt_file: str | None = None) -> list[dict]:
    """
    Normalised ground-truth rows. Loads from a local JSON file if ``gt_file`` is
    provided (avoids the slow /api/v1/safety/index/ endpoint when the local DB
    is recomputing); otherwise calls the live endpoint.
    """
    if gt_file:
        with open(gt_file, encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        r = _call_with_deadline(
            lambda: requests.get(f"{base}/api/v1/safety/index/", timeout=120), 150
        )
        r.raise_for_status()
        payload = r.json()
    rows = payload if isinstance(payload, list) else payload.get("intersections", [])
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or "intersection_name" not in row:
            continue
        out.append({
            "name": str(row["intersection_name"]),
            "blended": float(row.get("safety_index", 0.0) or 0.0),
            "mcdm": float(row.get("mcdm_index", 0.0) or 0.0),
            "rt_si": float(row.get("rt_si_index", 0.0) or 0.0),
            "type": str(row.get("index_type", "")),
        })
    return out


def ask(base: str, q: str) -> tuple[str, float, int | None, str]:
    started = time.perf_counter()
    try:
        r = _call_with_deadline(
            lambda: requests.post(
                f"{base}/api/v1/chat/",
                json={"messages": [{"role": "user", "content": q}]},
                timeout=300,
            ),
            330,
        )
    except (requests.RequestException, TimeoutError) as exc:
        return "", time.perf_counter() - started, None, str(exc)
    latency = time.perf_counter() - started
    if not r.ok:
        try:
            detail = r.json().get("detail", "")
        except ValueError:
            detail = r.text[:200]
        return "", latency, r.status_code, detail
    return r.json().get("reply", ""), latency, r.status_code, ""


# ── Per-validation evaluation ────────────────────────────────────────────


def _extract_numbers(text: str) -> list[float]:
    return [float(n) for n in NUMBER_RE.findall(text)]


def _site_mentioned(gt_name: str, low: str) -> bool:
    suffixes = {"st", "rd", "ave", "blvd", "dr", "ln", "ct", "pl", "way", "hwy"}
    tokens = {t for t in re.split(r"[^a-z0-9]+", gt_name.lower()) if t}
    sig = {t for t in tokens - suffixes if len(t) > 1}
    norm = re.sub(r"[^a-z0-9]", "", low)
    return bool(sig) and all(t in norm for t in sig)


def evaluate(v: dict, reply: str, gt: list[dict]) -> dict:
    """Return {verdict, expected, detail} for one validation against a reply."""
    low = reply.lower()
    by_name = {r["name"]: r for r in gt}

    if v["expect"] == "value":
        row = by_name.get(v["site"])
        if not row:
            return {"verdict": "ERROR",
                    "expected": f"site {v['site']!r} not in ground truth",
                    "detail": ""}
        gt_value = row[v["field"]]
        expected = f"{v['field']}={gt_value:.2f} ({v['site']})"
        nums = _extract_numbers(reply)
        if not nums:
            return {"verdict": "FAIL", "expected": expected,
                    "detail": "no numeric value in reply"}
        best = min(nums, key=lambda n: abs(n - gt_value))
        if abs(best - gt_value) <= SCORE_TOLERANCE:
            return {"verdict": "MATCH", "expected": expected,
                    "detail": f"closest claim {best} within ±{SCORE_TOLERANCE} of {gt_value:.2f}"}
        return {"verdict": "MISMATCH", "expected": expected,
                "detail": f"closest claim {best}; ground truth {gt_value:.2f}"}

    if v["expect"] == "argmax":
        with_data = [r for r in gt if r["type"] != "No Data"]
        if not with_data:
            return {"verdict": "ERROR", "expected": "no sites with data",
                    "detail": ""}
        top = max(with_data, key=lambda r: r[v["field"]])
        expected = f"top {v['field']}: {top['name']} ({top[v['field']]:.2f})"
        # Naming the top site is not enough — the reply must positively
        # *attribute* the maximum to it. Without a superlative cue the answer
        # could be an alphabetical listing (the symptom of the UC1 all-zero
        # bug, where compare_intersections returns equal zeros for everyone).
        superlatives = ("highest", "top", "most", "maximum", "leading",
                        "greatest", "ranked")
        mentions_top = _site_mentioned(top["name"], low)
        has_superlative = any(s in low for s in superlatives)
        if mentions_top and has_superlative:
            return {"verdict": "MATCH", "expected": expected,
                    "detail": f"reply names {top['name']} with a superlative"}
        if mentions_top:
            return {"verdict": "MANUAL", "expected": expected,
                    "detail": "names the top site but does not call it highest"}
        return {"verdict": "MISMATCH", "expected": expected,
                "detail": f"reply did not clearly name {top['name']}"}

    if v["expect"] == "compare":
        a, b = by_name.get(v["site_a"]), by_name.get(v["site_b"])
        if not a or not b:
            return {"verdict": "ERROR", "expected": "site missing", "detail": ""}
        higher = v["site_a"] if a[v["field"]] > b[v["field"]] else v["site_b"]
        lower = v["site_b"] if higher == v["site_a"] else v["site_a"]
        expected = (f"{lower} ({by_name[lower][v['field']]:.2f}) lower than "
                    f"{higher} ({by_name[higher][v['field']]:.2f}) on {v['field']}")
        if not (_site_mentioned(lower, low) and _site_mentioned(higher, low)):
            return {"verdict": "MISMATCH", "expected": expected,
                    "detail": "did not name both sites"}
        if any(k in low for k in ("lower risk", "safer", "less risk")):
            return {"verdict": "MATCH", "expected": expected,
                    "detail": "names both sites + a comparative term"}
        return {"verdict": "MANUAL", "expected": expected,
                "detail": "names both sites; comparative verdict unclear from text"}

    if v["expect"] == "threshold_above":
        with_data = [r for r in gt if r["type"] != "No Data"]
        matching = [r for r in with_data if r[v["field"]] > v["threshold"]]
        expected = f"{len(matching)} site(s) with {v['field']} > {v['threshold']}"
        if not matching:
            says_none = any(k in low for k in (
                "no intersections", "none ", "no sites", "currently no",
                "there are no", "no current", "no current high",
            ))
            return {"verdict": "MATCH" if says_none else "MANUAL",
                    "expected": expected,
                    "detail": "GT has none above threshold; reply says none"
                              if says_none else
                              "GT has none above; reply unclear"}
        if any(_site_mentioned(r["name"], low) for r in matching):
            return {"verdict": "MATCH", "expected": expected,
                    "detail": "names a qualifying site"}
        return {"verdict": "MISMATCH", "expected": expected,
                "detail": "GT has qualifying sites; reply names none"}

    if v["expect"] == "count_with_data":
        n = sum(1 for r in gt if r["type"] != "No Data")
        expected = f"{n} intersection(s) with live data (of {len(gt)} monitored)"
        nums = _extract_numbers(reply)
        if any(abs(num - n) < 0.5 for num in nums):
            return {"verdict": "MATCH", "expected": expected,
                    "detail": f"reply mentions {n}"}
        return {"verdict": "MISMATCH", "expected": expected,
                "detail": f"GT count {n}; reply numbers: {nums}"}

    return {"verdict": "ERROR",
            "expected": f"unknown expect type {v['expect']!r}", "detail": ""}


# ── Output ────────────────────────────────────────────────────────────────


def write_table(path: str, base: str, gt: list[dict], results: list[dict]) -> None:
    n_match = sum(1 for r in results if r["verdict"] == "MATCH")
    n_mis = sum(1 for r in results if r["verdict"] == "MISMATCH")
    n_man = sum(1 for r in results if r["verdict"] == "MANUAL")
    n_fail = sum(1 for r in results if r["verdict"] in ("FAIL", "ERROR"))

    sites_with_data = sum(1 for r in gt if r["type"] != "No Data")

    md = [
        "# SafetyChat groundedness validation",
        "",
        f"Generated against `{base}`. Ground truth: {sites_with_data} sites "
        f"with live telemetry (of {len(gt)} monitored).",
        "",
        "Each row asks SafetyChat a question whose correct answer can be read ",
        "directly from `/api/v1/safety/index/`. *Verdict* is automated: ",
        "**MATCH** = the answer's number / identified site agrees with ground ",
        f"truth within ±{SCORE_TOLERANCE} (for 0-100 scores); **MISMATCH** = a ",
        "concrete disagreement; **MANUAL** = answer requires a human judgment; ",
        "**FAIL** = no usable answer.",
        "",
        f"**Summary:** {n_match} match / {n_mis} mismatch / {n_man} manual / "
        f"{n_fail} fail (of {len(results)}).",
        "",
        "| ID | Question | Ground truth | SafetyChat answer (excerpt) | Latency | Verdict |",
        "|---|---|---|---|---:|:---:|",
    ]
    for r in results:
        q = r["question"].replace("|", "\\|")
        gt_desc = r["expected"].replace("|", "\\|")
        snippet = (r["reply"] or "").strip().replace("\n", " ").replace("|", "\\|")
        if len(snippet) > 180:
            snippet = snippet[:180] + " …"
        if not snippet:
            snippet = f"*(HTTP {r['status']}: {r['error']})*"
        lat = f"{r['latency_s']:.1f}s"
        md.append(f"| {r['id']} | {q} | {gt_desc} | {snippet} | {lat} | **{r['verdict']}** |")

    md += [
        "",
        f"> Score tolerance ±{SCORE_TOLERANCE}. \"MANUAL\" verdicts need human ",
        "> review of the reply against the ground-truth column. Full replies ",
        "> and ground-truth rows are in `validation_results.json`.",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=DEFAULT_BASE, help="backend base URL")
    ap.add_argument("--out", default="tests/demo/validation_table.md",
                    help="Markdown output path")
    ap.add_argument("--json", default="tests/demo/validation_results.json",
                    help="raw JSON output path")
    ap.add_argument("--gt-file", default=None,
                    help="Load ground truth from a local JSON file instead of "
                         "calling /api/v1/safety/index/ (use when the endpoint "
                         "is slow / unavailable)")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    if args.gt_file:
        print(f"Loading ground truth from {args.gt_file} ...")
    else:
        print(f"Fetching ground truth from {base}/api/v1/safety/index/ ...")
    gt = fetch_gt(base, args.gt_file)
    if not gt:
        print("FAIL: empty ground truth — cannot validate")
        return 2
    with_data = sum(1 for r in gt if r["type"] != "No Data")
    print(f"  {len(gt)} sites total, {with_data} with live data")

    results: list[dict] = []
    for v in VALIDATIONS:
        print(f"\n[{v['id']}] {v['question']}")
        reply, latency, status, error = ask(base, v["question"])
        evaluation = evaluate(v, reply, gt)
        results.append({
            **v,
            "reply": reply,
            "latency_s": round(latency, 2),
            "status": status,
            "error": error,
            **evaluation,
        })
        print(f"  -> {evaluation['verdict']:8s}  {evaluation['detail']}  [{latency:.1f}s]")

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump({"base": base, "ground_truth": gt, "results": results},
                  fh, indent=2, default=str)
    write_table(args.out, base, gt, results)

    n_match = sum(1 for r in results if r["verdict"] == "MATCH")
    n_mis = sum(1 for r in results if r["verdict"] == "MISMATCH")
    n_man = sum(1 for r in results if r["verdict"] == "MANUAL")
    n_fail = sum(1 for r in results if r["verdict"] in ("FAIL", "ERROR"))

    print()
    print("=" * 60)
    print(f"  {n_match} match / {n_mis} mismatch / {n_man} manual / {n_fail} fail")
    print(f"  Wrote {args.out}")
    print(f"  Wrote {args.json}")
    return 0 if (n_fail == 0 and n_mis == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
