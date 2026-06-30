"""Template overlay through workflow.load_config and an end-to-end run_report."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

CONFIG = Path(__file__).resolve().parents[1] / "src" / "femrep" / "config.yaml"


def _tiny_f06(tmp_path: Path) -> Path:
    f06 = tmp_path / "tiny.f06"
    f06.write_text(
        "SOL 153\n"
        "TIME = 1.0\n"
        " T E M P E R A T U R E   V E C T O R\n"
        "      1 S  300.0 301.0 302.0\n",
        encoding="ascii",
    )
    return f06


def test_load_config_overlays_template_file(tmp_path):
    from femrep import workflow, templates
    tpl = templates.default_template("Acme")
    tpl["branding"]["company"] = "Acme Co"
    tpl["sections"] = [
        {"key": "summary", "enabled": True, "intro": ""},
        {"key": "results", "enabled": True, "intro": ""},
    ]
    path = templates.save_path(tmp_path / "acme.json", tpl)

    cfg = workflow.load_config(CONFIG, template_file=path)
    assert cfg["company"] == "Acme Co"
    assert [s["key"] for s in cfg["sections"]] == ["summary", "results"]


def test_run_report_with_template_file_limits_sections(tmp_path):
    from pypdf import PdfReader
    from femrep import workflow, templates

    tpl = templates.default_template("Two")
    tpl["sections"] = [
        {"key": "summary", "enabled": True, "intro": ""},
        {"key": "governance", "enabled": True, "intro": ""},
    ]
    tpl_path = templates.save_path(tmp_path / "two.json", tpl)

    out = tmp_path / "report.pdf"
    workflow.run_report(
        _tiny_f06(tmp_path), out=out, config_path=CONFIG,
        template_file=tpl_path, no_figures=True,
    )
    assert out.exists()
    text = "\n".join(page.extract_text() for page in PdfReader(str(out)).pages)
    assert "1. Summary" in text
    assert "2. Governance" in text
    assert "Meshing" not in text          # disabled section absent
    assert "Run manifest" not in text


def test_default_run_report_keeps_all_sections(tmp_path):
    from pypdf import PdfReader
    from femrep import workflow

    out = tmp_path / "full.pdf"
    workflow.run_report(_tiny_f06(tmp_path), out=out, config_path=CONFIG, no_figures=True)
    text = "\n".join(page.extract_text() for page in PdfReader(str(out)).pages)
    for heading in ("1. Summary", "2. Model", "3. Meshing", "9. Run manifest"):
        assert heading in text
