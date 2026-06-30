"""Tests for the report-template model & per-project I/O (pure stdlib, no Ansys)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_default_template_has_all_sections_enabled_in_canonical_order():
    from femrep import templates
    tpl = templates.default_template("Default")
    assert tpl["name"] == "Default"
    assert tpl["femrep_template_version"] == 1
    keys = [s["key"] for s in tpl["sections"]]
    assert keys == [k for k, _ in templates.SECTIONS]
    assert all(s["enabled"] for s in tpl["sections"])
    # branding carries every config.yaml key
    for k in ("title", "company", "customer", "color_primary", "font", "page_size"):
        assert k in tpl["branding"]


def test_validate_repairs_partial_template():
    from femrep import templates
    raw = {
        "name": "Partial",
        "branding": {"company": "Acme"},          # missing most keys
        "sections": [
            {"key": "results", "enabled": True},   # out of order, missing intro
            {"key": "bogus", "enabled": True},     # unknown -> dropped
        ],
    }
    tpl = templates.validate(raw)
    assert tpl["femrep_template_version"] == 1
    assert tpl["branding"]["company"] == "Acme"
    assert "color_primary" in tpl["branding"]       # filled from default
    keys = [s["key"] for s in tpl["sections"]]
    assert "bogus" not in keys                      # unknown dropped
    assert set(keys) == templates.SECTION_KEYS      # catalog completed
    # the explicitly-listed section keeps its order at the front; the rest appended
    assert keys[0] == "results"
    assert all("intro" in s for s in tpl["sections"])
    # appended (previously absent) sections default to disabled
    model = next(s for s in tpl["sections"] if s["key"] == "model")
    assert model["enabled"] is False


def test_to_config_flattens_branding_and_enabled_sections():
    from femrep import templates
    tpl = templates.default_template("X")
    tpl["branding"]["company"] = "Acme"
    tpl["sections"] = [
        {"key": "results", "enabled": True, "intro": "see fig."},
        {"key": "model", "enabled": False, "intro": ""},
        {"key": "summary", "enabled": True, "intro": ""},
    ]
    cfg = templates.to_config(templates.validate(tpl))
    assert cfg["company"] == "Acme"
    assert cfg["template"] == "X"
    enabled = [(s["key"], s["title"], s["intro"]) for s in cfg["sections"]]
    # only enabled, in given order; titles resolved from registry
    assert enabled[0] == ("results", "Results", "see fig.")
    assert ("model", "Model", "") not in [(s["key"], s["title"], s["intro"]) for s in cfg["sections"]]
    assert any(k == "summary" for k, *_ in enabled)


def test_seed_from_results_enables_only_data_bearing_sections():
    from femrep import templates
    base = {
        "primary_qoi": {"name": "temperature", "units": "K"},
        "mesh": {"nodes": 10, "elements": 4},
    }
    # no composite, no gci -> those two disabled, others enabled
    tpl = templates.seed_from_results(base, "Seeded")
    state = {s["key"]: s["enabled"] for s in tpl["sections"]}
    assert state["composites"] is False
    assert state["gci"] is False
    assert state["summary"] is True and state["results"] is True

    rich = dict(base, composite={"layup": "[0/90/0]"}, gci={"gci_fine": 0.1})
    tpl2 = templates.seed_from_results(rich, "Seeded2")
    state2 = {s["key"]: s["enabled"] for s in tpl2["sections"]}
    assert state2["composites"] is True
    assert state2["gci"] is True


def test_per_project_save_list_load_delete(tmp_path):
    from femrep import templates
    project = tmp_path / "proj"
    (project / "templates").mkdir(parents=True)

    tpl = templates.default_template("My Standard")
    tpl["branding"]["company"] = "Acme Co"
    path = templates.save_template(project, tpl)
    assert path.exists() and path.suffix == ".json"

    assert "My Standard" in templates.list_templates(project)
    loaded = templates.load_template(project, "My Standard")
    assert loaded["branding"]["company"] == "Acme Co"
    assert [s["key"] for s in loaded["sections"]] == [k for k, _ in templates.SECTIONS]

    templates.delete_template(project, "My Standard")
    assert "My Standard" not in templates.list_templates(project)


def test_load_path_rejects_non_json(tmp_path):
    from femrep import templates
    bad = tmp_path / "notatemplate.json"
    bad.write_text("this is not json", encoding="utf-8")
    try:
        templates.load_path(bad)
    except ValueError as exc:
        assert "template" in str(exc).lower() or "json" in str(exc).lower()
    else:
        raise AssertionError("a non-JSON file must raise a clear ValueError")
