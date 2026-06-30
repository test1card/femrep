# femrep report-template generator — design

**Date:** 2026-06-30
**Status:** approved (approach A)
**Target release:** v0.3.0

## Goal

Let a non-developer engineer build, save, and reuse **named report templates**
per femrep project, then generate a customized PDF/DOCX report against one — all
from the GUI. A template controls the report's **branding / title block** and its
**section layout** (which sections appear, in what order, with optional per-section
intro text).

## Approach (A): section registry

Both renderers currently hardcode sections inline with fixed numbering
(`"1. Summary"`, `"2. Model"`, …). We refactor each section into a named builder
behind a shared ordered registry. `render()` iterates the template's
enabled-and-ordered section list and numbers dynamically. Default behavior (no
template) renders all sections in canonical order — identical to today.

## Components & boundaries

### 1. `femrep/templates.py` (new) — template model & I/O (pure stdlib)

Single source of truth for the section catalog and template persistence.

```python
SECTIONS = [   # canonical order + default title; cover is separate (always on)
    ("summary",    "Summary"),
    ("model",      "Model"),
    ("meshing",    "Meshing"),
    ("composites", "Composites / CFRP"),
    ("solve",      "Mechanical / solve"),
    ("results",    "Results"),
    ("gci",        "Mesh independence (GCI)"),
    ("governance", "Governance"),
]
SECTION_KEYS = {k for k, _ in SECTIONS}
```

Template dict (schema v1):
```json
{
  "femrep_template_version": 1,
  "name": "MyCompany Standard",
  "branding": { <all current config.yaml keys> },
  "sections": [ {"key": "summary", "enabled": true, "intro": ""}, ... ]
}
```

API:
- `default_template(name="Default") -> dict` — neutral branding + all sections enabled in canonical order.
- `validate(tpl) -> dict` — coerce/repair: fill missing branding keys from defaults, drop unknown section keys, append any missing known sections (disabled) so the catalog is always complete, ensure version.
- `to_config(tpl) -> dict` — flatten to the flat `cfg` dict the renderers consume: branding keys at top level, plus `cfg["sections"]` = ordered list of enabled `{key,title,intro}` (title resolved from registry), plus `cfg["template"]=name`.
- `seed_from_results(results, name) -> dict` — auto-enable only data-bearing sections: `composites` only if `results.get("composite")`/layup present; `gci` only if a GCI study present; everything else default-on; pre-fill `title`/units hints from results. Returns a template the user then edits.
- Persistence (per-project): `templates_dir(project) -> Path` (`<project>/templates`), `list_templates(project) -> list[str]`, `load_template(project, name) -> dict`, `save_template(project, tpl) -> Path`, `delete_template(project, name)`.
- Path-based for GUI file dialogs / sharing: `load_path(path) -> dict`, `save_path(path, tpl)`.

Files are JSON: `<project>/templates/<slug>.json`. Stdlib-first, matches the
repo ethos (no new deps).

### 2. Renderer refactor — `report_pdf.py`, `report_docx.py`

Each renderer exposes a builder map keyed by the same section keys:
```python
SECTION_BUILDERS = {"summary": _section_summary, "model": _section_model, ...}
```
Each builder has a uniform signature, e.g.
`_section_summary(story, n, results, manifest, checks, gci, cfg, st, figures, intro) -> None`
(DOCX analog operates on `doc`). `render()`:
1. builds cover band + title block from branding (always),
2. resolves the section list: `cfg.get("sections")` if present, else the full
   canonical list (all enabled) — preserving today's output,
3. iterates, calling each builder with a running 1-based number and injecting
   `intro` as a lead paragraph when non-empty.

Numbering is dynamic (the Nth enabled section is "N. Title"). Cross-references
that today assume fixed numbers are removed/relativized.

### 3. `workflow.load_config` + CLI

- `load_config(path, template=None, template_obj=None)`: keep flat reader + the 4
  built-in named `TEMPLATES`; add an overlay path that accepts a validated
  template dict (from a JSON file) and merges branding + attaches `sections`.
- `run_report(..., template_file: Path | None = None)` threads a chosen template
  through to `load_config`.
- CLI: new `--template-file PATH`; existing `--template NAME` (built-ins) stays.

### 4. GUI — new "Templates" tab (PySide6)

Thin UI over `templates.py` + `workflow`; all testable logic lives in those
modules. Adds:
- a **project** control (open/create a femrep project → sets the templates dir),
- a **template list** with: New blank, New from result… (calls `seed_from_results`),
  Duplicate, Delete, and an edit form (branding fields + a section checklist with
  up/down reorder + per-section intro text), Save.
- On the report screen, a **template dropdown** populated from the current
  project; "Generate report" renders against the selected template.

## Data flow

```
template JSON ──load/validate──> tpl dict ──to_config──> cfg (flat + sections)
result file ──extract──> results ─┐
                                  ├─> govern ──> manifest, checks
gci/log ──────────────────────────┘
cfg + results + manifest + checks ──> report_pdf/docx.render
        (iterates cfg["sections"]: enabled, ordered, numbered, intro)
   └─> report.pdf / report.docx
seed: results ──seed_from_results──> draft tpl (data-bearing sections enabled)
```

## Error handling

- `validate()` repairs malformed/partial templates rather than throwing (a
  non-dev must never see a stack trace from a hand-shared file); unknown keys are
  dropped, missing ones filled. A non-JSON file raises a clear `ValueError`.
- Empty section list ⇒ falls back to a cover-only report with a visible note;
  generation never crashes on an over-pruned template.
- Selecting a template whose `logo` path is missing ⇒ text wordmark fallback
  (existing behavior), not a crash.

## Testing (offline, no Ansys/Qt)

- `templates.py`: `default_template`/`validate` round-trip; `validate` repairs
  partial + drops unknown + completes catalog; `to_config` flattens correctly;
  `seed_from_results` enables exactly the data-bearing sections for synthetic
  results (with/without composite, with/without gci); save→list→load→delete in a
  tmp project.
- renderers: with a template enabling a subset+reorder, the produced PDF `story`
  (and DOCX paragraphs) contain exactly those section titles, in that order, with
  correct running numbers; disabled section absent; intro text present; **default
  (no template) output unchanged** vs current section set; empty-sections
  fallback note present.
- workflow/CLI: `--template-file` overlays branding + sections; built-in
  `--template` and bare `config.yaml` still work.
- GUI logic that is non-Qt (seed, list population helper) tested via `templates.py`.

## Scope / non-goals

- No run defaults (mode/units/QoI) in templates — per-analysis choices stay at
  run time. (Deferred; cheap to add later.)
- No global/shared template library — per-project only (a project folder, or its
  `templates/`, can be copied to share).
- GUI widget rendering is not headless-unit-tested; logic is pushed down to
  tested modules.

## Backward compatibility

Default render path (no template / plain `config.yaml` / built-in `--template`)
produces byte-for-byte the same sections as v0.2.1. New behavior is opt-in via a
template file or the GUI.
