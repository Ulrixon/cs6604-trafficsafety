# Software Specification: VTTSI Final Report — arXiv Remediation

**Target artifact:** `files/conference_101719.tex` (Virginia Tech Transportation Safety Index, IEEEtran conference format, 21 pp.)
**Goal:** Make the final class report submission-ready for arXiv by removing factual contradictions, course-only artifacts, and cosmetic defects — without altering the underlying methodology or results.
**Ground-truth source of record:** the deployed backend in this repo (`backend/app/...`). Where the paper and code disagree, the **code wins**.

---

## 0. Resolved Ground Truth (decisions, not open questions)

| Item | Paper says | Deployed code | Decision |
|------|-----------|---------------|----------|
| EB shrinkage λ\* | §IV: `10000`; Appendix: `100000` | `rt_si_service.py:41 LAMBDA = 100000.0` | **λ\* = 100,000** (fix §IV) |
| Pooled mean r₀ | Appendix: `3.365` | `rt_si_service.py:42 R0 = 3.365` | **r₀ = 3.365** (already correct) |
| α blending | §IV + Validation: α=0.7 blend; Appendix: "no α applied" | `intersection.py:315` blends, default `alpha=0.7`, API + slider configurable | **α-blend IS shipped, default 0.7** (fix Appendix) |

---

## 1. Functional Requirements

### 1.1 Factual Consistency (Must-have)
- **FR-001:** The methodology EB optimum `\lambda^\star` MUST read `100000` (currently `10000`, line ~422), matching `LAMBDA = 100000.0` in `rt_si_service.py`. Rationale: a 10× factual contradiction with the appendix and the deployed code.
- **FR-002:** The appendix "Final Blend" subsection MUST state that α-blending **is** applied in the released code with default `α = 0.7`, configurable via the safety-index API and the Streamlit slider, and MUST reference the blended-index equation in §IV. The sentence "No blending parameter α is applied in the released code" MUST be removed. Rationale: the entire Validation section and four "final-blended" figures depend on the blend; the appendix statement contradicts both the methodology and `intersection.py:315`.

### 1.2 Cross-Reference Integrity (Must-have)
- **FR-003:** Appendix "Other intersections' results" perturbation sentence MUST reference `fig:perturbed-rt-si-comparison-birch` **and** `fig:perturbed-rt-si-comparison-broad` (currently the second ref wrongly points at `fig:all-variable-normalized-broad`).
- **FR-004:** The deviation-distribution sentence MUST reference `fig:rt-si-changes-distribution-birch` **and** `fig:rt-si-changes-distribution-broad` (currently the same label `...-broad` is referenced twice).

### 1.3 Scope / Artifact Removal (Must-have)
- **FR-005:** The entire `\section{Team Member Contribution Report}` appendix (and its `\label{appendix:contributions}`, incl. the "Appendix A" narrative) MUST be removed. Rationale: course-grading artifact written in progress-report / future tense ("is investigating", "upcoming tasks", "under active development"); inappropriate for a public preprint and inconsistent with a finished paper.

### 1.4 Claim Accuracy (Must-have)
- **FR-006:** The Results §IX sentence claiming perturbation experiments at "(±25% and ±50%)" MUST be reduced to "±25%", since only the ±25% / 50-run experiment is described and plotted (Sensitivity §VIII). Rationale: no ±50% results exist in the paper.

### 1.5 Cosmetic / Hygiene (Should-have)
- **FR-007:** The three stray literal `---` lines (≈ lines 458, 707, 721) MUST be deleted; they render as floating em-dashes between subsections.
- **FR-008:** `\nocite{*}` (≈ line 1208) MUST be removed so the bibliography lists only works actually cited in text. Rationale: `\nocite{*}` pads the reference list with ~20 uncited entries.
- **FR-009:** The one-line Acknowledgment ("This research paper used AI for assistance in generating content.") SHOULD be expanded to a complete generative-AI-use disclosure (tools named; authors take responsibility; review/verification stated) and the VTTI collaboration acknowledged.

### 1.6 Submission Metadata (Should-have, non-rendering)
- **FR-010:** Record the arXiv classification as a comment in the `.tex` preamble and in this spec: **primary `cs.CY`** (Computers & Society), **cross-list `stat.AP`** (Statistics – Applications), **optional cross-list `eess.SY`** (Systems & Control). `cs.SE` is NOT recommended as primary. Rationale: this is submission-form metadata, not body content; the comment is a convenience record.

### 1.7 Out of Scope (explicitly NOT changed)
- The time-averaged `\overline{SI}^{MCDM}_i` vs per-(i,t) MCDM nuance in the blend equation (subtle, not a contradiction with results) — leave as-is.
- Any change to numerical results, figures, model formulas, or narrative conclusions.
- arXiv directory flattening — not needed; this report's includes are already path-clean (single folder + `.bbl`).

---

## 2. Non-Functional Requirements

### 2.1 Build Integrity
- **NFR-001:** After all edits, `latexmk -pdf conference_101719.tex` MUST exit 0 with **zero undefined references** and **zero undefined citations**.
- **NFR-002:** Overfull/underfull box count MUST NOT increase beyond the current baseline (1 overfull).

### 2.2 Reversibility / Traceability
- **NFR-003:** All edits MUST be confined to `conference_101719.tex` (no figure, bib, or code changes), each mapping to exactly one FR, so the diff is reviewable line-by-line.

### 2.3 Fidelity
- **NFR-004:** No edit may change a reported numeric result, equation, or experimental conclusion; edits only correct inconsistencies *toward the deployed-code ground truth* or remove non-content artifacts.

---

## 3. System Constraints
- **C-1:** IEEEtran `conference` class; biblatex/biber backend; compiled with TeX Live 2025 `latexmk`.
- **C-2:** Single-file source; bibliography `reference.bib`; figures are local `.png` + `system-architecture.tex` `\input`.
- **C-3:** Ground-truth authority is the deployed backend, not prior drafts.

---

## 4. Acceptance Criteria
- **AC-1 (FR-001):** `grep "lambda^\star" conference_101719.tex` shows `100000` everywhere; no remaining `\lambda^\star = 10000`.
- **AC-2 (FR-002):** Appendix "Final Blend" affirms α-blend shipped at default 0.7 and references the §IV blended equation; the string "No blending parameter" is absent.
- **AC-3 (FR-003/004):** Each perturbation/deviation appendix sentence references the matching `-birch` and `-broad` labels exactly once each; no label referenced twice in the same sentence.
- **AC-4 (FR-005):** `grep "Team Member Contribution" conference_101719.tex` returns nothing; `\label{appendix:contributions}` is gone; document still compiles.
- **AC-5 (FR-006):** No `\pm 50\%` claim remains in Results §IX.
- **AC-6 (FR-007):** No standalone `---` lines remain in the body.
- **AC-7 (FR-008):** `\nocite{*}` is absent; bibliography length decreases; still no undefined citations.
- **AC-8 (FR-009):** Acknowledgment is a multi-sentence AI-use + VTTI disclosure.
- **AC-9 (FR-010):** arXiv-class comment present in preamble.
- **AC-10 (NFR-001):** Clean `latexmk` build, 0 undefined refs/cites, PDF produced.

---

## 5. Priority Summary
| Priority | Requirements |
|----------|-------------|
| Must-have | FR-001 … FR-006, NFR-001, NFR-003, NFR-004 |
| Should-have | FR-007 … FR-010, NFR-002 |
| Nice-to-have | — |
