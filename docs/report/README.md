# Report drafts

Chapter drafts for the written report (template: `docs/course_material/ReportUseCase_template.docx`).
Ch2–Ch3 also feed the first oral presentation (27 Oct 2026, 15 min: use case + requirements).

| File | Template chapter | Status |
|---|---|---|
| `ch2_use_case.md` | 2 — Needs, use case, actors, benefits | Draft |
| `ch3_requirements.md` | 3 — Technical requirements and capabilities | Draft |
| `references.md` | References | Draft (links/versions to add) |

**Markers.** `[VERIFY: …]` = fact to check against a primary source. `[TODO: …]` = content still missing.
`[UNVERIFIED]` = inherited from a config value that has no source yet (`docs/assumptions.md`). No marker may
survive into the submitted report.

**Numbers** come from citations or from the model (`make run` → `results/results.json`). If a config value
changes, re-check the numbers quoted in Ch3 §3.4.

**Convert to Word** with the course template's styles:

```
pandoc docs/report/ch2_use_case.md docs/report/ch3_requirements.md docs/report/references.md \
  --reference-doc=docs/course_material/ReportUseCase_template.docx -o report_draft.docx
```
