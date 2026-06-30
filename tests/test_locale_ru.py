"""Tests for the Russian string layer (locale_ru)."""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Latin tokens allowed to survive in an otherwise-Russian document: proper nouns,
# established abbreviations, unit symbols are checked separately at the doc level.
ALLOWED_LATIN = {"ansys", "nastran", "femis", "gci"}


def latin_words(text: str) -> set[str]:
    """English-ish Latin word tokens (>=3 letters) minus the allow-list."""
    return {w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)} - ALLOWED_LATIN


def _results():
    return {"primary_qoi": {"name": "temperature", "units": "K", "min": 300.0, "max": 305.0}}


def _manifest():
    return {"analysis_type": "thermal", "solver": "Nastran", "solver_version": "0.1"}


def test_section_titles_cover_registry_and_are_cyrillic():
    from femrep import templates, locale_ru
    for key, _ in templates.SECTIONS:
        assert key in locale_ru.SECTION_TITLES_RU, f"missing RU title for {key}"
        assert re.search(r"[А-Яа-я]", locale_ru.SECTION_TITLES_RU[key])


def test_verdict_and_status_maps():
    from femrep import locale_ru
    assert locale_ru.verdict_ru("pass") == "соответствует"
    assert locale_ru.verdict_ru("fail") == "не соответствует"
    assert locale_ru.verdict_ru("not_done") == "не выполнено"
    assert locale_ru.status_ru("complete") == "полное"
    assert locale_ru.analysis_ru("steady_thermal (.f06)") == "тепловой"
    assert locale_ru.qoi_ru("von_mises_stress").startswith("эквивалентные")
    assert locale_ru.units_ru("K") == "К"


def test_keywords_uppercase_and_count():
    from femrep import locale_ru
    kw = locale_ru.keywords(_results(), _manifest())
    assert 5 <= len(kw) <= 15
    assert all(w == w.upper() for w in kw)


def test_generated_prose_is_russian_no_english_labels():
    from femrep import locale_ru
    r, m = _results(), _manifest()
    checks = {"readiness": {"status": "issue_with_limitations"},
              "gates": [{"gate": "units", "verdict": "pass"}]}
    referat = locale_ru.referat_text(r, m)
    vved = locale_ru.vvedenie_text(r, m)
    zakl = locale_ru.zaklyuchenie_text(r, checks)
    for text in (referat, vved, zakl):
        assert re.search(r"[А-Яа-я]", text)
        assert latin_words(text) == set(), f"unexpected English in: {sorted(latin_words(text))}"


def test_gate_and_readiness_notes_russian():
    from femrep import locale_ru
    note = locale_ru.gate_note_ru({"gate": "mesh_independence_GCI", "verdict": "pass"},
                                  {"gci_fine_pct": 1.2, "convergence_ratio_R": 0.5, "observed_order_p": 2.0})
    assert "GCI" in note and re.search(r"[А-Яа-я]", note)
    rn = locale_ru.readiness_note_ru({"key": "deck_hash", "status": "missing"})
    assert latin_words(rn) == set()
