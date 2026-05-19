# SafetyChat — one-line reviewer reproductions

Each use case from Table 2 of the paper, reduced to a single `curl` against
the live deployment. Paste any line into a shell and the response body
returns the SafetyChat assistant reply. Add `| jq -r '.reply'` for the
human-readable answer; the full JSON also includes the `model` field for
reproducibility (currently pinned to `gpt-4o-2024-11-20`).

```text
BASE=https://cs6604-trafficsafety-180117512369.europe-west1.run.app
```

> **Latency note.** Cold start is ≈ 10–15 s; warm responses settle to
> ≈ 5–7 s. The agentic loop chains up to six tool calls.

## UC1 — TMC Operator Morning Briefing

```bash
curl -sS -X POST "$BASE/api/v1/chat/" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Give me a morning safety briefing for all intersections."}]}' | jq -r '.reply'
```

## UC2 — Causal Safety Explanation for Planners

```bash
curl -sS -X POST "$BASE/api/v1/chat/" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Why did E. Broad & N. Washington score above 70 yesterday at 5 PM? Explain which criteria drove the elevated score."}]}' | jq -r '.reply'
```

## UC3 — Emergency Responder Routing

```bash
curl -sS -X POST "$BASE/api/v1/chat/" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Which of Glebe & Potomac or Birch & W. Broad has lower current risk? Recommend the safer crossing for emergency vehicle routing."}]}' | jq -r '.reply'
```

## UC4 — Public Stakeholder Trend Engagement

```bash
curl -sS -X POST "$BASE/api/v1/chat/" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Is the Glebe & Potomac intersection getting safer over time?"}]}' | jq -r '.reply'
```

## Inspecting the tool schema

The agent's six callable tools are introspectable without burning a chat
call — no OpenAI usage, no key required:

```bash
curl -sS "$BASE/api/v1/chat/tools" | jq '.tools[].function.name'
```

## Health and ground truth

```bash
curl -sS "$BASE/health" | jq
curl -sS "$BASE/api/v1/safety/index/" | jq '.[] | {name: .intersection_name, blended: .safety_index, mcdm: .mcdm_index, type: .index_type}'
```

The `/api/v1/safety/index/` endpoint is what the SafetyChat answers should
agree with up to its time-anchor / α-blend snapshot; the
`tests/demo/validate_groundedness.py` script automates that comparison.
