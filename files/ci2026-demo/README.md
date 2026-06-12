# CI/HCOMP 2026 Demo Draft

This folder contains a separate ACM Collective Intelligence 2026 demo-track
adaptation of the VTTSI-Chat paper.

## Target Track

- Conference: ACM Collective Intelligence 2026, co-located with ACM HCOMP 2026
- Track: Posters and Demos, demo submission
- Topic affiliation: HCOMP / human-AI complementarity, with CI framing around
  collective intelligence and the 2026 theme, Connections
- Submission deadline: July 16, 2026, 11:59 pm AoE
- Notification: August 5, 2026

## Requirements Reflected

- Non-anonymized, single-blind demo writeup
- Non-archival
- Main description kept to a compact 2-page ACM manuscript-style PDF
- Includes system description, interaction model, expected audience engagement,
  logistics, screenshots, and LLM-use disclosure
- Uses ACM LaTeX `manuscript` mode, matching the CI/HCOMP general submission
  instruction to submit a single-column review copy

Source pages checked:

- https://ci.acm.org/2026/
- https://ci.acm.org/2026/posters-demos.html
- https://ci.acm.org/2026/general-submission-instructions.html
- https://ci.acm.org/2026/topics.html

## Build

```bash
cd files/ci2026-demo
latexmk -pdf -interaction=nonstopmode -halt-on-error vttsi-chat-ci2026-demo.tex
```

Output:

- `vttsi-chat-ci2026-demo.pdf`

## Simple Architecture Graph

This folder also includes a lightweight system architecture graph suitable for
the demo paper, poster, or video walkthrough:

- `system-architecture-simple.dot` - editable Graphviz source
- `system-architecture-simple.png` - raster version for slides/docs
- `system-architecture-simple.svg` - editable/vector web version
- `system-architecture-simple.pdf` - vector PDF version for LaTeX

Regenerate it with:

```bash
cd files/ci2026-demo
dot -Tpng system-architecture-simple.dot -o system-architecture-simple.png
dot -Tsvg system-architecture-simple.dot -o system-architecture-simple.svg
dot -Tpdf system-architecture-simple.dot -o system-architecture-simple.pdf
```

## Remaining Submission Item

The demo track requires a video walkthrough. The paper currently says the
walkthrough will accompany the EasyChair submission; record and add the final
video URL before submission if EasyChair asks for it in the PDF or supplement.
