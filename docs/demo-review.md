# Pre-submission self-review: VTTSI-Chat demo (SIGSPATIAL '26)

> **Status: Internal working document — do not publish.**
> This is a simulated reviewer-style critique intended for the authors' own
> revision planning. It is *not* linked from `index.html` and should not be
> committed onto a publicly-served path. The candid "Weak Reject" framing is
> appropriate as an internal stress-test, not as a public statement before
> the paper has been peer-reviewed.

---

## Metadata

| Field | Value |
|---|---|
| Paper | "VTTSI-Chat: Agentic GeoAI for Real-Time Intersection Safety Monitoring with Natural Language Explanation [Demo]" |
| Authors | Cheng-Shun Chuang, Jason Cusati (Virginia Tech) |
| Venue | SIGSPATIAL '26 (Riverside, CA, Nov 3–6, 2026) — Demo track |
| Paper file | `files/acmart-primary/vttsi-chat-demo.pdf` (4 pages) |
| Live deployment exercised | `https://cs6604-trafficsafety-180117512369.europe-west1.run.app` |
| Verification harness | `tests/demo/verify_demo.py` + `tests/demo/verification_checklist.md` |
| Branch with proposed fixes | `fix/compare-intersections-time-anchor` |
| Review date | 2026-05-19 |
| Reviewer | Self-review via Claude (Opus 4.7), grounded in: paper read + source read + live deployment exercised |

---

## Review

**Recommendation: Weak Reject as submitted, with a clear path to Accept on revision.**

The contribution is real and the demo is live — that is already more than half
of demo-track papers deliver. But the paper makes several quantitative claims
that the deployment does not currently support, and the flagship use case has
a reproducible bug. These are fixable before camera-ready; without fixes, a
careful reviewer will catch them.

### Summary

The authors layer **SafetyChat**, a tool-augmented GPT-4o module, on top of
an existing hybrid safety index (RT-SI Empirical-Bayes-stabilized crash rate
+ CRITIC-weighted MCDM scoring) covering 18 instrumented intersections in
Falls Church, VA. Six typed function-call tools (`get_safety_score`,
`get_component_breakdown`, `get_historical_baseline`, `compare_intersections`,
`get_trend_data`, `run_sql_query`) ground every numerical claim in
PostGIS-backed live data. Four use cases (briefing / causal / routing /
trend) anchor the demo session. A live cloud deployment is provided.

### Strengths

1. **Live, accessible demo.** A working `run.app` URL, four end-to-end use
   cases, and a documented schema for the six tools. Demonstrability is
   genuine.
2. **Sound architectural choice.** Tool-augmented function calling against
   PostGIS is the right pattern for grounded spatial QA — bounded SELECT-only
   SQL with `LIMIT` cap, fuzzy intersection name resolution, and anchoring
   "now" to the latest data timestamp (in most tools) all reflect mature
   engineering.
3. **The "what vs why" framing** (§3) is the cleanest articulation of the
   contribution. Existing dashboards present numbers; SafetyChat produces
   causal narratives traced back to component criteria. That framing is
   defensible and the related-work positioning (Table 1) supports it.
4. **System prompt embeds the formula reference** (~125 lines covering RT-SI
   Eqs. 1–16 and MCDM Eqs. 17–42). This is a real, often-overlooked
   discipline — the model can correctly cite Eq. 3 EB stabilization or
   Eq. 17 CRITIC weighting when asked, instead of confabulating.
5. **Reasonable formula validation** (§2.2): pairwise correlation
   *r ≈ 0.78–0.99* across the three MCDM methods and RT-SI MAD ≈ 0.09 under
   ±25% perturbation justifies the underlying index.

### Substantive concerns

#### W1. The flagship use case (UC1) has a reproducible bug

`compare_intersections` calls
`mcdm_svc.calculate_safety_score_for_time(intersection, datetime.now())` —
the server wall clock — while every sibling tool anchors to
`MAX(publish_timestamp)`. When the server clock drifts past the latest
15-minute data bin, UC1 returns *all zeros* and the briefing reads:

> *"All top 5 intersections currently show a blended safety score of 0...
> No further action or specific concerns at this time."*

This is reproducible on the live deployment. It is **intermittent**, which
is arguably worse — the briefing is unpredictably wrong rather than
consistently wrong. This is the very use case the paper opens with (§4.2).

*Fix proposed on branch `fix/compare-intersections-time-anchor`: anchor to
`MAX(publish_timestamp)` like the sibling tools; ≈ 4 LOC of behavior change,
9 chat-service tests pass, 124 backend+plugin tests pass.*

#### W2. Several quantitative claims are unsupported or contradicted by the deployment

- **"Under five seconds"** (UC1, §4.2). Observed latency on the live
  deployment: 12.5 s cold, 5–7 s warm. The agentic loop chains up to 6
  iterations; under multi-tool UC1 the budget is not met.
- **"Avoids hallucination" / "grounding all LLM outputs in six typed API
  calls"** (§6, Abstract). The paper offers no quantitative groundedness
  measurement — no audit of tool-call traces vs claimed numbers, no
  precision metric for numeric answers, no user study. The claim is
  plausible architecturally but unsubstantiated.
- **"18 instrumented intersections"** (Abstract, §2). The live
  `/api/v1/safety/index/` endpoint returns 18 records, but **only 3** have
  `index_type: "Blended"` (real data); **15 are `"No Data"`**. The paper
  does not distinguish.
- **"Hybrid"** index. In the deployed system `rt_si_index = 0.0` for every
  monitored intersection. The blended index reduces to `0.3 × MCDM` in
  practice. The hybrid claim is structurally hollow at demo time, even
  though the formulae are correct.

#### W3. The paper does not demonstrate correctness of the LLM answers

Beyond W2's groundedness claim, there is no evidence that SafetyChat answers
are accurate against the dashboard. Spot-checks of the four UCs reveal:

- **UC2** accepts a false premise ("above 70") and explains an MCDM of 69.27
  as "elevated" without correcting the user.
- **UC3** routing recommendation is *ranking-correct* against ground truth
  (Glebe < Birch), but the numbers reported (Glebe 1.35, Birch 14.99) differ
  from the index endpoint (0.20, 15.55) — suggesting a different
  time-anchor or alpha snapshot than the dashboard uses. A reviewer asking
  "which is right?" gets no answer.
- **UC4** reports a 30-day average MCDM of 39.89 for Glebe & Potomac, where
  the current MCDM is 0.66. Plausible if the score truly declined, but
  unverified.

A simple table comparing 5–10 LLM answers to dashboard ground truth would
substantially strengthen the paper.

#### W4. "Agentic GeoAI" is overclaimed terminology

The paper invokes "agentic GeoAI" but the agentic behavior is a standard
OpenAI tool-calling loop with a hard cap of 6 iterations. "Geo" reduces to
PostGIS-backed tools — there is no spatial reasoning *in the LLM*
(e.g., topological inference, spatial joins reasoned about by the model).
The system is a *spatial-data QA agent*, which is good; the "GeoAI" framing
oversells it. Tempering the framing (or actually demonstrating LLM-driven
spatial reasoning, e.g., "which intersections lie within 500m of a school
zone and have elevated VRU exposure?") would help.

### Specific issues / questions for the authors

- **§2 / DB schema**: the paper references `vdot_crashes_with_intersections`
  (plural) but the `get_historical_baseline` tool queries
  `public.vdot_crash_with_intersections` (singular). Which is correct? Live
  deployment behavior would tell.
- **§4.2**: "in under five seconds" — measured under what conditions? Cold
  start? Specify.
- **Figure 1**: the orange pathway lists *four* tools but §3 lists *six*.
  The figure is stale relative to the prose. (The two missing —
  `get_trend_data` and `run_sql_query` — are also the most interesting ones
  for a GIS audience; surface them in Fig. 1.)
- **§3**: "agentic loop (up to six iterations)" — what happens on the 7th?
  The code returns whatever's in the last message, which can be the last
  tool result. Briefly clarify graceful degradation.
- **§4.4 UC3**: routing recommendations from an LLM are safety-critical.
  What guardrails exist if the model recommends the *higher*-risk crossing?
  (Currently none — a wrong recommendation just propagates.)
- **Related work**: the LLM-for-spatial-QA literature has moved fast —
  SpatialNLI / GeoQA / LLM-as-spatial-reasoner work is worth situating
  against.

### Reproducibility / demonstrability

The live deployment is the demo's strongest asset. To strengthen
reproducibility for a conference audience:

- Pin the OpenAI model version (`gpt-4o` is a moving target).
- Document a 1-line repro for each UC.
- The `/api/v1/chat/tools` endpoint surfaces the tool schema — excellent.
  Mention this in the paper.
- The deployment's `/health` returns `database: not_configured` despite
  data flowing — confusing for an attendee who pokes at the API.

### Path to acceptance

This paper is one revision cycle from being a solid demo:

1. **Fix UC1.** Anchor `compare_intersections` to latest data.
   *(Already prepared on `fix/compare-intersections-time-anchor`.)*
2. **Add a small validation table.** 5–10 questions × {LLM answer,
   dashboard ground truth, match?}. This converts the groundedness claim
   from rhetoric to evidence.
3. **Temper the "18 intersections" / "hybrid" claims.** State the
   data-coverage reality; acknowledge RT-SI = 0 in the current deployment
   and discuss when/how it will be nonzero.
4. **Measure latency under disclosed conditions.** Replace "under five
   seconds" with a percentile table (p50/p95 per UC, warm vs. cold).
5. **Sharpen the GeoAI claim** — either soften it or add one use case that
   actually exercises spatial reasoning (proximity, containment, topology).

### Overall

**Recommendation: Weak Reject → Accept with major revision.** The system is
real, the architectural choices are sound, and the contribution is
publishable as a demo. The paper as submitted overclaims in ways a careful
reader will notice within minutes of using the live deployment. The good
news: every concern above is mechanical, not conceptual. If the authors
fix UC1, add a 10-row validation table, and temper three sentences, this
is an Accept.

**Confidence: 4/5** (read source, ran the live demo, reproduced UC1 bug).

---

## Pre-submission checklist

- [ ] **W1** — Land `fix/compare-intersections-time-anchor` and redeploy.
      Confirm UC1 returns non-zero scores via `tests/demo/verify_demo.py`.
- [ ] **W2.a** — Replace "under five seconds" with measured percentiles.
- [ ] **W2.b** — Replace "avoids hallucination" with the measurement that
      backs it (validation table; see W3).
- [ ] **W2.c** — Distinguish "18 monitored" from "3 with live data" in the
      abstract and §2.
- [ ] **W2.d** — Clarify the "hybrid" claim given current RT-SI = 0
      behaviour.
- [ ] **W3** — Add a 5–10 row LLM-answer ↔ ground-truth comparison table.
- [ ] **W4** — Either soften "agentic GeoAI" or add a spatial-reasoning
      use case.
- [ ] **Figure 1** — Update orange pathway to show six tools.
- [ ] **§2 schema** — Resolve `vdot_crash_with_intersections` vs
      `vdot_crashes_with_intersections` discrepancy.
- [ ] **Reproducibility** — Pin OpenAI model version; document 1-line UC
      repros.
