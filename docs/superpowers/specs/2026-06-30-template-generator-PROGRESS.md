# Template generator — build progress (v0.3.0)

Loop tracker. Spec: `2026-06-30-femrep-template-generator-design.md`. Approach A.
Test venv: `./.test-venv/bin/python -m pytest tests/ -q`. Build wheel:
`./.test-venv/bin/python -m build -w`.

## Checklist
- [ ] 1. Spec written + committed
- [ ] 2. `templates.py` module + tests (model, validate, to_config, seed, per-project I/O)
- [ ] 3. `report_pdf.py` section-registry refactor + tests (subset/reorder/number/intro; default unchanged)
- [ ] 4. `report_docx.py` section-registry refactor + tests (mirror PDF)
- [ ] 5. `workflow.load_config` + `run_report` template overlay; CLI `--template-file`; tests
- [ ] 6. GUI: Templates tab (project picker, list, new blank/from-result, edit form, save), report-screen template dropdown
- [ ] 7. Full suite green; build wheel; bump 0.3.0
- [ ] 8. Re-bundle Windows installer + README/limitations note; release v0.3.0
- [ ] 9. Polish pass (code-review/simplify), changelog, final verify

## Contract (frozen)
SECTIONS order: summary, model, meshing, composites, solve, results, gci, governance.
Cover/title-block always rendered from branding (not in numbered list).
Template schema v1: {femrep_template_version, name, branding{...config keys...}, sections[{key,enabled,intro}]}.
Per-project JSON at <project>/templates/<slug>.json.

## Notes / decisions
- (none yet)
