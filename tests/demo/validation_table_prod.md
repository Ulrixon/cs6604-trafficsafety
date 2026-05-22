# SafetyChat groundedness validation

Generated against `https://cs6604-trafficsafety-180117512369.europe-west1.run.app`. Ground truth: 3 sites with live telemetry (of 18 monitored).

Each row asks SafetyChat a question whose correct answer can be read 
directly from `/api/v1/safety/index/`. *Verdict* is automated: 
**MATCH** = the answer's number / identified site agrees with ground 
truth within ±2.0 (for 0-100 scores); **MISMATCH** = a 
concrete disagreement; **MANUAL** = answer requires a human judgment; 
**FAIL** = no usable answer.

**Summary:** 4 match / 3 mismatch / 1 manual / 0 fail (of 8).

| ID | Question | Ground truth | SafetyChat answer (excerpt) | Latency | Verdict |
|---|---|---|---|---:|:---:|
| V1 | What is the current MCDM safety score for Birch & W. Broad? | mcdm=51.82 (birch_st-w_broad_st) | The current MCDM safety score for Birch & W. Broad is 44.95, indicating a moderate risk level. | 6.5s | **MISMATCH** |
| V2 | What is the current MCDM safety score for E. Broad & N. Washington? | mcdm=52.62 (e_broad_st-n_washington_st) | The current MCDM safety score for the intersection at E. Broad & N. Washington is 61.17, which indicates moderate risk. | 9.8s | **MISMATCH** |
| V3 | What is the current MCDM safety score for Glebe & Potomac? | mcdm=0.66 (glebe-potomac) | The current MCDM safety score for the intersection of Glebe Road and Potomac Avenue (Glebe & Potomac) is 0.0, which indicates no identified safety risks based on the Multi-Criteria … | 4.2s | **MATCH** |
| V4 | Which intersection currently has the highest MCDM safety score? | top mcdm: e_broad_st-n_washington_st (52.62) | The intersection with the highest current MCDM safety score is Broad St & Washington St with an MCDM score of 55.42, which falls into the moderate risk category. | 2.5s | **MATCH** |
| V5 | Is Glebe & Potomac currently higher or lower risk than Birch & W. Broad? | glebe-potomac (0.66) lower than birch_st-w_broad_st (51.82) on mcdm | Glebe Rd & Potomac Ave has a blended safety score of **1.35** (low risk), while Birch Rd & W. Broad St has a higher blended score of **14.99** (also low risk). Currently, Birch & W … | 4.6s | **MANUAL** |
| V6 | Are there any intersections currently scoring above 70 on the MCDM index? | 0 site(s) with mcdm > 70 | No, there are currently no intersections scoring above 70 on the MCDM safety index. The highest MCDM score recorded is 55.42 at the "Broad & Washington" intersection, which is stil … | 2.9s | **MATCH** |
| V7 | How many monitored intersections currently have live telemetry data? | 3 intersection(s) with live data (of 18 monitored) | *(HTTP 402: OpenAI quota exceeded. Add billing at https://platform.openai.com/account/billing)* | 7.2s | **MISMATCH** |
| V8 | What is the current blended safety index for Birch & W. Broad at alpha=0.7? | blended=15.55 (birch_st-w_broad_st) | The current blended safety index for the Birch & W. Broad intersection at alpha=0.7 is 14.99, categorized as low risk. | 6.2s | **MATCH** |

> Score tolerance ±2.0. "MANUAL" verdicts need human 
> review of the reply against the ground-truth column. Full replies 
> and ground-truth rows are in `validation_results.json`.