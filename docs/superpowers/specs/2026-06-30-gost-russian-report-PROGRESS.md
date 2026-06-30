# GOST 7.32-2017 Russian report profile — build progress (v0.4.0)

Loop tracker. Standard: ГОСТ 7.32-2017, DOCX only, титульный лист (no ЕСКД frame),
fully Russian (zero English label words). Separate renderer → no regression to the
v0.3.0 English path. Test venv: `./.test-venv/bin/python -m pytest tests/ -q`.

## Checklist
- [ ] 1. Spec + tracker committed
- [ ] 2. `locale_ru.py` — section titles, table headers, verdict/status/analysis/QoI/units maps, GOST structural + титул labels, claim/введение/заключение/реферат phrasing; + tests
- [ ] 3. `report_gost_docx.py` — титульный лист, реферат, содержание, введение, основная часть (numbered RU sections), заключение; GOST formatting (Times New Roman 14, 1.5, поля 30/15/20/20 mm, абзац 1.25, justify, page numbers, титул unnumbered); build_gost_doc seam; + tests
- [ ] 4. Schema: template `profile` ("default"|"gost_ru") + GOST title-page branding fields; validate defaults; tests
- [ ] 5. Wiring: run_report routes profile=gost_ru → report_gost_docx (force .docx); CLI `--profile`; tests
- [ ] 6. GUI: профиль selector + GOST title-page fields in TemplateDialog; offscreen test
- [ ] 7. Zero-English-labels test passes; GOST formatting test; full suite green; build wheel; bump 0.4.0
- [ ] 8. README + CHANGELOG; re-bundle installer; release v0.4.0
- [ ] 9. Polish; verify Cyrillic in generated docx; final verify

## Contract / decisions
- Structural elements (ГОСТ 7.32 §6): ТИТУЛЬНЫЙ ЛИСТ, РЕФЕРАТ, СОДЕРЖАНИЕ, ВВЕДЕНИЕ,
  основная часть (numbered), ЗАКЛЮЧЕНИЕ. (Список источников/приложения optional, off by default.)
- Основная часть = template's enabled sections, Russian titles, numbered 1..N.
- Auto-generated реферат/введение/заключение from results (minimal hand-work).
- Proper nouns (Ansys/Nastran) and unit symbols kept; mm→мм where natural. Verdicts:
  pass→соответствует, fail→не соответствует, not_done→не выполнено.
- Selection: template profile field; run_report forces .docx + GOST renderer.
- Zero-English enforced by a test scanning all doc text against a forbidden label list.

## Notes
- (none yet)
