# ГОСТ profile GUI selector + full-Russian GUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ГОСТ 7.32-2017 a first-class, always-available choice in the femrep desktop GUI (no project/template required), and bring every visible GUI string to Russian.

**Architecture:** Two parts. (1) The main-window **Шаблон** dropdown gains two always-present built-in entries — `По умолчанию` and `ГОСТ 7.32-2017 (DOCX, рус.)` — identified by a `Qt.UserRole` kind payload; selecting ГОСТ sets `cfg["profile"]="gost_ru"` and the existing `_render_to` routing emits a Russian `.docx`. (2) All visible GUI strings are centralized in `locale_ru.py` and replaced in `gui.py`, enforced by a zero-English test mirroring the existing ГОСТ-document discipline. The ГОСТ renderer, CLI, schema, and English report path are untouched.

**Tech Stack:** Python 3.14, PySide6 (Qt offscreen for tests), python-docx, pytest.

## Global Constraints

- **Version:** package is `0.5.6`; do not bump in this plan.
- **No regressions:** the existing suite (73 tests) must stay green; the English PDF/DOCX report path, CLI, `templates.py`, and `report_gost_docx.py` are **not modified**.
- **Russian-only GUI:** no English label words in visible GUI strings. Allowed exceptions (proper nouns / abbreviations / file masks): `femrep`, `femis`, `FEM`, `Ansys`, `Nastran`, `GCI`, `QoI`, `PDF`, `DOCX`, `SHA`, and file extensions (`*.png`, `*.f06`, …).
- **No copyrighted lyrics** anywhere in source/strings (the parked ГрОб rail-motto is out of scope).
- **Strings live in `locale_ru.py`** — `gui.py` must not hardcode user-visible label text (Russian or English) going forward.
- **Interpreter / test commands** (Git Bash):
  - `PY="/c/Users/3fall/AppData/Local/femrep/venv/Scripts/python.exe"`
  - Tasks 1–5 run tests against source: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/ -q`
  - Per the user's global rule, prefix `git` (and other passthrough commands) with `rtk` when running them.

---

## File Structure

- **Modify** `src/femrep/locale_ru.py` — add the `GUI` string dict, `BRANDING_LABELS` map + `branding_label()` helper, and the two built-in dropdown label constants. (Pure data + tiny helpers; no Qt import.)
- **Modify** `src/femrep/gui.py` — built-in ГОСТ dropdown entry + `_current_template_ref()` / profile-aware `_selected_cfg()` / `_enabled_sections()`; replace every visible string with a `locale_ru` lookup; drop English tooltips/parentheticals.
- **Create** `tests/test_gui_russian.py` — zero-English string test (Task 1), built-in-profile routing tests (Task 2), and offscreen widget-walk zero-English tests (Tasks 3–4). Shares a small Latin-token normalizer at the top of the file.
- **Modify** `README.md` — correct the "Select Профиль …" sentence to match the actual dropdown (Task 5).

---

## Task 1: locale_ru — GUI strings, branding labels, built-in constants

**Files:**
- Modify: `src/femrep/locale_ru.py` (append a new GUI section at end)
- Test: `tests/test_gui_russian.py` (new)

**Interfaces:**
- Produces:
  - `locale_ru.BUILTIN_DEFAULT_LABEL: str` = `"По умолчанию"`
  - `locale_ru.BUILTIN_GOST_LABEL: str` = `"ГОСТ 7.32-2017 (DOCX, рус.)"`
  - `locale_ru.BRANDING_LABELS: dict[str, str]` (keys mirror `templates.DEFAULT_BRANDING`)
  - `locale_ru.branding_label(key: str) -> str`
  - `locale_ru.GUI: dict[str, str]` (all GUI strings; values may contain `{ext}/{name}/{err}/{path}` format fields)

- [ ] **Step 1: Write the failing test**

Create `tests/test_gui_russian.py`:

```python
"""Russian-only GUI checks. The string-level test (Task 1) needs no Qt; the
widget-walk tests (Tasks 3-4) use offscreen Qt and skip without PySide6."""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Proper nouns / abbreviations that may legitimately appear in Russian UI text.
ALLOWED = {"femrep", "femis", "fem", "ansys", "nastran", "gci", "qoi",
           "pdf", "docx", "sha"}


def latin_leaks(text: str) -> list[str]:
    """Latin-letter runs (len>=2) in `text`, after stripping {placeholders} and
    file masks like *.png / .f06, excluding the ALLOWED proper-noun set."""
    t = re.sub(r"\{[^}]*\}", "", text or "")        # format placeholders
    t = re.sub(r"\*?\.[A-Za-z0-9]+", "", t)          # file extensions / globs
    return [w for w in re.findall(r"[A-Za-z]{2,}", t) if w.lower() not in ALLOWED]


def test_gui_strings_have_no_english():
    from femrep import locale_ru as L
    values = (list(L.GUI.values()) + list(L.BRANDING_LABELS.values())
              + [L.BUILTIN_DEFAULT_LABEL, L.BUILTIN_GOST_LABEL])
    leaked = sorted({w for v in values for w in latin_leaks(v)})
    assert leaked == [], f"English leaked into GUI strings: {leaked}"


def test_branding_label_maps_known_and_passes_unknown():
    from femrep import locale_ru as L
    assert L.branding_label("company") == "Организация"
    assert L.branding_label("udc") == "УДК"
    assert L.branding_label("totally_unknown_key") == "totally_unknown_key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py -q`
Expected: FAIL — `AttributeError: module 'femrep.locale_ru' has no attribute 'GUI'`.

- [ ] **Step 3: Add the GUI section to `locale_ru.py`**

Append at the end of `src/femrep/locale_ru.py`:

```python
# --- GUI (PySide6 desktop app) strings ---------------------------------------
# Centralized here so gui.py holds no hardcoded label text and a zero-English
# test can scan a single source. Proper nouns (femrep/femis/Ansys/Nastran) and
# abbreviations (GCI/QoI/PDF/DOCX) are intentionally kept.

# Built-in entries always present in the main-window «Шаблон» dropdown.
BUILTIN_DEFAULT_LABEL = "По умолчанию"
BUILTIN_GOST_LABEL = "ГОСТ 7.32-2017 (DOCX, рус.)"

# Branding / title-block field labels (template editor). Keys mirror
# templates.DEFAULT_BRANDING; unknown keys pass through unchanged.
BRANDING_LABELS = {
    "title": "Название",
    "author": "Автор",
    "company": "Организация",
    "project": "Проект",
    "customer": "Заказчик",
    "document_number": "Номер документа",
    "revision": "Редакция",
    "prepared_by": "Подготовил",
    "checked_by": "Проверил",
    "approved_by": "Утвердил",
    "logo": "Логотип",
    "color_primary": "Основной цвет",
    "color_accent": "Акцентный цвет",
    "color_warn": "Цвет предупреждения",
    "color_ok": "Цвет «норма»",
    "color_muted": "Приглушённый цвет",
    "font": "Шрифт",
    "page_size": "Размер страницы",
    "ministry": "Министерство (ведомство)",
    "udc": "УДК",
    "city": "Город",
    "year": "Год",
    "report_type": "Вид отчёта",
    "head_org_title": "Должность руководителя организации",
    "head_work_title": "Должность руководителя НИР",
}


def branding_label(key: str) -> str:
    return BRANDING_LABELS.get(key, key)


GUI = {
    # window / brand
    "window_title": "femrep — генератор отчётов по МКЭ под управлением femis",
    "brand_sub": "FEM-отчёты под femis",
    "rail_hint": "femis: вывод не сильнее своей проверки.",
    # step / card titles
    "step_result": "Результат",
    "step_check": "Проверка",
    "step_template": "Шаблон",
    "step_export": "Экспорт",
    # step 1 (result)
    "card1_sub": "Перетащите сюда любые файлы — результат, журнал, сетки GCI "
                 "или расчётную модель. Роль определяется автоматически.",
    "sec_attachments": "Вложения",
    "drop_text": "Перетащите файлы или нажмите, чтобы выбрать\n"
                 "результат · журнал · GCI · расчётная модель",
    "attach_required": "файл результата обязателен (.rst / .rth / .f06 / .op2)",
    "attach_ready": "готово к извлечению",
    "with_figures": "С иллюстрациями",
    "btn_extract": "Извлечь и проверить →",
    "attach_remove_tip": "Убрать",
    # step 2 (check)
    "card2_sub": "Результаты извлечены. Проверьте величину интереса и вердикты "
                 "проверок femis перед выпуском отчёта.",
    "sec_contour": "Контур",
    "preview_placeholder": "предпросмотр контура появится после извлечения",
    "sec_qoi": "Сводка показателей",
    "sec_gates": "Проверки femis",
    "sec_claim": "Утверждение femis",
    "contour_unavailable": "контур недоступен",
    "contour_unavailable_hint": "контур недоступен — см. историю по времени в отчёте",
    "btn_open_review": "Открыть HTML-обзор",
    "btn_next": "Далее →",
    "btn_back": "Назад",
    # step 3 (template)
    "card3_sub": "Проект и шаблон задают брендинг, разделы и профиль (например, ГОСТ).",
    "sec_project": "Проект",
    "btn_open_project": "Открыть / создать проект…",
    "btn_open_project_tip": "Открыть или создать папку проекта femrep с шаблонами",
    "project_none": "проект не выбран — встроенная разметка",
    "sec_template": "Шаблон оформления",
    "btn_manage_templates": "Управление шаблонами…",
    "sec_content": "Содержание отчёта (что попадёт в отчёт)",
    "avail_yes": "доступно",
    "avail_example": "контрольный пример",
    "avail_no_gci": "нет данных GCI",
    # step 4 (export)
    "card4_sub": "Сводка форматирования. Нажмите, чтобы сгенерировать итоговый отчёт.",
    "sec_summary": "Сводка",
    "sec_sections": "Разделы отчёта",
    "sections_none": "разделы не выбраны",
    "sec_format": "Формат",
    "gost_note": "Профиль ГОСТ — отчёт будет сохранён как русский .docx "
                 "(формат выбран автоматически).",
    "btn_generate": "Сгенерировать отчёт",
    "export_project": "Проект",
    "export_template": "Шаблон",
    "export_profile": "Профиль",
    "profile_default_name": "стандартный",
    # status
    "status_running": "выполняется…",
    "status_done": "готово",
    "status_error": "ОШИБКА",
    # dialogs / messages (modal — covered by the string-level test)
    "dlg_attach_files": "Выберите файлы",
    "filter_all": "Все файлы (*.*)",
    "dlg_open_project": "Открыть или создать папку проекта femrep",
    "dlg_save_report": "Сохранить отчёт",
    "filter_report": "Отчёт (*{ext})",
    "msg_attach_first": "Сначала прикрепите файл результатов.",
    "msg_extract_first": "Сначала извлеките результаты (шаг 1).",
    "msg_open_project_first": "Сначала откройте проект, чтобы хранить шаблоны.",
    "msg_load_template_failed": "Не удалось загрузить шаблон {name}: {err}",
    "msg_report_saved": "Отчёт сохранён:\n{path}",
    "msg_render_failed": "Не удалось сформировать отчёт:\n{err}",
    "startup_error_title": "femrep — ошибка запуска",
    "startup_error_body": "{tb}\n\nЛог: {path}",
    # template editor (dialog)
    "td_title": "femrep — шаблоны отчёта",
    "td_list_header": "Шаблоны в этом проекте:",
    "td_new_blank": "Создать пустой",
    "td_new_from_result": "Создать из результата…",
    "td_duplicate": "Дублировать",
    "td_delete": "Удалить",
    "td_name": "Название",
    "td_profile": "Профиль",
    "profile_default_label": "Стандартный (PDF/DOCX)",
    "profile_gost_label": "ГОСТ 7.32-2017 (DOCX, рус.)",
    "td_branding_header": "Брендинг / титульный блок:",
    "td_sections_header": "Разделы (отметьте для включения, порядок — кнопками ↑/↓):",
    "td_intro": "Вступление:",
    "td_intro_placeholder": "необязательный текст под заголовком раздела",
    "td_save": "Сохранить шаблон",
    "td_copy_suffix": "копия",
    "td_new_template_title": "Новый шаблон",
    "td_new_template_prompt": "Название шаблона:",
    "td_new_template_default": "Новый шаблон",
    "td_default_template_name": "По умолчанию",
    "td_seed_result_title": "Файл результата для основы шаблона",
    "filter_results": "Результаты (*.rst *.rth *.f06 *.op2);;Все файлы (*.*)",
    "td_seed_failed": "Не удалось прочитать результат для основы шаблона:\n{err}",
    "td_logo_title": "Изображение логотипа",
    "filter_images": "Изображения (*.png *.jpg *.jpeg)",
    "td_saved": "Шаблон сохранён:\n{path}",
    "td_delete_confirm": "Удалить шаблон {name}?",
    "td_from_result_name": "Из результата",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add src/femrep/locale_ru.py tests/test_gui_russian.py
rtk git commit -m "feat(gui): centralize Russian GUI strings + built-in profile labels in locale_ru"
```

---

## Task 2: GUI — built-in ГОСТ dropdown entry + profile-aware selection (Part 1)

**Files:**
- Modify: `src/femrep/gui.py` — `_build_step3` combo seeding; `_refresh_templates`; new `_current_template_ref`; `_selected_cfg`; `_enabled_sections`
- Test: `tests/test_gui_russian.py` (append)

**Interfaces:**
- Consumes: `locale_ru.BUILTIN_DEFAULT_LABEL`, `locale_ru.BUILTIN_GOST_LABEL`, `locale_ru.GUI` (Task 1).
- Produces:
  - `FemrepWindow._current_template_ref(self) -> tuple[str, str]` returning `("builtin","default")`, `("builtin","gost_ru")`, or `("project", <name>)`.
  - Built-in dropdown items carry their `(kind, ref)` tuple as `Qt.UserRole` data.
  - `_selected_cfg()` sets `cfg["profile"]="gost_ru"` for the built-in ГОСТ entry; `_enabled_sections()` returns the default section list for both built-ins.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gui_russian.py`:

```python
pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _payload() -> dict:
    return {
        "results": {"result_file": "000.f06", "result_sha256": "a",
                    "primary_qoi": {"name": "temperature", "units": "K",
                                    "min": 300.0, "max": 305.0,
                                    "hot_node": 1, "cold_node": 2},
                    "qoi_catalog": [{"name": "temperature"}],
                    "mesh": {"nodes": 10, "elements": 4, "element_types": {"tet": 4}},
                    "convergence": {"converged": True, "substeps": 1, "note": "ок"}},
        "manifest": {"analysis_type": "thermal", "units": "SI", "solver": "Nastran",
                     "solver_version": "0.1", "deck_path": None},
        "checks": {"claim": "", "gci": None,
                   "gates": [{"gate": "units", "verdict": "pass", "note": ""}],
                   "readiness": {"status": "issue_with_limitations",
                                 "summary": "", "items": []}},
        "figures": {},
    }


def test_builtin_gost_selected_routes_to_russian_docx(app, tmp_path):
    from docx import Document
    from femrep import gui, locale_ru as L
    win = gui.FemrepWindow()
    win.last_payload = _payload()
    i = win.cmb_template.findText(L.BUILTIN_GOST_LABEL)
    assert i >= 0, "built-in ГОСТ entry must be in the dropdown"
    win.cmb_template.setCurrentIndex(i)
    cfg = win._selected_cfg()
    assert cfg["profile"] == "gost_ru"
    out = win._render_to(tmp_path / "r.pdf", cfg)   # ask .pdf — must become .docx
    assert out.suffix == ".docx" and out.exists()
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "РЕФЕРАТ" in text


def test_builtin_default_stays_default(app):
    from femrep import gui, locale_ru as L
    win = gui.FemrepWindow()
    i = win.cmb_template.findText(L.BUILTIN_DEFAULT_LABEL)
    assert i >= 0
    win.cmb_template.setCurrentIndex(i)
    cfg = win._selected_cfg()
    assert cfg.get("profile", "default") == "default"
    assert "sections" not in cfg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py -q -k "builtin"`
Expected: FAIL — `findText(L.BUILTIN_GOST_LABEL)` returns -1 (dropdown still shows only "Built-in default").

- [ ] **Step 3: Implement the dropdown + selection logic**

In `src/femrep/gui.py`, in `_build_step3`, replace:

```python
        self.cmb_template = QComboBox()
        self.cmb_template.addItem("Built-in default")
        self.cmb_template.currentIndexChanged.connect(lambda _i: self._refresh_content_panel())
```

with:

```python
        self.cmb_template = QComboBox()
        self.cmb_template.addItem(locale_ru.BUILTIN_DEFAULT_LABEL, ("builtin", "default"))
        self.cmb_template.addItem(locale_ru.BUILTIN_GOST_LABEL, ("builtin", "gost_ru"))
        self.cmb_template.currentIndexChanged.connect(lambda _i: self._refresh_content_panel())
```

Replace the whole `_refresh_templates` method with:

```python
    def _refresh_templates(self, select: str | None = None):
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        self.cmb_template.addItem(locale_ru.BUILTIN_DEFAULT_LABEL, ("builtin", "default"))
        self.cmb_template.addItem(locale_ru.BUILTIN_GOST_LABEL, ("builtin", "gost_ru"))
        if self.project:
            for name in templates_mod.list_templates(self.project):
                self.cmb_template.addItem(name, ("project", name))
        if select:
            i = self.cmb_template.findText(select)
            if i >= 0:
                self.cmb_template.setCurrentIndex(i)
        self.cmb_template.blockSignals(False)
```

Add a new helper just above `_selected_cfg`:

```python
    def _current_template_ref(self) -> tuple[str, str]:
        """(kind, ref) for the selected dropdown item: ('builtin','default'),
        ('builtin','gost_ru'), or ('project', <name>). Defaults to builtin default."""
        data = self.cmb_template.currentData()
        return data if isinstance(data, tuple) else ("builtin", "default")
```

Replace the whole `_selected_cfg` method with:

```python
    def _selected_cfg(self):
        """Base config.yaml, then apply the selected dropdown entry: a built-in
        profile (default / gost_ru) or a project template overlay."""
        cfg = cli_mod._load_config(HERE / "config.yaml")
        kind, ref = self._current_template_ref()
        if kind == "builtin":
            if ref == "gost_ru":
                cfg["profile"] = "gost_ru"
        elif kind == "project" and self.project:
            try:
                tpl = templates_mod.load_template(self.project, ref)
                cfg.update(templates_mod.to_config(tpl))
            except (FileNotFoundError, ValueError) as e:
                QMessageBox.warning(self, "femrep",
                                    locale_ru.GUI["msg_load_template_failed"].format(
                                        name=repr(ref), err=e))
        return cfg
```

Replace the whole `_enabled_sections` method with:

```python
    def _enabled_sections(self) -> list[str]:
        """Ordered section keys for the selection. Both built-ins use the full
        default section list; a project template uses its enabled sections."""
        kind, ref = self._current_template_ref()
        if kind == "project" and self.project:
            try:
                tpl = templates_mod.load_template(self.project, ref)
                return [s["key"] for s in templates_mod.to_config(tpl).get("sections", [])]
            except (FileNotFoundError, ValueError):
                pass
        return [k for k, _ in templates_mod.SECTIONS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py -q -k "builtin"`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/ -q`
Expected: PASS — all previously-green tests plus the new ones (the existing `test_window_selected_cfg_overlays_project_template` still passes: default built-in is index 0 ⇒ base cfg with no `sections`; selecting project "Two" overlays sections).

- [ ] **Step 6: Commit**

```bash
rtk git add src/femrep/gui.py tests/test_gui_russian.py
rtk git commit -m "feat(gui): built-in ГОСТ 7.32-2017 dropdown entry, selectable with no project"
```

---

## Task 3: GUI — Russify the main window + window zero-English test (Part 2a)

**Files:**
- Modify: `src/femrep/gui.py` — `STEPS`, `_build_rail`, `_card`, all `_build_stepN`, `_pick_attach`, `_refresh_attachments`, `_populate_check`, `_refresh_export_summary`, `_render`, `main()` strings
- Test: `tests/test_gui_russian.py` (append)

**Interfaces:**
- Consumes: `locale_ru.GUI` (Task 1).
- Produces: `FemrepWindow` builds with no English visible strings (proper-noun exceptions allowed). `_card(title_key, subtitle)` signature drops the English-tooltip parameter.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui_russian.py`:

```python
def _widget_texts(root):
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit
    texts = []
    if root.windowTitle():
        texts.append(root.windowTitle())
    for w in root.findChildren(QLabel):
        texts.append(w.text())
    for w in root.findChildren(QAbstractButton):
        texts.append(w.text())
    for w in root.findChildren(QComboBox):
        for i in range(w.count()):
            texts.append(w.itemText(i))
    for w in root.findChildren(QLineEdit):
        texts.append(w.placeholderText())
    return texts


def test_main_window_has_no_english(app):
    from femrep import gui
    win = gui.FemrepWindow()
    leaked = sorted({w for t in _widget_texts(win) for w in latin_leaks(t)})
    assert leaked == [], f"English leaked into main window: {leaked}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py::test_main_window_has_no_english -q`
Expected: FAIL — leaks include `Attach`, `Contour`, `Summary`, `Gates`, `Claim`, `Project`, `Template`, `Sections`, `Format`, `with`, `figures`, `Built`, `default`.

- [ ] **Step 3: Russify the main window**

In `src/femrep/gui.py` make these edits.

(a) Replace the module-level `STEPS`:

```python
STEPS = ["step_result", "step_check", "step_template", "step_export"]
```

(b) In `_build_rail`, replace the brand/sub/step loop block:

```python
        brand = QLabel("femrep"); brand.setObjectName("brand")
        sub = QLabel(locale_ru.GUI["brand_sub"]); sub.setObjectName("brandsub")
        lay.addWidget(brand); lay.addWidget(sub)
        lay.addSpacing(22)

        self._rail_rows: list[tuple[QLabel, QLabel]] = []
        for i, key in enumerate(STEPS):
            row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            num = QLabel(str(i + 1)); num.setObjectName("num"); num.setAlignment(Qt.AlignCenter)
            step = QLabel(locale_ru.GUI[key]); step.setProperty("role", "step")
            rl.addWidget(num); rl.addWidget(step, 1)
            lay.addWidget(row)
            self._rail_rows.append((num, step))
        lay.addStretch()

        hint = QLabel(locale_ru.GUI["rail_hint"])
        hint.setObjectName("brandsub"); hint.setWordWrap(True)
        lay.addWidget(hint)
        return rail
```

(c) Replace `_card` (drop the English tooltip param):

```python
    def _card(self, title_key: str, subtitle: str):
        """Build a card QFrame, return (card, body_layout) with header pre-filled."""
        card = QFrame(); card.setObjectName("card")
        v = QVBoxLayout(card); v.setContentsMargins(36, 32, 36, 32); v.setSpacing(14)
        h = QLabel(locale_ru.GUI[title_key]); h.setObjectName("h2")
        v.addWidget(h)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("sub"); s.setWordWrap(True)
            v.addWidget(s)
        return card, v
```

(d) Set the window title in `__init__`: replace
`self.setWindowTitle("femrep — femis-governed FEM report generator")` with
`self.setWindowTitle(locale_ru.GUI["window_title"])`.

(e) `_build_step1` — replace the literals:
- `self._card("Результат", "Result", "Перетащите сюда…")` → `self._card("step_result", locale_ru.GUI["card1_sub"])`
- `self._section("Вложения (Attach)")` → `self._section(locale_ru.GUI["sec_attachments"])`
- `DropZone("Перетащите файлы…")` → `DropZone(locale_ru.GUI["drop_text"])`
- `self.lbl_attach_hint = QLabel("файл результата обязателен …")` → `QLabel(locale_ru.GUI["attach_required"])`
- `self.chk_figs = QRadioButton("С иллюстрациями (with figures)")` → `QRadioButton(locale_ru.GUI["with_figures"])`
- `self.btn_run = QPushButton("Извлечь и проверить →")` → `QPushButton(locale_ru.GUI["btn_extract"])`

(f) `_footer` — replace `back = QPushButton("Назад")` → `QPushButton(locale_ru.GUI["btn_back"])`.

(g) `_build_step2` — replace:
- `self._card("Проверка", "Check", "Результаты извлечены…")` → `self._card("step_check", locale_ru.GUI["card2_sub"])`
- `self._section("Контур (Contour)")` → `self._section(locale_ru.GUI["sec_contour"])`
- `self.preview = QLabel("предпросмотр контура…")` → `QLabel(locale_ru.GUI["preview_placeholder"])`
- `self._section("Сводка QoI (Summary)")` → `self._section(locale_ru.GUI["sec_qoi"])`
- `self._section("Проверки femis (Gates)")` → `self._section(locale_ru.GUI["sec_gates"])`
- `self._section("Утверждение femis (Claim)")` → `self._section(locale_ru.GUI["sec_claim"])`
- `self.btn_review = QPushButton("Открыть HTML-обзор")` → `QPushButton(locale_ru.GUI["btn_open_review"])`
- `nxt = QPushButton("Далее →")` → `QPushButton(locale_ru.GUI["btn_next"])`

(h) `_build_step3` — replace:
- `self._card("Шаблон", "Template", "Проект и шаблон…")` → `self._card("step_template", locale_ru.GUI["card3_sub"])`
- `self._section("Проект (Project)")` → `self._section(locale_ru.GUI["sec_project"])`
- `self.btn_project = QPushButton("Открыть / создать проект…")` → `QPushButton(locale_ru.GUI["btn_open_project"])`
- `self.btn_project.setToolTip("Open or create a femrep project folder that holds your templates")` → `self.btn_project.setToolTip(locale_ru.GUI["btn_open_project_tip"])`
- `self.lbl_project = QLabel("проект не выбран — встроенная разметка")` → `QLabel(locale_ru.GUI["project_none"])`
- `self._section("Шаблон оформления (Template)")` → `self._section(locale_ru.GUI["sec_template"])`
- `self.btn_manage = QPushButton("Управление шаблонами…")` → `QPushButton(locale_ru.GUI["btn_manage_templates"])`
- `self._section("Содержание отчёта (что попадёт в отчёт)")` → `self._section(locale_ru.GUI["sec_content"])`
- `nxt = QPushButton("Далее →")` → `QPushButton(locale_ru.GUI["btn_next"])`

(i) `_build_step4` — replace:
- `self._card("Экспорт", "Export", "Сводка форматирования…")` → `self._card("step_export", locale_ru.GUI["card4_sub"])`
- `self._section("Сводка (Summary)")` → `self._section(locale_ru.GUI["sec_summary"])`
- `self._section("Разделы отчёта (Sections)")` → `self._section(locale_ru.GUI["sec_sections"])`
- `self._section("Формат (Format)")` → `self._section(locale_ru.GUI["sec_format"])`
- `self.btn_render = QPushButton("Сгенерировать отчёт")` → `QPushButton(locale_ru.GUI["btn_generate"])`

(j) `_pick_attach` — replace the dialog literals:

```python
        paths, _ = QFileDialog.getOpenFileNames(
            self, locale_ru.GUI["dlg_attach_files"], "", locale_ru.GUI["filter_all"])
```

(k) `_refresh_attachments` — replace:
- `rm.setToolTip("Убрать")` → `rm.setToolTip(locale_ru.GUI["attach_remove_tip"])`
- the hint ternary →
```python
        self.lbl_attach_hint.setText(
            locale_ru.GUI["attach_ready"] if has_result
            else locale_ru.GUI["attach_required"])
```

(l) `_section_availability` — replace the three returned labels:
- `return "warn", "контрольный пример"` → `return "warn", locale_ru.GUI["avail_example"]`
- `return "ok", "доступно"` (gci branch) → `return "ok", locale_ru.GUI["avail_yes"]`
- `return "warn", "нет данных GCI"` → `return "warn", locale_ru.GUI["avail_no_gci"]`
- final `return "ok", "доступно"` → `return "ok", locale_ru.GUI["avail_yes"]`

(m) `_run` — `self.lbl_status.setText("выполняется…")` → `setText(locale_ru.GUI["status_running"])`.

(n) `_on_done` — `self.lbl_status.setText("готово")` → `setText(locale_ru.GUI["status_done"])`.

(o) `_on_fail` — `self.lbl_status.setText("ОШИБКА")` → `setText(locale_ru.GUI["status_error"])`.

(p) `_populate_check` — replace the two preview fallbacks:
- `self.preview.setText("контур недоступен")` → `setText(locale_ru.GUI["contour_unavailable"])`
- `self.preview.setText("контур недоступен — см. историю по времени в отчёте")` → `setText(locale_ru.GUI["contour_unavailable_hint"])`

(q) `_refresh_export_summary` — replace the summary block:

```python
        cfg = self._selected_cfg()
        gost = cfg.get("profile") == "gost_ru"
        name = self.cmb_template.currentText()
        proj = str(self.project) if self.project else locale_ru.GUI["project_none"]
        prof = "ГОСТ 7.32-2017" if gost else locale_ru.GUI["profile_default_name"]
        self.lbl_export.setText(
            f"<b>{locale_ru.GUI['export_project']}:</b> {proj}<br>"
            f"<b>{locale_ru.GUI['export_template']}:</b> {name}<br>"
            f"<b>{locale_ru.GUI['export_profile']}:</b> {prof}")
        if gost:
            self.lbl_gost.setText(locale_ru.GUI["gost_note"])
            self.rb_docx.setChecked(True)
            self.rb_pdf.setEnabled(False); self.rb_docx.setEnabled(False)
        else:
            self.lbl_gost.setText("")
            self.rb_pdf.setEnabled(True); self.rb_docx.setEnabled(True)
```

(r) `_refresh_export_sections` — replace the fallback `"разделы не выбраны"` → `locale_ru.GUI["sections_none"]`.

(s) `_render` — replace literals:
```python
        p, _ = QFileDialog.getSaveFileName(self, locale_ru.GUI["dlg_save_report"],
                                           str(base / ("report" + ext)),
                                           locale_ru.GUI["filter_report"].format(ext=ext))
```
```python
            out = self._render_to(Path(p), cfg)
            QMessageBox.information(self, "femrep",
                                    locale_ru.GUI["msg_report_saved"].format(out=out, path=out))
        except Exception as e:
            QMessageBox.critical(self, "femrep",
                                 locale_ru.GUI["msg_render_failed"].format(
                                     err=f"{e}\n{traceback.format_exc()[-600:]}"))
```
Note: drop the `if gost` title swap — the title is always `locale_ru.GUI["dlg_save_report"]`.

(t) `_run` guard + `_render` guard message boxes:
- in `_run`: `QMessageBox.warning(self, "femrep", "Сначала прикрепите файл результатов.")` → `...warning(self, "femrep", locale_ru.GUI["msg_attach_first"])`
- in `_render`: `QMessageBox.warning(self, "femrep", "Сначала извлеките результаты (шаг 1).")` → `...warning(self, "femrep", locale_ru.GUI["msg_extract_first"])`

(u) `main()` startup error dialog — replace:
```python
            QMessageBox.critical(None, locale_ru.GUI["startup_error_title"],
                                 locale_ru.GUI["startup_error_body"].format(
                                     tb=tb[-1500:], path=_crash_log_path()))
```
Add `from . import locale_ru` is already imported at module top — confirm it is (it is: `from . import locale_ru`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py::test_main_window_has_no_english -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/ -q`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
rtk git add src/femrep/gui.py tests/test_gui_russian.py
rtk git commit -m "feat(gui): main window fully Russian (strings via locale_ru) + zero-English test"
```

---

## Task 4: GUI — Russify the TemplateDialog + dialog zero-English test (Part 2b)

**Files:**
- Modify: `src/femrep/gui.py` — `TemplateDialog._build`, `_new_blank`, `_new_from_result`, `_duplicate`, `_delete`, `_save`, `_pick_logo`
- Test: `tests/test_gui_russian.py` (append)

**Interfaces:**
- Consumes: `locale_ru.GUI`, `locale_ru.branding_label` (Task 1).
- Produces: `TemplateDialog` builds with no English visible strings; branding rows labeled via `branding_label(key)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gui_russian.py`:

```python
def test_template_dialog_has_no_english(app, tmp_path):
    from femrep import gui, templates
    project = tmp_path / "proj"
    templates.templates_dir(project).mkdir(parents=True)
    dlg = gui.TemplateDialog(project)
    dlg._load_into_form(templates.default_template("Шаблон"))
    leaked = sorted({w for t in _widget_texts(dlg) for w in latin_leaks(t)})
    # QFormLayout labels are QLabel children; branding rows must be Russian too.
    from PySide6.QtWidgets import QFormLayout
    for form in dlg.findChildren(QFormLayout):
        for r in range(form.rowCount()):
            item = form.itemAt(r, QFormLayout.LabelRole)
            if item and item.widget() is not None:
                leaked += [w for w in latin_leaks(item.widget().text())]
    assert sorted(set(leaked)) == [], f"English leaked into TemplateDialog: {sorted(set(leaked))}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py::test_template_dialog_has_no_english -q`
Expected: FAIL — leaks include `Templates`, `New`, `blank`, `from`, `result`, `Duplicate`, `Delete`, `Name`, `Profile`, `Branding`, `title`, `block`, `Sections`, `Intro`, `Save`, `template`, and branding keys `title/author/company/...`.

- [ ] **Step 3: Russify the TemplateDialog**

In `src/femrep/gui.py`, `TemplateDialog._build`, make these edits.

(a) Window title in `__init__`: replace `self.setWindowTitle("femrep — report templates")` →
`self.setWindowTitle(locale_ru.GUI["td_title"])`.

(b) Left column:
```python
        left.addWidget(QLabel(locale_ru.GUI["td_list_header"]))
        left.addWidget(self.lst, 1)
        for label_key, slot in [("td_new_blank", self._new_blank),
                                ("td_new_from_result", self._new_from_result),
                                ("td_duplicate", self._duplicate),
                                ("td_delete", self._delete)]:
            b = QPushButton(locale_ru.GUI[label_key]); b.clicked.connect(slot); left.addWidget(b)
```

(c) Form rows + profile combo:
```python
        self.f_name = QLineEdit()
        form.addRow(locale_ru.GUI["td_name"], self.f_name)
        self.f_profile = QComboBox()
        self._profiles = [(locale_ru.GUI["profile_default_label"], "default"),
                          (locale_ru.GUI["profile_gost_label"], "gost_ru")]
        for label, _ in self._profiles:
            self.f_profile.addItem(label)
        form.addRow(locale_ru.GUI["td_profile"], self.f_profile)
```

(d) Branding field rows — replace `form.addRow(key, host)` / `form.addRow(key, le)` with the Russian label:
```python
        self.brand_fields: dict[str, QLineEdit] = {}
        for key in templates_mod.DEFAULT_BRANDING:
            le = QLineEdit()
            self.brand_fields[key] = le
            if key == "logo":
                row = QHBoxLayout(); row.addWidget(le, 1)
                browse = QPushButton("…"); browse.setFixedWidth(28)
                browse.clicked.connect(self._pick_logo); row.addWidget(browse)
                host = QWidget(); host.setLayout(row)
                form.addRow(locale_ru.branding_label(key), host)
            else:
                form.addRow(locale_ru.branding_label(key), le)
```

(e) Remaining right-column labels/buttons:
```python
        right.addWidget(QLabel(locale_ru.GUI["td_branding_header"])); right.addWidget(scroll, 2)

        right.addWidget(QLabel(locale_ru.GUI["td_sections_header"]))
```
```python
        secbtns.addWidget(QLabel(locale_ru.GUI["td_intro"]))
        self.f_intro = QLineEdit(); self.f_intro.setPlaceholderText(locale_ru.GUI["td_intro_placeholder"])
```
```python
        save = QPushButton(locale_ru.GUI["td_save"]); save.clicked.connect(self._save)
```

(f) `_pick_logo`:
```python
        p, _ = QFileDialog.getOpenFileName(self, locale_ru.GUI["td_logo_title"], "",
                                           locale_ru.GUI["filter_images"])
```

(g) `_new_blank`:
```python
        name, ok = QInputDialog.getText(self, locale_ru.GUI["td_new_template_title"],
                                        locale_ru.GUI["td_new_template_prompt"],
                                        text=locale_ru.GUI["td_new_template_default"])
```

(h) `_new_from_result`:
```python
            p, _ = QFileDialog.getOpenFileName(self, locale_ru.GUI["td_seed_result_title"], "",
                                               locale_ru.GUI["filter_results"])
            if not p:
                return
            try:
                results = extract_mod.extract(Path(p))
            except Exception as e:
                QMessageBox.critical(self, "femrep",
                                     locale_ru.GUI["td_seed_failed"].format(err=e))
                return
        self._load_into_form(templates_mod.seed_from_results(results, locale_ru.GUI["td_from_result_name"]))
```

(i) `_duplicate` — replace the English `" copy"`:
```python
        tpl = self._collect()
        tpl["name"] = f"{tpl['name']} {locale_ru.GUI['td_copy_suffix']}"
        self._load_into_form(tpl)
```

(j) `_delete`:
```python
        if QMessageBox.question(self, "femrep",
                                locale_ru.GUI["td_delete_confirm"].format(name=repr(item.text()))) == QMessageBox.Yes:
```

(k) `_save`:
```python
        path = self._persist()
        QMessageBox.information(self, "femrep", locale_ru.GUI["td_saved"].format(path=path))
```

(l) `_manage_templates` (in `FemrepWindow`) — replace `QMessageBox.information(self, "femrep", "Open a project first to store templates.")` →
`QMessageBox.information(self, "femrep", locale_ru.GUI["msg_open_project_first"])`.

(m) `_pick_project` (in `FemrepWindow`) — replace `QFileDialog.getExistingDirectory(self, "Open or create a femrep project folder")` →
`QFileDialog.getExistingDirectory(self, locale_ru.GUI["dlg_open_project"])`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/test_gui_russian.py::test_template_dialog_has_no_english -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd /c/Users/3fall/Projects/femrep && PYTHONPATH=src "$PY" -m pytest tests/ -q`
Expected: PASS (no regressions; `test_gui_templates.py` still green — branding_fields keys and `_load_into_form` behavior unchanged).

- [ ] **Step 6: Commit**

```bash
rtk git add src/femrep/gui.py tests/test_gui_russian.py
rtk git commit -m "feat(gui): template editor + dialogs fully Russian (branding labels via locale_ru)"
```

---

## Task 5: README wording + reinstall so the launcher reflects the change

**Files:**
- Modify: `README.md` (the GOST GUI sentence)
- Deployment: editable reinstall into the femrep venv; full suite via the installed package

**Interfaces:** none (docs + deployment).

- [ ] **Step 1: Fix the README sentence**

In `README.md`, under "### Russian GOST report (ГОСТ 7.32-2017)", replace:

```
Select **Профиль → ГОСТ 7.32-2017** in the GUI, or:
```

with:

```
Select **Шаблон → ГОСТ 7.32-2017 (DOCX, рус.)** in the GUI (no project needed), or:
```

- [ ] **Step 2: Editable reinstall so `femrep-gui` uses the source**

The launcher resolves to the installed copy in the venv (currently a non-editable
`0.5.6`). Reinstall editable so the GUI reflects the new code:

Run: `"$PY" -m pip install -e "/c/Users/3fall/Projects/femrep[gui]" -q`
Expected: completes; `"$PY" -c "import femrep, importlib.util as u; print(u.find_spec('femrep').origin)"` now points under `Projects/femrep/src/femrep/__init__.py`.

- [ ] **Step 3: Run the full suite against the installed (editable) package**

Run: `cd /c/Users/3fall/Projects/femrep && "$PY" -m pytest tests/ -q`
Expected: PASS (no `PYTHONPATH` needed now — `femrep` resolves to source).

- [ ] **Step 4: Smoke-test the GOST path headlessly**

Run:
```bash
cd /c/Users/3fall/Projects/femrep && QT_QPA_PLATFORM=offscreen "$PY" - <<'PY'
from femrep import gui, locale_ru as L
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
win = gui.FemrepWindow()
labels = [win.cmb_template.itemText(i) for i in range(win.cmb_template.count())]
assert L.BUILTIN_GOST_LABEL in labels, labels
print("OK dropdown:", labels)
PY
```
Expected: prints `OK dropdown: ['По умолчанию', 'ГОСТ 7.32-2017 (DOCX, рус.)']`.

- [ ] **Step 5: Commit**

```bash
rtk git add README.md
rtk git commit -m "docs: GUI ГОСТ selection is now Шаблон → ГОСТ 7.32-2017 (no project needed)"
```

---

## Self-Review

**1. Spec coverage**
- Part 1 (built-in ГОСТ dropdown, no project, forces Russian .docx, kind-payload identity) → Task 2. ✓
- Part 2 (all GUI strings Russian, centralized in locale_ru, zero-English test, branding-label map) → Tasks 1, 3, 4. ✓
- Non-goals respected: renderer/CLI/schema/English-path untouched (Tasks touch only `gui.py`, `locale_ru.py`, tests, README). ✓
- Testing section (built-in routing, built-in default, GUI zero-English strings + widgets, suite green) → Tasks 1–4. ✓
- Deployment note (editable reinstall so `femrep-gui` reflects source) → Task 5. ✓
- ГрОб rail-motto parked (out of scope) — not implemented. ✓ (the `rail_hint` string is a neutral Russian femis line, no lyrics.)

**2. Placeholder scan** — no TBD/TODO/"handle edge cases"/"similar to Task N"; every code step shows full code. ✓

**3. Type consistency** — `_current_template_ref()` returns `tuple[str,str]` and is consumed by `_selected_cfg`/`_enabled_sections` consistently; dropdown item data is always a `(kind, ref)` tuple; `locale_ru.GUI[...]` keys used in `gui.py` all exist in the Task 1 dict; `branding_label` used in Task 4 is defined in Task 1; `_card` signature change (drop English param) is applied at all four call sites in Task 3. ✓
