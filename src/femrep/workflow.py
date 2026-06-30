"""Product workflows for femrep.

Small stdlib-first helpers for the product shell around the core pipeline:
single-run reports, report packages, HTML review, project folders, batch runs,
and GCI study generation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from . import extract, govern


HERE = Path(__file__).parent


TEMPLATES = {
    "client": {"title": "FEM Analysis Report"},
    "internal": {"title": "FEM Evidence Report"},
    "executive": {"title": "FEM Executive Summary"},
    "verification": {"title": "FEM Verification Appendix"},
}


def load_config(path: Path, template: str | None = None,
                template_file: Path | None = None, profile: str | None = None) -> dict:
    """Flat key:value config reader plus template overlays. A built-in named
    `template` overlays first; a saved `template_file` (custom GUI template) is
    overlaid last and wins — bringing its branding and section layout."""
    cfg = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        in_q = False
        for i, ch in enumerate(line):
            if ch == '"':
                in_q = not in_q
            elif ch == ":" and not in_q:
                k, v = line[:i].strip(), line[i + 1:]
                break
        else:
            continue
        v = v.strip()
        if v.startswith('"'):
            end = v.find('"', 1)
            v = v[1:end] if end != -1 else v.strip('"')
        else:
            v = v.split("#", 1)[0].strip()
        cfg[k] = None if v.lower() == "null" else v
    if template:
        cfg.update(TEMPLATES.get(template, {}))
        cfg["template"] = template
    if template_file:
        from . import templates as _templates
        cfg.update(_templates.to_config(_templates.load_path(Path(template_file))))
    if profile:
        cfg["profile"] = profile
    return cfg


def resolve_inputs(result_file: Path, deck: Path | None) -> tuple[Path, Path | None]:
    """Detect obvious companions without owning a database."""
    if result_file.suffix.lower() == ".op2":
        f06 = result_file.with_suffix(".f06")
        if f06.exists():
            print(f"[femrep] .op2 adapter pending; using companion .f06: {f06}", flush=True)
            result_file = f06
    if deck is None:
        for suffix in (".dat", ".bdf", ".inp", ".cdb"):
            cand = result_file.with_suffix(suffix)
            if cand.exists():
                print(f"[femrep] detected deck companion: {cand}", flush=True)
                deck = cand
                break
    return result_file, deck


def _detect_log(result_file: Path) -> Path | None:
    for suffix in (".mntr", ".out", ".log"):
        cand = result_file.with_suffix(suffix)
        if cand.exists():
            print(f"[femrep] detected solve log companion: {cand}", flush=True)
            return cand
    return None


def _detect_gci(result_file: Path) -> Path | None:
    for cand in (result_file.with_name("gci_runs.json"), result_file.with_suffix(".gci.json")):
        if cand.exists():
            print(f"[femrep] detected GCI companion: {cand}", flush=True)
            return cand
    return None


def run_report(result_file: Path, *, out: Path, log: Path | None = None,
               mode: str = "ENGINEERING", gci_path: Path | None = None,
               deck: Path | None = None, config_path: Path | None = None,
               template: str | None = None, template_file: Path | None = None,
               profile: str | None = None, no_figures: bool = False,
               make_html: bool = False, make_package: bool = False,
               project: Path | None = None, run_name: str | None = None,
               supersedes: str | None = None, qoi: str | None = None) -> dict:
    """Run extract -> govern -> figures -> render, returning artifact paths."""
    result_file, deck = resolve_inputs(result_file, deck)
    if not result_file.exists():
        raise FileNotFoundError(result_file)
    log = log or _detect_log(result_file)
    gci_path = gci_path or _detect_gci(result_file)

    config_path = config_path or HERE / "config.yaml"
    project_root = None
    if project:
        run_name = run_name or f"{result_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_root = project
        out = project / "runs" / run_name / out.name
    out_dir = out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    if project_root:
        _copy_inputs(out_dir / "inputs", [result_file, deck, log, gci_path])

    print(f"[femrep] extracting {result_file} ...", flush=True)
    results = extract.extract(result_file, log, qoi)
    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"[femrep] applying femis governance (mode={mode}) ...", flush=True)
    gci = govern.run_gci(json.loads(gci_path.read_text(encoding="utf-8"))) if gci_path else None
    manifest = govern.build_manifest(results, mode, deck_path=deck, superseded_by=supersedes)
    gates = govern.evaluate_gates(results, mode, manifest, gci)
    claim = govern.phrase_claim(mode, results, gci, gates)
    readiness = govern.evaluate_readiness(results, manifest, gates, gci)
    checks = {"mode": mode, "claim": claim, "gates": gates,
              "gci": gci, "readiness": readiness}
    manifest_path = out_dir / "manifest.json"
    checks_path = out_dir / "checks.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")

    figure_paths: dict = {}
    if not no_figures:
        try:
            from . import figures as fig_mod
            figure_paths = fig_mod.generate(results, gci, out_dir)
            print(f"[femrep] figures: {list(figure_paths)}", flush=True)
        except Exception as e:
            print(f"[femrep] figures skipped: {e}", flush=True)

    cfg = load_config(config_path, template, template_file, profile)
    meta = {"generated": datetime.now().isoformat(timespec="seconds"),
            "config_path": str(config_path)}
    if cfg.get("profile") == "gost_ru":
        # ГОСТ 7.32-2017: всегда .docx, на русском языке
        from . import report_gost_docx
        if out.suffix.lower() != ".docx":
            out = out.with_suffix(".docx")
            print(f"[femrep] профиль ГОСТ 7.32 — вывод в .docx: {out}", flush=True)
        report_gost_docx.render(results, manifest, checks, cfg, figure_paths, meta, out)
    elif out.suffix.lower() == ".docx":
        from . import report_docx
        report_docx.render(results, manifest, checks, cfg, figure_paths, meta, out)
    else:
        from . import report_pdf
        report_pdf.render(results, manifest, checks, cfg, figure_paths, meta, out)
    print(f"[femrep] report -> {out}", flush=True)

    html_path = render_html_review(results, manifest, checks, figure_paths, out_dir) if make_html else None
    package_path = create_package(out_dir, out) if make_package else None
    artifacts = {
        "results": results_path,
        "manifest": manifest_path,
        "checks": checks_path,
        "report": out,
        "html": html_path,
        "package": package_path,
        "figures": figure_paths,
    }
    if project_root:
        record_run(project_root, run_name or out_dir.name, artifacts, readiness)
    return artifacts


def _copy_inputs(target: Path, paths: list[Path | None]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path and Path(path).exists():
            shutil.copy2(path, target / Path(path).name)


def record_run(project: Path, run_name: str, artifacts: dict, readiness: dict) -> None:
    project.mkdir(parents=True, exist_ok=True)
    index = project / "runs_index.csv"
    new_file = not index.exists() or index.stat().st_size == 0
    with index.open("a", newline="", encoding="utf-8") as f:
        fieldnames = ["run", "status", "report", "html", "package", "updated_at"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "run": run_name,
            "status": readiness.get("status", "unknown"),
            "report": str(artifacts.get("report") or ""),
            "html": str(artifacts.get("html") or ""),
            "package": str(artifacts.get("package") or ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })


def render_html_review(results: dict, manifest: dict, checks: dict,
                       figures: dict, out_dir: Path) -> Path:
    """Write a self-contained-ish HTML review page.

    If PyVista can export a rotatable scene, link it; otherwise show the static
    figure gallery and the evidence dashboard.
    """
    interactive = None
    try:
        from .figures import interactive_contour_html
        interactive = interactive_contour_html(results, out_dir)
    except Exception:
        interactive = None

    qoi = results["primary_qoi"]
    qoi_catalog = ", ".join(i["name"] for i in results.get("qoi_catalog", [])) or "not available"
    readiness = checks.get("readiness", {})
    fig_html = []
    for key, path in figures.items():
        if path and Path(path).exists():
            fig_html.append(f'<figure><img src="{Path(path).name}" alt="{key}"><figcaption>{key}</figcaption></figure>')
    item_rows = "\n".join(
        f"<tr><td>{i['key']}</td><td>{i['status']}</td><td>{i['note']}</td><td>{i.get('fix','')}</td></tr>"
        for i in readiness.get("items", [])
    )
    transient = results.get("transient")
    transient_rows = ""
    if transient:
        transient_rows = "\n".join(
            f"<tr><td>{t}</td><td>{lo}</td><td>{hi}</td><td>{mean}</td></tr>"
            for t, lo, hi, mean in zip(transient.get("times", []),
                                       transient.get("min", []),
                                       transient.get("max", []),
                                       transient.get("mean", []))
        )
    scene = (f'<p><a class="button" href="{interactive.name}">Open rotatable contour viewer</a></p>'
             if interactive else "<p class='muted'>Rotatable contour unavailable for this result format.</p>")
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>femrep review</title>
<style>
body{{font-family:Arial,sans-serif;margin:24px;color:#1f2933}} .muted{{color:#667085}}
.button{{display:inline-block;background:#1f3a5f;color:white;padding:8px 12px;text-decoration:none}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}td,th{{border:1px solid #d0d5dd;padding:6px;vertical-align:top}}
th{{background:#1f3a5f;color:white}} img{{max-width:100%;border:1px solid #d0d5dd}} figure{{margin:18px 0}}
</style>
<h1>FEM Review</h1>
<p><b>{manifest.get('solver','')}</b> {manifest.get('solver_version','')}</p>
<p><b>QoI:</b> {qoi['name']} = {qoi['min']} .. {qoi['max']} {qoi['units']}</p>
<p><b>QoI catalog:</b> {qoi_catalog}</p>
<p><b>Hot spot:</b> node {qoi.get('hot_node', 0)} at {qoi.get('hot_node_xyz_mm', [])} mm</p>
<p><b>Cold spot:</b> node {qoi.get('cold_node', 0)} at {qoi.get('cold_node_xyz_mm', [])} mm</p>
<p><b>Readiness:</b> {readiness.get('summary','not evaluated')}</p>
{scene}
<h2>Evidence</h2>
<table><tr><th>Evidence</th><th>Status</th><th>Note</th><th>Fix</th></tr>{item_rows}</table>
<h2>Transient History</h2>
{f'<table><tr><th>time</th><th>min</th><th>max</th><th>mean</th></tr>{transient_rows}</table>' if transient else '<p class="muted">No transient sequence detected.</p>'}
<h2>Figures</h2>
{''.join(fig_html) or '<p class="muted">No figures generated.</p>'}
<h2>Claim</h2>
<p>{checks['claim'].replace('**', '')}</p>
</html>"""
    out = out_dir / "review.html"
    out.write_text(html, encoding="utf-8")
    return out


def create_package(out_dir: Path, report_path: Path) -> Path:
    """Zip report artifacts next to the report."""
    package = report_path.with_suffix(".femrep.zip")
    names = ["results.json", "manifest.json", "checks.json", "review.html"]
    packaged: list[Path] = []
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if report_path.exists():
            z.write(report_path, report_path.name)
            packaged.append(report_path)
        for name in names:
            p = out_dir / name
            if p.exists():
                z.write(p, name)
                packaged.append(p)
        for p in out_dir.glob("*.png"):
            z.write(p, p.name)
            packaged.append(p)
        for p in out_dir.glob("*.html"):
            if p.name != "review.html":
                z.write(p, p.name)
                packaged.append(p)
        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": [{"name": p.name, "sha256": _sha256(p)} for p in packaged],
        }
        z.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2))
    return package


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def init_project(root: Path, name: str) -> Path:
    project = root / name
    for sub in ("runs", "reports", "templates", "assets"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    (project / "runs_index.csv").touch(exist_ok=True)
    return project


def run_batch(batch_path: Path) -> list[dict]:
    """Run a JSON batch file: {"runs": [{"result": "...", "out": "..."}]}."""
    spec = json.loads(batch_path.read_text(encoding="utf-8-sig"))
    runs = spec.get("runs", [])
    outputs = []
    for run in runs:
        outputs.append(run_report(
            Path(run["result"]),
            out=Path(run.get("out", Path(run["result"]).with_suffix(".pdf"))),
            log=Path(run["log"]) if run.get("log") else None,
            deck=Path(run["deck"]) if run.get("deck") else None,
            gci_path=Path(run["gci"]) if run.get("gci") else None,
            config_path=Path(run["config"]) if run.get("config") else None,
            template=run.get("template"),
            template_file=Path(run["template_file"]) if run.get("template_file") else None,
            profile=run.get("profile"),
            no_figures=bool(run.get("no_figures", False)),
            make_html=bool(run.get("html", True)),
            make_package=bool(run.get("package", True)),
            supersedes=run.get("supersedes"),
            qoi=run.get("qoi"),
        ))
    return outputs


def build_gci_study(rows: list[dict], out_path: Path, qoi: str = "QoI") -> dict:
    """Write a gci_runs.json from h/f rows."""
    payload = {"qoi": qoi, "grids": [{"h": float(r["h"]), "f": float(r["f"])} for r in rows]}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def build_gci_study_from_csv(csv_path: Path, out_path: Path, qoi: str = "QoI") -> dict:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and "result" in rows[0] and "f" not in rows[0]:
        built = []
        for row in rows:
            result_path = Path(row["result"])
            payload = extract.extract(result_path)
            built.append({"h": row["h"], "f": payload["primary_qoi"]["max"]})
        rows = built
    return build_gci_study(rows, out_path, qoi)
