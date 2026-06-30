# Template generator — build progress (v0.3.0)

Loop tracker. Spec: `2026-06-30-femrep-template-generator-design.md`. Approach A.
Test venv: `./.test-venv/bin/python -m pytest tests/ -q`. Build wheel:
`./.test-venv/bin/python -m build -w`.

## Checklist
- [x] 1. Spec written + committed
- [x] 2. `templates.py` module + tests (model, validate, to_config, seed, per-project I/O)
- [x] 3. `report_pdf.py` section-registry refactor + tests (subset/reorder/number/intro; default unchanged)
- [x] 4. `report_docx.py` section-registry refactor + tests (mirror PDF)
- [ ] 5. `workflow.load_config` + `run_report` template overlay; CLI `--template-file`; tests
- [x] 6. GUI: project picker, template dropdown, TemplateDialog (list, new blank/from-result, dup/delete, branding form, section checklist+reorder+intro, save); 2 offscreen tests
- [ ] 7. Full suite green; build wheel; bump 0.3.0
- [ ] 8. Re-bundle Windows installer + README/limitations note; release v0.3.0
- [ ] 9. Polish pass (code-review/simplify), changelog, final verify

## Notes / decisions
- 9 sections (governance + manifest split) to keep default output byte-for-byte.
- build_story/build_doc are the test seams; section list key-presence (not truthiness)
  distinguishes "no template" from "empty template".
- GUI modal feedback (_save) split from persistence (_persist) so logic is headless-testable.
- PySide6 added to .test-venv; GUI tests importorskip + QT_QPA_PLATFORM=offscreen.

## Contract (frozen)
SECTIONS order: summary, model, meshing, composites, solve, results, gci, governance.
Cover/title-block always rendered from branding (not in numbered list).
Template schema v1: {femrep_template_version, name, branding{...config keys...}, sections[{key,enabled,intro}]}.
Per-project JSON at <project>/templates/<slug>.json.

## Notes / decisions
- (none yet)
