# Review-3 deck — figures to place

Deck: `documents/PWP1 - Review 3 - DSC06 (Slide 19 onwards).pptx` (30 slides).
It begins at the **Class Diagram** — template slide 19 — so slides 1–18 still come
from the Review-2 deck. Ten slides carry a grey placeholder box: delete the box,
paste the image in its place, keep the caption below it.

Figures are numbered in slide order: **1–4 are the UML diagrams, 5–10 are
application screenshots.**

---

## Figures 1–4 — the UML diagrams (slides 1, 3, 5, 7)

Source files are in `diagrams/`. Open each in draw.io, then **File ▸ Export as ▸ PNG**
with *Zoom 200%*, *Border 10*, *Transparent background off*. Paste the PNG into the
matching slide — the placeholder is already sized to that diagram's exact aspect
ratio, so it will fill the box without letterboxing.

| Slide | Figure | File | Aspect |
|---|---|---|---|
| 1 | **Figure 1** — Class diagram | `diagrams/class-diagram.drawio` | wide, 2620 × 1150 |
| 3 | **Figure 2** — Sequence diagram | `diagrams/sequence-diagram.drawio` | 2900 × 1830 |
| 5 | **Figure 3** — Use case diagram | `diagrams/use-case-diagram.drawio` | 1980 × 1180 |
| 7 | **Figure 4** — Activity diagram | `diagrams/activity-diagram.drawio` | **portrait**, 1760 × 2500 |

Slides 2, 4, 6 and 8 hold the written description for each diagram, in the same
"Notation / Input / Processing" style the Review-2 architecture slides used.

---

## Figures 5–10 — application screenshots (slides 11–16)

Target size is roughly **8.9 in × 2.3 in** (a wide crop) — capture the browser at a
wide window so the panels sit side by side rather than stacked. Run in fixture mode
first so every figure comes from the same recorded run:

```bash
RESEARCHGPT_FIXTURE=1 python -m uvicorn researchgpt.api.app:app --port 8000
cd frontend && npm run dev        # http://localhost:5173/  (NOT 127.0.0.1)
```

| Slide | Figure | What to capture |
|---|---|---|
| 11 | **Figure 5** — Run control and live agent progress | Panel 1 (run control, with the research question typed in and the paper budget at 10) **and** Panel 2 (agent progress) in one shot, captured while agents are still transitioning so at least one row shows an in-progress state. |
| 12 | **Figure 6** — Critic decision chain | Panel 2 after the run has finished, scrolled so all four Critic decisions are visible: `RETRIEVE → REPLAN → RETRIEVE → WRITE`, with the iteration counter (3 of 4). If the corpus figure 271 → 551 is on screen, include it. |
| 13 | **Figure 7** — Evidence inspection | Panel 3 with a verified sentence **clicked open**, showing the evidence span, the source paper and the support score. Pick a claim with a high score so the span is clearly relevant — `c0001` (0.9994) works well. |
| 14 | **Figure 8** — Dropped claims + HITL | Panel 4 listing all three dropped claims with their support scores (0.2169, 0.0098, 0.0061) and the confirm / override control visible. |
| 15 | **Figure 9** — Review output and artefacts | The rendered `review.md` showing prose with `[n]` citations, plus the artefact list/download links. If they don't fit in one shot, put the review on the left and a file listing of `outputs/runs/fixture/` on the right in a two-up crop. |
| 16 | **Figure 10** — Regression suite | Terminal running `python -m pytest tests/ -q`, cropped to the last few lines so the summary is legible: `334 passed, 1 skipped`. |

---

## Notes

- The deck says **334 passed, 1 skipped** — verified by a full run on 2026-09-08.
  The `README.md` figure of 284 is stale; the suite now collects 335.
- Figures 7 and 8 are the two that carry the Verifier argument. If any screenshot
  is worth retaking until it is crisp, it is these.
- Use the same browser theme in all five app screenshots.
- If the Review-2 slides you paste in front already number their own figures,
  renumber this deck's captions to continue from there.
