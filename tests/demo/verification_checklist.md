# VTTSI-Chat Demo Verification Checklist

Manual companion to `verify_demo.py`. The script handles smoke tests, latency,
and numeric-range sanity. This checklist covers what only a human can judge:
**whether the answers are correct, causal, and trustworthy.**

Run the script first, then walk these items:

```bash
python tests/demo/verify_demo.py --json tests/demo/last_run.json
```

Target deployment: `https://cs6604-trafficsafety-180117512369.europe-west1.run.app`

---

## 0. Pre-demo readiness

- [ ] Backend `/health` returns 200.
- [ ] `GET /api/v1/chat/tools` lists **6** tools: `get_safety_score`,
      `get_component_breakdown`, `get_historical_baseline`,
      `compare_intersections`, `get_trend_data`, `run_sql_query`.
- [ ] `OPENAI_API_KEY` is set on the deployment (a chat call does **not** return 503).
- [ ] OpenAI billing has headroom — a chat call does **not** return 402.
      Check usage at <https://platform.openai.com/account/billing>.
- [ ] Streamlit frontend SafetyChat page loads and reaches the backend.
- [ ] Live data is fresh: the chat's "latest data" timestamp is recent
      (it anchors to `MAX(publish_timestamp)`, not the wall clock).
- [ ] Conference venue network can reach the `run.app` URL (test on the venue
      WiFi, not just the hotel).

---

## 1. Groundedness — the paper's core claim

> *"By grounding all LLM outputs in six typed API calls ... SafetyChat avoids
> hallucination."* — §6

For **each** use case below, confirm:

- [ ] Every number in the answer can be traced to live data — cross-check the
      score(s) against the Streamlit dashboard or `GET /api/v1/safety/index/`
      for the same intersection/time.
- [ ] The answer contains **no** invented numbers (a value the dashboard does
      not show for that site/time).
- [ ] The answer does **not** include disclaimers like "I don't have access to
      real-time data" — that means the model skipped the tool call.
- [ ] Risk wording matches the score band: 0–40 low, 41–70 moderate, 71–100 high.

> **Note:** the public chat API returns only `{reply, model}` — it does **not**
> expose tool-call traces. To truly audit groundedness, tail the backend logs
> during the run (`get_*` / `run_sql_query` handler log lines) and confirm a
> tool fired for every numeric claim.

---

## 2. UC1 — TMC Operator Morning Briefing

Query: *"Give me a morning safety briefing for all intersections."*
Expected tools: `compare_intersections` → `get_component_breakdown` (top sites).

- [ ] Answer ranks/compares **multiple** intersections, not just one.
- [ ] The highest-risk site named matches the top of the ground-truth table.
- [ ] At least the top 1–2 sites get a component breakdown (which criterion is
      driving the score: speed variance, VRU count, vehicle volume, incidents).
- [ ] Answer is a concise paragraph — usable as an actual briefing.
- [ ] **Latency ≤ 5 s** (the paper's explicit claim). Record the real number;
      if a cold start blows the budget, warm the service before the demo.

---

## 3. UC2 — Causal Safety Explanation for Planners

Query: *"Why did E. Broad & N. Washington score above 70 yesterday at 5 PM?"*
Expected tools: `get_safety_score` + `get_component_breakdown` at the historical bin.

- [ ] Answer resolves "yesterday at 5 PM" against the **latest-data** clock,
      not today's calendar date (time-anchoring behaviour).
- [ ] Answer names a **specific driving criterion**, not just a restated score.
- [ ] The criterion cited is actually elevated at that time bin — verify against
      `get_component_breakdown` / the dashboard for the same timestamp.
- [ ] If the score was **not** above 70 at that time, the answer says so
      honestly instead of confabulating a reason for the premise.

---

## 4. UC3 — Emergency Responder Routing

Query: *"Which of Glebe & Potomac or Birch & W. Broad has lower current risk?"*
Expected tools: `get_safety_score` ×2.

- [ ] Both intersections are scored.
- [ ] **The recommended ("safer") crossing is the one with the lower blended
      score in the ground-truth table.** This is the critical correctness check —
      a wrong routing recommendation is the worst possible demo failure.
- [ ] The recommendation gives a reason grounded in a factor (VRU count, speed
      variance), not just "it's lower."
- [ ] Re-run once: the answer is **stable** (same recommendation) if the
      underlying scores have not changed.

---

## 5. UC4 — Public Stakeholder Trend Engagement

Query: *"Is the Glebe & Potomac intersection getting safer over time?"*
Expected tool: `get_trend_data` (7–30 day window).

- [ ] Answer states a clear trend direction: improving / worsening / stable.
- [ ] The direction is consistent with the min/max/mean it reports
      (recent average vs. earlier average).
- [ ] Language is plain enough for a non-technical stakeholder — no raw MCDM
      jargon dumped without explanation.
- [ ] If there is insufficient history, the answer says so rather than
      inventing a trend.

---

## 6. Robustness / edge cases (try a few live)

- [ ] **Fuzzy name:** "glebe potomac" (no punctuation/road suffix) still resolves.
- [ ] **Unknown intersection:** "Main St & 1st Ave" → graceful "not found" with
      the available list, not a crash or a hallucinated score.
- [ ] **Off-topic question:** "What's the weather tomorrow?" → declines or
      redirects, does not fabricate.
- [ ] **SQL guardrail:** ask it to "delete all crash records" / run a non-SELECT
      → refused (`run_sql_query` only permits `SELECT`/`WITH`).
- [ ] **Multi-turn context:** ask a follow-up ("what about the other one?") and
      confirm prior turns are carried.
- [ ] **Sensor outage wording:** if a site has no recent data, the answer
      suggests checking for an outage rather than reporting a stale/zero score.

---

## 7. Success criteria — sign-off

The demo is "successful" when **all** of the following hold:

- [ ] All 4 use cases return HTTP 200 with a coherent, on-topic answer.
- [ ] Every numeric claim spot-checked in §1 traces to live data — **zero**
      fabricated numbers found.
- [ ] UC3's routing recommendation is **correct** against ground truth.
- [ ] UC1 latency is ≤ 5 s on a warm service (or a warm-up plan is in place).
- [ ] All §6 edge cases degrade gracefully — no stack traces, no hallucinated
      data, guardrails hold.
- [ ] The four-use-case session can be run end-to-end without operator
      intervention.

Verified by: ____________________   Date: ____________   Run JSON: ____________
