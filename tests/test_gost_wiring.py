"""End-to-end: profile=gost_ru routes run_report to the ГОСТ Russian DOCX renderer,
forcing .docx, and the template carries the profile + GOST title-page fields."""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

CONFIG = Path(__file__).resolve().parents[1] / "src" / "femrep" / "config.yaml"


def _tiny_f06(tmp_path: Path) -> Path:
    f06 = tmp_path / "000.f06"
    f06.write_text("SOL 153\nTIME = 1.0\n T E M P E R A T U R E   V E C T O R\n"
                   "      1 S  300.0 301.0 302.0\n", encoding="ascii")
    return f06


def test_template_carries_profile_and_gost_fields():
    from femrep import templates
    tpl = templates.validate({"name": "ГОСТ", "profile": "gost_ru",
                              "branding": {"udc": "536.2", "city": "Москва"}})
    assert tpl["profile"] == "gost_ru"
    for field in ("ministry", "udc", "city", "year", "report_type",
                  "head_org_title", "head_work_title"):
        assert field in tpl["branding"]
    cfg = templates.to_config(tpl)
    assert cfg["profile"] == "gost_ru" and cfg["udc"] == "536.2"
    # bad profile coerced to default
    assert templates.validate({"profile": "bogus"})["profile"] == "default"


def test_run_report_gost_profile_forces_russian_docx(tmp_path):
    from docx import Document
    from femrep import workflow

    out = tmp_path / "report.pdf"          # ask for .pdf — GOST must force .docx
    workflow.run_report(_tiny_f06(tmp_path), out=out, config_path=CONFIG,
                        profile="gost_ru", no_figures=True)
    docx = out.with_suffix(".docx")
    assert docx.exists(), "GOST profile must emit a .docx"
    assert not out.exists(), "GOST profile must not emit the .pdf"

    text = "\n".join(p.text for p in Document(str(docx)).paragraphs)
    assert "ОТЧЁТ О НАУЧНО-ИССЛЕДОВАТЕЛЬСКОЙ РАБОТЕ" in text
    assert "РЕФЕРАТ" in text and "ЗАКЛЮЧЕНИЕ" in text
    assert re.search(r"[А-Яа-я]", text)
