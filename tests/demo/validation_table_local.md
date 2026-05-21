# SafetyChat groundedness validation

Generated against `http://localhost:8001`. Ground truth: 3 sites with live telemetry (of 18 monitored).

Each row asks SafetyChat a question whose correct answer can be read 
directly from `/api/v1/safety/index/`. *Verdict* is automated: 
**MATCH** = the answer's number / identified site agrees with ground 
truth within ±2.0 (for 0-100 scores); **MISMATCH** = a 
concrete disagreement; **MANUAL** = answer requires a human judgment; 
**FAIL** = no usable answer.

**Summary:** 5 match / 3 mismatch / 0 manual / 0 fail (of 8).

| ID | Question | Ground truth | SafetyChat answer (excerpt) | Latency | Verdict |
|---|---|---|---|---:|:---:|
| V1 | What is the current MCDM safety score for Birch & W. Broad? | mcdm=51.82 (birch_st-w_broad_st) | The current MCDM safety score for the Birch & W. Broad intersection is 44.95, placing it in the "moderate risk" range. | 16.8s | **MISMATCH** |
| V2 | What is the current MCDM safety score for E. Broad & N. Washington? | mcdm=52.62 (e_broad_st-n_washington_st) | The current MCDM safety score for the E. Broad & N. Washington intersection is **61.17**, which falls into the **moderate risk** category. | 10.7s | **MISMATCH** |
| V3 | What is the current MCDM safety score for Glebe & Potomac? | mcdm=0.66 (glebe-potomac) | The current MCDM safety score for the Glebe & Potomac intersection is 0.0, indicating a low-risk level. | 9.4s | **MATCH** |
| V4 | Which intersection currently has the highest MCDM safety score? | top mcdm: e_broad_st-n_washington_st (52.62) | The intersection with the highest current MCDM safety score is "E Broad St & N Washington St," which has a score of 61.17, indicating moderate risk. | 38.4s | **MATCH** |
| V5 | Is Glebe & Potomac currently higher or lower risk than Birch & W. Broad? | glebe-potomac (0.66) lower than birch_st-w_broad_st (51.82) on mcdm | Currently, the Glebe & Potomac intersection has a lower risk with a blended safety score of 1.35 (low risk) compared to Birch & W. Broad, which has a blended safety score of 14.99  … | 17.2s | **MATCH** |
| V6 | Are there any intersections currently scoring above 70 on the MCDM index? | 0 site(s) with mcdm > 70 | No intersections are currently scoring above 70 on the MCDM safety index. The highest score is 61.17 at the "E Broad St - N Washington St" intersection, which falls within the mode … | 37.9s | **MATCH** |
| V7 | How many monitored intersections currently have live telemetry data? | 3 intersection(s) with live data (of 18 monitored) | Currently, there are no monitored intersections with live telemetry data. This may indicate a system-wide outage or temporary lack of real-time updates. It is advisable to check fo … | 5.6s | **MISMATCH** |
| V8 | What is the current blended safety index for Birch & W. Broad at alpha=0.7? | blended=15.55 (birch_st-w_broad_st) | The current blended safety index for Birch & W. Broad with alpha=0.7 is **14.99** (low risk). The contributing factors include a speed uplift of 0.661, variance uplift of 0.1, and  … | 9.8s | **MATCH** |

> Score tolerance ±2.0. "MANUAL" verdicts need human 
> review of the reply against the ground-truth column. Full replies 
> and ground-truth rows are in `validation_results.json`.