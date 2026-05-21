#!/usr/bin/env python3
"""
UC latency benchmark for SafetyChat
===================================
Replaces the paper's "under five seconds" claim with measured percentiles
(cold start, warm p50, warm p95) per use case. Not run automatically because
each invocation burns OpenAI quota — operator runs this once before
camera-ready, after confirming billing has headroom.

Usage
-----
    python tests/demo/benchmark_ucs.py              # default N=5 runs per UC
    python tests/demo/benchmark_ucs.py --n 10
    python tests/demo/benchmark_ucs.py --base http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

try:
    import requests
except ImportError:
    sys.exit(
        "benchmark_ucs.py needs the 'requests' package.\n"
        "Run it inside the project environment, or: pip install requests"
    )

DEFAULT_BASE = "https://cs6604-trafficsafety-180117512369.europe-west1.run.app"

# Same four queries used in verify_demo.py / the demo paper Table 2.
QUERIES: list[tuple[str, str]] = [
    ("UC1", "Give me a morning safety briefing for all intersections."),
    ("UC2",
     "Why did E. Broad & N. Washington score above 70 yesterday at 5 PM? "
     "Explain which criteria drove the elevated score."),
    ("UC3",
     "Which of Glebe & Potomac or Birch & W. Broad has lower current risk? "
     "Recommend the safer crossing for emergency vehicle routing."),
    ("UC4", "Is the Glebe & Potomac intersection getting safer over time?"),
]


def _ask(base: str, q: str) -> tuple[float, int | None, str]:
    started = time.perf_counter()
    try:
        r = requests.post(
            f"{base}/api/v1/chat/",
            json={"messages": [{"role": "user", "content": q}]},
            timeout=300,
        )
    except requests.RequestException as exc:
        return time.perf_counter() - started, None, str(exc)
    latency = time.perf_counter() - started
    if r.ok:
        return latency, r.status_code, ""
    try:
        detail = r.json().get("detail", "")
    except ValueError:
        detail = r.text[:200]
    return latency, r.status_code, detail


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    # nearest-rank p95
    i = max(0, int(round(0.95 * (len(s) - 1))))
    return s[i]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=DEFAULT_BASE, help="backend base URL")
    ap.add_argument("--n", type=int, default=5,
                    help="number of runs per UC (default 5)")
    ap.add_argument("--out", default="tests/demo/latency_table.md",
                    help="Markdown output path")
    ap.add_argument("--json", default="tests/demo/latency_results.json",
                    help="raw JSON output path")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    print(f"Benchmark — N={args.n} runs per UC against {base}")
    print("(each run is one OpenAI-billable chat call)\n")

    results: list[dict] = []
    for uid, q in QUERIES:
        print(f"[{uid}] ", end="", flush=True)
        timings: list[float] = []
        statuses: list[int | None] = []
        errors: list[str] = []
        for _ in range(args.n):
            lat, status, err = _ask(base, q)
            timings.append(lat)
            statuses.append(status)
            errors.append(err)
            tag = "" if status == 200 else f"({status})"
            print(f"{lat:.1f}s{tag} ", end="", flush=True)
        print()

        cold = timings[0]
        warm = timings[1:]
        ok = [t for t, s in zip(timings, statuses) if s == 200]
        results.append({
            "uc": uid,
            "query": q,
            "n": args.n,
            "timings_s": [round(t, 2) for t in timings],
            "statuses": statuses,
            "errors": [e for e in errors if e],
            "cold_s": round(cold, 2),
            "warm_p50_s": round(statistics.median(warm), 2) if warm else None,
            "warm_p95_s": round(_p95(warm), 2) if warm else None,
            "min_s": round(min(timings), 2),
            "max_s": round(max(timings), 2),
            "ok_count": len(ok),
        })

    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump({"base": base, "n": args.n, "results": results},
                  fh, indent=2, default=str)

    md = [
        "# SafetyChat UC latency",
        "",
        f"Measured against `{base}` with N={args.n} runs per UC. ",
        f"\"Cold\" = first call after deployment quiescence; warm "
        f"percentiles exclude that call.",
        "",
        "| UC | Cold | Warm p50 | Warm p95 | Min / Max | OK / N |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        p50 = f"{r['warm_p50_s']}s" if r['warm_p50_s'] is not None else "n/a"
        p95 = f"{r['warm_p95_s']}s" if r['warm_p95_s'] is not None else "n/a"
        md.append(
            f"| {r['uc']} | {r['cold_s']}s | {p50} | {p95} | "
            f"{r['min_s']} / {r['max_s']}s | {r['ok_count']}/{r['n']} |"
        )
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    print(f"\nWrote {args.out}")
    print(f"Wrote {args.json}")
    any_nonok = any(r["ok_count"] < r["n"] for r in results)
    return 1 if any_nonok else 0


if __name__ == "__main__":
    sys.exit(main())
