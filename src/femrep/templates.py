"""femrep.templates — report-template model, validation, and per-project I/O.

A template captures a report's branding / title block plus its section layout
(which sections appear, in what order, with optional per-section intro text). It
is the single source of truth for the section catalog shared by both renderers.

Pure stdlib (json + pathlib): a template is a plain dict persisted as JSON at
``<project>/templates/<slug>.json``. ``to_config`` flattens a template into the
flat ``cfg`` dict the PDF/DOCX renderers already consume.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TEMPLATE_VERSION = 1

# Canonical section order + default title. The cover band / title block is always
# rendered from branding and is intentionally NOT in this list.
SECTIONS: list[tuple[str, str]] = [
    ("summary", "Summary"),
    ("model", "Model"),
    ("meshing", "Meshing"),
    ("composites", "Composites / CFRP"),
    ("solve", "Mechanical / solve"),
    ("results", "Results"),
    ("gci", "Mesh independence (GCI)"),
    ("governance", "Governance (femis)"),
    ("manifest", "Run manifest (provenance)"),
]
SECTION_KEYS = {k for k, _ in SECTIONS}
SECTION_TITLES = dict(SECTIONS)

# Neutral branding defaults — mirrors src/femrep/config.yaml so a template and the
# bundled config stay in lockstep.
DEFAULT_BRANDING: dict = {
    "title": "FEM Analysis Report",
    "author": "Engineer",
    "company": "",
    "project": "",
    "customer": "",
    "document_number": "",
    "revision": "A",
    "prepared_by": "",
    "checked_by": "",
    "approved_by": "",
    "logo": None,
    "color_primary": "#1f3a5f",
    "color_accent": "#0b7285",
    "color_warn": "#c92a2a",
    "color_ok": "#2b8a3e",
    "color_muted": "#868e96",
    "font": "Helvetica",
    "page_size": "A4",
}


def default_template(name: str = "Default") -> dict:
    """A template with neutral branding and every section enabled in order."""
    return {
        "femrep_template_version": TEMPLATE_VERSION,
        "name": name,
        "branding": dict(DEFAULT_BRANDING),
        "sections": [{"key": k, "enabled": True, "intro": ""} for k, _ in SECTIONS],
    }


def validate(tpl: dict) -> dict:
    """Coerce/repair a (possibly hand-edited or partial) template into a complete,
    well-formed one. Never raises on a dict input — a non-developer must not see a
    stack trace from a shared file. Fills missing branding, drops unknown section
    keys, and appends any missing known sections (disabled) so the catalog is
    always complete and editable."""
    if not isinstance(tpl, dict):
        raise ValueError("template must be a JSON object")
    out: dict = {
        "femrep_template_version": TEMPLATE_VERSION,
        "name": str(tpl.get("name") or "Untitled"),
        "branding": dict(DEFAULT_BRANDING),
    }
    branding = tpl.get("branding")
    if isinstance(branding, dict):
        for k in DEFAULT_BRANDING:
            if k in branding:
                out["branding"][k] = branding[k]

    seen: set[str] = set()
    sections: list[dict] = []
    for s in tpl.get("sections") or []:
        if not isinstance(s, dict):
            continue
        key = s.get("key")
        if key not in SECTION_KEYS or key in seen:
            continue          # drop unknown or duplicate keys
        seen.add(key)
        sections.append({
            "key": key,
            "enabled": bool(s.get("enabled", True)),
            "intro": str(s.get("intro") or ""),
        })
    # append any known section not listed, disabled, in canonical order
    for k, _ in SECTIONS:
        if k not in seen:
            sections.append({"key": k, "enabled": False, "intro": ""})
    out["sections"] = sections
    return out


def to_config(tpl: dict) -> dict:
    """Flatten a (validated) template into the flat cfg dict the renderers consume:
    branding keys at top level + cfg['sections'] = ordered ENABLED sections with
    titles resolved from the registry + cfg['template'] name."""
    tpl = validate(tpl)
    cfg = dict(tpl["branding"])
    cfg["template"] = tpl["name"]
    cfg["sections"] = [
        {"key": s["key"], "title": SECTION_TITLES[s["key"]], "intro": s.get("intro", "")}
        for s in tpl["sections"] if s["enabled"]
    ]
    return cfg


def _has(results: dict, *keys: str) -> bool:
    return any(results.get(k) for k in keys)


def seed_from_results(results: dict, name: str = "From result") -> dict:
    """Auto-generate a starter template from an extracted results dict: enable only
    the data-bearing sections (composites if a layup/composite block is present;
    GCI if a study is present), everything else on. The user then edits it."""
    tpl = default_template(name)
    has_composite = _has(results, "composite", "composites", "layup")
    has_gci = _has(results, "gci", "gci_runs", "mesh_independence")
    for s in tpl["sections"]:
        if s["key"] == "composites":
            s["enabled"] = bool(has_composite)
        elif s["key"] == "gci":
            s["enabled"] = bool(has_gci)
    qoi = (results.get("primary_qoi") or {}).get("name")
    if qoi:
        tpl["branding"]["title"] = f"FEM Analysis Report — {qoi}"
    return tpl


# --- persistence (per-project) ------------------------------------------------

def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip().lower()).strip("_")
    return s or "template"


def templates_dir(project: Path) -> Path:
    return Path(project) / "templates"


def list_templates(project: Path) -> list[str]:
    """Names of saved templates in a project (sorted), read from each file's name
    field so display names survive slugging."""
    d = templates_dir(project)
    if not d.exists():
        return []
    names = []
    for p in sorted(d.glob("*.json")):
        try:
            names.append(json.loads(p.read_text(encoding="utf-8")).get("name") or p.stem)
        except (ValueError, OSError):
            continue
    return names


def _find_file(project: Path, name: str) -> Path | None:
    d = templates_dir(project)
    target = d / f"{_slug(name)}.json"
    if target.exists():
        return target
    for p in d.glob("*.json"):          # fall back to a name-field match
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("name") == name:
                return p
        except (ValueError, OSError):
            continue
    return None


def save_template(project: Path, tpl: dict) -> Path:
    tpl = validate(tpl)
    d = templates_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_slug(tpl['name'])}.json"
    path.write_text(json.dumps(tpl, indent=2), encoding="utf-8")
    return path


def load_template(project: Path, name: str) -> dict:
    path = _find_file(project, name)
    if path is None:
        raise FileNotFoundError(f"no template named {name!r} in {templates_dir(project)}")
    return load_path(path)


def delete_template(project: Path, name: str) -> None:
    path = _find_file(project, name)
    if path is not None:
        path.unlink()


# --- path-based I/O (GUI file dialogs / sharing) ------------------------------

def load_path(path: Path) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path} is not a valid femrep template (invalid JSON): {exc}") from exc
    return validate(raw)


def save_path(path: Path, tpl: dict) -> Path:
    path = Path(path)
    path.write_text(json.dumps(validate(tpl), indent=2), encoding="utf-8")
    return path
