"""Headless (offscreen Qt) checks for the GUI template editor. Skipped entirely
when PySide6 (the `gui` extra) isn't installed, so the core suite stays light."""
from __future__ import annotations
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_save_load_reorder_and_intro(app, tmp_path):
    from femrep import gui, templates
    project = tmp_path / "proj"
    templates.templates_dir(project).mkdir(parents=True)

    dlg = gui.TemplateDialog(project)
    dlg._load_into_form(templates.default_template("Acme Std"))
    dlg.brand_fields["company"].setText("Acme Co")

    # reorder: move the first section (summary) down one
    dlg.lst_sec.setCurrentRow(0)
    first_key = dlg.lst_sec.item(0).data(Qt.UserRole)
    dlg._move_section(1)
    assert dlg.lst_sec.item(1).data(Qt.UserRole) == first_key

    # disable a section + set an intro on another
    dlg.lst_sec.item(0).setCheckState(Qt.Unchecked)
    dlg.lst_sec.setCurrentRow(2)
    dlg._on_intro_edit("Lead text.")

    collected = templates.validate(dlg._collect())
    assert collected["branding"]["company"] == "Acme Co"
    third_key = dlg.lst_sec.item(2).data(Qt.UserRole)
    intro_section = next(s for s in collected["sections"] if s["key"] == third_key)
    assert intro_section["intro"] == "Lead text."

    dlg._persist()
    assert dlg.saved_name == "Acme Std"
    assert "Acme Std" in templates.list_templates(project)
    reloaded = templates.load_template(project, "Acme Std")
    assert reloaded["branding"]["company"] == "Acme Co"


def test_window_selected_cfg_overlays_project_template(app, tmp_path):
    from femrep import gui, templates
    win = gui.FemrepWindow()
    # no project => base config, no section override
    base = win._selected_cfg()
    assert "sections" not in base

    project = tmp_path / "proj"
    templates.templates_dir(project).mkdir(parents=True)
    tpl = templates.default_template("Two")
    tpl["sections"] = [{"key": "summary", "enabled": True, "intro": ""},
                       {"key": "results", "enabled": True, "intro": ""}]
    templates.save_template(project, tpl)

    win.project = project
    win._refresh_templates(select="Two")
    cfg = win._selected_cfg()
    assert [s["key"] for s in cfg["sections"]] == ["summary", "results"]


def test_dialog_profile_roundtrip(app, tmp_path):
    from femrep import gui, templates
    project = tmp_path / "proj"
    templates.templates_dir(project).mkdir(parents=True)
    dlg = gui.TemplateDialog(project)
    tpl = templates.default_template("ГОСТ-шаблон")
    tpl["profile"] = "gost_ru"
    dlg._load_into_form(tpl)
    assert dlg._collect()["profile"] == "gost_ru"


def test_render_to_routes_gost_profile_to_russian_docx(app, tmp_path):
    from docx import Document
    from femrep import gui, templates
    win = gui.FemrepWindow()
    win.last_payload = {
        "results": {"result_file": "000.f06", "result_sha256": "a",
                    "primary_qoi": {"name": "temperature", "units": "K", "min": 300.0,
                                    "max": 305.0, "hot_node": 1, "cold_node": 2},
                    "qoi_catalog": [{"name": "temperature"}],
                    "mesh": {"nodes": 10, "elements": 4, "element_types": {"tet": 4}},
                    "convergence": {"converged": True, "substeps": 1, "note": "ок"}},
        "manifest": {"analysis_type": "thermal", "units": "SI", "solver": "Nastran",
                     "solver_version": "0.1", "deck_path": None},
        "checks": {"claim": "", "gci": None,
                   "gates": [{"gate": "units", "verdict": "pass", "note": ""}],
                   "readiness": {"status": "issue_with_limitations", "summary": "", "items": []}},
        "figures": {},
    }
    cfg = templates.to_config(dict(templates.default_template("g"), profile="gost_ru"))
    out = win._render_to(tmp_path / "r.pdf", cfg)   # ask .pdf — must become .docx
    assert out.suffix == ".docx" and out.exists()
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "РЕФЕРАТ" in text
