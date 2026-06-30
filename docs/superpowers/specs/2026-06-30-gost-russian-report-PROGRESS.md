# GOST 7.32-2017 Russian report profile — build progress (v0.4.0)

Loop tracker. Standard: ГОСТ 7.32-2017, DOCX only, титульный лист (no ЕСКД frame),
fully Russian (zero English label words). Separate renderer → no regression to the
v0.3.0 English path. Test venv: `./.test-venv/bin/python -m pytest tests/ -q`.

## Checklist
- [x] 1. Spec + tracker committed
- [x] 2. `locale_ru.py` + 5 tests
- [x] 3. `report_gost_docx.py` + 4 tests (structure, formatting, zero-English, section selection)
- [x] 4. Schema: `profile` + GOST title-page fields; validate defaults; tests
- [x] 5. Wiring: run_report → report_gost_docx (force .docx); CLI `--profile`; batch; tests
- [x] 6. GUI: Профиль selector + GOST fields (auto) + _render_to routing; 2 offscreen tests
- [x] 7. Zero-English + GOST formatting tests green; full suite 51 passed; bumped 0.4.0
- [ ] 8. README + CHANGELOG done; build wheel; re-bundle installer; release v0.4.0
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
