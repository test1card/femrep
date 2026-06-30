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
           "pdf", "docx", "html", "sha"}


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


def test_template_dialog_has_no_english(app, tmp_path):
    from femrep import gui, templates
    project = tmp_path / "proj"
    templates.templates_dir(project).mkdir(parents=True)
    dlg = gui.TemplateDialog(project)
    dlg._load_into_form(templates.default_template("Шаблон"))
    leaked = [w for t in _widget_texts(dlg) for w in latin_leaks(t)]
    from PySide6.QtWidgets import QFormLayout
    for form in dlg.findChildren(QFormLayout):
        for r in range(form.rowCount()):
            item = form.itemAt(r, QFormLayout.LabelRole)
            if item and item.widget() is not None:
                leaked += latin_leaks(item.widget().text())
    assert sorted(set(leaked)) == [], f"English leaked into TemplateDialog: {sorted(set(leaked))}"
