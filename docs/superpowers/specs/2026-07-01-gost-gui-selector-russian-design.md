# ГОСТ profile selectable in the GUI + full Russian GUI — design (v0.5.x)

## Problem

The ГОСТ 7.32-2017 report renderer (`report_gost_docx.py`), its Russian string
layer (`locale_ru.py`), the schema field (`profile: "gost_ru"`), and the
CLI (`--profile gost_ru`) all already exist and pass the suite (73 tests green).
The **only** gap is the desktop GUI:

1. **ГОСТ is not directly choosable.** The single way to reach it is a hidden
   sequence: open/create a project → *Управление шаблонами…* → create a template →
   set *Профиль → ГОСТ 7.32-2017* → save → pick that template. The main wizard's
   **Шаблон** dropdown offers only `Built-in default`. The README even claims
   "Select Профиль → ГОСТ 7.32-2017 in the GUI", but no such direct control exists.
2. **The GUI is not fully Russian.** `Built-in default` is English, and the whole
   *Управление шаблонами* editor and its dialogs/messages are English (`New blank`,
   `Duplicate`, `Save template`, branding labels `title`/`author`/`company`, file
   pickers, message boxes, etc.). Visible labels in the main window carry English
   parentheticals/tooltips (`Сводка QoI (Summary)`, `(Attach)`, `(Contour)`, …).

## Goal

- Make **ГОСТ 7.32-2017** a first-class, always-available choice in the main
  window's **Шаблон** dropdown — usable with **no project and no template**.
- Make **every user-visible string in the GUI Russian**, with the same
  "zero-English-label-words" discipline already enforced for the ГОСТ document
  (proper nouns Ansys/Nastran/femrep/femis and abbreviations GCI/QoI/PDF/DOCX/SHA
  excepted).

## Non-goals (YAGNI)

- No PDF-GOST. ГОСТ remains DOCX-only (its renderer is DOCX-only by design).
- No new inline title-page form in the main window. With no template, the ГОСТ
  титульный лист uses the Russian defaults/placeholders the renderer already
  produces; to fill организация/УДК/город/год/руководители precisely the user
  opens a project and the (now-Russian) template editor — the existing path,
  no longer *required* just to get a ГОСТ report.
- No change to the English report path, to the ГОСТ document content, or to the
  CLI. Only *how the profile is selected* and *the GUI language* change.
- The ГрОб/Летов rail-motto idea is parked as a separate, later follow-up.

## Design

### Part 1 — ГОСТ as a built-in dropdown choice

**Built-in entries.** The **Шаблон** dropdown (`cmb_template`) is always seeded
with two built-in profile entries, before any project templates:

| Display (Russian) | Carried profile | Sections | Export |
|---|---|---|---|
| `По умолчанию` | `default` | all default sections | PDF or DOCX (user picks) |
| `ГОСТ 7.32-2017 (DOCX, рус.)` | `gost_ru` | all default sections, Russian titles | forced Russian `.docx` |

Any per-project templates are listed after these two (unchanged).

**Robust identification.** The current code branches on the fragile string test
`name != "Built-in default"`. Replace it with per-item data: each combo item
stores a `Qt.UserRole` payload describing its **kind** —
`("builtin", "default")`, `("builtin", "gost_ru")`, or `("project", "<name>")`.
A small helper `self._current_template_ref()` returns that payload; all branching
keys off it. This removes label-string matching and lets a project legitimately
contain a template literally named "ГОСТ…" without colliding with the built-in.

**`_selected_cfg()`** (the flat cfg the renderers consume):
- `("builtin", "default")` → base `config.yaml`, `profile` stays `default`.
- `("builtin", "gost_ru")` → base `config.yaml` with `cfg["profile"] = "gost_ru"`
  and no `sections` override (renderer falls back to all default sections with
  Russian titles, exactly as a profile-only ГОСТ run does today).
- `("project", name)` → load + overlay the project template as today (its own
  `profile` honored).

**`_enabled_sections()`** mirrors the same three-way branch: built-ins → the full
default section list; project template → its enabled sections.

**Export wiring is already correct and reused unchanged:**
- `_render_to(path, cfg)` already routes `cfg["profile"] == "gost_ru"` to
  `report_gost_docx.render` and coerces the suffix to `.docx`.
- `_refresh_export_summary()` already detects the gost profile, forces the DOCX
  radio, disables the format radios, and shows the "русский .docx" note.

**Net effect:** launch GUI → attach result → *Извлечь и проверить* →
**Шаблон → ГОСТ 7.32-2017** → *Сгенерировать отчёт* → Russian ГОСТ `.docx`. No
project, no template editor.

### Part 2 — Everything in the GUI in Russian

**Centralize strings.** Add a `GUI` dict (and a `BRANDING_LABELS` map +
`branding_label()` helper) to `locale_ru.py`, the project's existing home for all
Russian strings. `gui.py` pulls every visible string from it; no Russian literals
are hardcoded in `gui.py` going forward. Scope of replacement in `gui.py`:

- **Шаблон dropdown:** built-in labels become the Russian constants above
  (`По умолчанию`, `ГОСТ 7.32-2017 (DOCX, рус.)`).
- **Main-window leftovers:** drop English parentheticals/tooltips that are mere
  translations — section captions (`Вложения`, `Контур`, `Сводка показателей`,
  `Проверки femis`, `Утверждение femis`), the figures toggle (`С иллюстрациями`),
  the per-step and per-card English tooltips. Proper nouns/abbreviations stay.
- **TemplateDialog (Управление шаблонами):** window title; list header; the
  buttons *New blank / New from result… / Duplicate / Delete*; field labels
  *Название*, *Профиль*; the **branding field labels** (rendered today from raw
  English keys `title/author/company/customer/...` → Russian via `BRANDING_LABELS`,
  incl. the ГОСТ ones `ministry/udc/city/year/report_type/head_org_title/
  head_work_title`); *Branding / title block*, *Sections (…)*, *Intro*, the intro
  placeholder, *Save template*.
- **Modal dialogs/messages:** `QFileDialog` titles (open/create project, seed
  result, logo, save report), `QInputDialog` (new-template name), and every
  `QMessageBox` body (e.g. "Open a project first…", "Could not load template…",
  "Saved template…", "Delete template…?", "Render failed…", success "Отчёт
  сохранён"). The window/app name `femrep` is kept as a proper noun.

**Allowed exceptions** (excluded from the zero-English check): proper nouns
`femrep`, `femis`, `Ansys`, `Nastran`; abbreviations `GCI`, `QoI`, `PDF`, `DOCX`,
`SHA-256`; unit symbols; file names/extensions.

## Components & boundaries

- `locale_ru.py` — **owns all Russian strings.** New: `GUI` dict,
  `BRANDING_LABELS`, `branding_label(key)`. Pure data + tiny helpers; no Qt import.
- `gui.py` — **owns layout and behavior**, reads strings from `locale_ru`.
  Changed units: dropdown seeding/refresh, `_current_template_ref()`,
  `_selected_cfg()`, `_enabled_sections()`, and every string site. Routing
  (`_render_to`) and export-summary logic are untouched.
- `templates.py`, `report_gost_docx.py`, `workflow.py`, `cli.py` — **unchanged.**

## Testing

Mirror the existing zero-English discipline (`tests/test_gost_report.py`'s
`FORBIDDEN` list scanned case-insensitively) and the offscreen-Qt pattern
(`tests/test_gui_templates.py`).

1. **Built-in ГОСТ routes with no project.** Seed `last_payload` (reuse the
   existing fixture in `test_render_to_routes_gost_profile_to_russian_docx`),
   select the built-in `ГОСТ 7.32-2017` entry on a `FemrepWindow` with
   `project = None`, assert `_selected_cfg()["profile"] == "gost_ru"` and that
   `_render_to(tmp/"r.pdf", cfg)` yields a `.docx` containing `РЕФЕРАТ`.
2. **Built-in default stays default.** Selecting `По умолчанию` →
   `_selected_cfg()["profile"] == "default"`, no `sections` key, `.pdf` honored.
3. **GUI zero-English (strings).** Scan all `locale_ru.GUI` + `BRANDING_LABELS`
   values against the `FORBIDDEN` list (minus the allowed exceptions); assert no
   leaks.
4. **GUI zero-English (widgets).** Instantiate `FemrepWindow` and `TemplateDialog`
   offscreen, walk every `QLabel/QPushButton/QRadioButton/QComboBox item/
   QLineEdit placeholder/window title`, collect text, assert no `FORBIDDEN` word
   appears. (Modal dialog strings are covered by test 3 because they are routed
   through `locale_ru.GUI`.)
5. **Existing suite stays green** — 73 passing tests, including the English
   report path and the existing template/profile roundtrip tests, must not
   regress.

## Deployment note

Tests run against the source via `PYTHONPATH=src`. The `femrep-gui` command the
user launches resolves to the **installed** copy in the venv
(`AppData/Local/femrep/venv`, currently a non-editable `0.5.6`). After
implementation, reinstall so the launcher reflects the change — either an
editable install (`pip install -e ".[gui]"`) or rebuild+reinstall the wheel. The
implementation plan owns this step.

## Risks

- **Dropdown identity:** addressed by the `Qt.UserRole` kind payload (no
  label-string matching).
- **Tooltip removal:** dropping English tooltips that were pure translations is
  intentional; no information is lost (the visible Russian label says the same).
- **Missed hardcoded string:** the widget-walk test (test 4) is the backstop; any
  literal that slips through fails the suite.
