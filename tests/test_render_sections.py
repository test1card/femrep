"""Renderer section-registry tests: a template's section selection/order/numbering
is honored, and the default (no template) output is unchanged. Inspects the
flowable story directly — no PDF file or Ansys needed."""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _fixture():
    from femrep import templates
    results = {
        "result_file": "x.f06",
        "result_sha256": "abc123",
        "primary_qoi": {"name": "temperature", "units": "K", "min": 300.0, "max": 305.0,
                        "hot_node": 1, "hot_node_xyz_mm": [0, 0, 0],
                        "cold_node": 2, "cold_node_xyz_mm": [1, 1, 1]},
        "qoi_catalog": [{"name": "temperature"}],
        "mesh": {"nodes": 10, "elements": 4, "element_types": {"tet": 4}},
        "convergence": {"converged": True, "substeps": 1, "note": "ok"},
    }
    manifest = {"analysis_type": "thermal", "units": "SI", "solver": "nastran",
                "solver_version": "x", "platform": "p", "command_line": "c",
                "deck_path": None, "superseded_by": None}
    checks = {"claim": "claim text", "gates": [{"gate": "units", "verdict": "pass", "note": "n"}],
              "gci": None, "readiness": None}
    cfg = templates.to_config(templates.default_template("Default"))
    return results, manifest, checks, cfg


def _headings(story):
    from reportlab.platypus import Paragraph
    out = []
    for f in story:
        if isinstance(f, Paragraph) and re.match(r"^\d+\.\s", getattr(f, "text", "")):
            out.append(f.text)
    return out


def _texts(story):
    from reportlab.platypus import Paragraph
    return [f.text for f in story if isinstance(f, Paragraph)]


def test_default_renders_all_nine_sections_in_canonical_order():
    from femrep import report_pdf
    results, manifest, checks, cfg = _fixture()
    st = report_pdf._styles(cfg)
    story = report_pdf.build_story(results, manifest, checks, cfg, {}, {"generated": "x"}, st)
    assert _headings(story) == [
        "1. Summary", "2. Model", "3. Meshing", "4. Composites / CFRP",
        "5. Mechanical / solve", "6. Results", "7. Mesh independence (GCI)",
        "8. Governance (femis)", "9. Run manifest (provenance)",
    ]


def test_template_subset_and_reorder_with_dynamic_numbering():
    from femrep import report_pdf, templates
    results, manifest, checks, cfg = _fixture()
    tpl = templates.default_template("Custom")
    tpl["sections"] = [
        {"key": "results", "enabled": True, "intro": "Custom intro line."},
        {"key": "summary", "enabled": True, "intro": ""},
    ]
    cfg = templates.to_config(tpl)
    st = report_pdf._styles(cfg)
    story = report_pdf.build_story(results, manifest, checks, cfg, {}, {"generated": "x"}, st)

    assert _headings(story) == ["1. Results", "2. Summary"]
    # disabled sections absent
    joined = " ".join(_headings(story))
    assert "Model" not in joined and "Governance" not in joined
    # per-section intro text injected
    assert "Custom intro line." in _texts(story)


def test_empty_section_list_falls_back_to_note_not_crash():
    from femrep import report_pdf, templates
    results, manifest, checks, cfg = _fixture()
    tpl = templates.default_template("Empty")
    for s in tpl["sections"]:
        s["enabled"] = False
    cfg = templates.to_config(tpl)
    st = report_pdf._styles(cfg)
    story = report_pdf.build_story(results, manifest, checks, cfg, {}, {"generated": "x"}, st)
    assert _headings(story) == []
    assert any("No report sections are enabled" in t for t in _texts(story))


def _docx_headings(doc):
    return [p.text for p in doc.paragraphs if re.match(r"^\d+\.\s", p.text)]


def test_docx_default_renders_all_nine_sections_in_canonical_order():
    from femrep import report_docx
    results, manifest, checks, cfg = _fixture()
    doc = report_docx.build_doc(results, manifest, checks, cfg, {}, {"generated": "x"})
    assert _docx_headings(doc) == [
        "1. Summary", "2. Model", "3. Meshing", "4. Composites / CFRP",
        "5. Mechanical / solve", "6. Results", "7. Mesh independence (GCI)",
        "8. Governance (femis)", "9. Run manifest (provenance)",
    ]


def test_docx_template_subset_reorder_intro_and_empty():
    from femrep import report_docx, templates
    results, manifest, checks, cfg = _fixture()
    tpl = templates.default_template("Custom")
    tpl["sections"] = [
        {"key": "governance", "enabled": True, "intro": "Gov intro."},
        {"key": "summary", "enabled": True, "intro": ""},
    ]
    doc = report_docx.build_doc(results, manifest, checks, templates.to_config(tpl), {}, {"generated": "x"})
    assert _docx_headings(doc) == ["1. Governance (femis)", "2. Summary"]
    assert any(p.text == "Gov intro." for p in doc.paragraphs)

    empty = templates.default_template("Empty")
    for s in empty["sections"]:
        s["enabled"] = False
    doc2 = report_docx.build_doc(results, manifest, checks, templates.to_config(empty), {}, {"generated": "x"})
    assert _docx_headings(doc2) == []
    assert any("No report sections are enabled" in p.text for p in doc2.paragraphs)
