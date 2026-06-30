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
