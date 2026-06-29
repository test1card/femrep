"""femrep.cli - product entrypoints.

Normal use:
    femrep result.f06 --out report.pdf --html --package

Product helpers:
    femrep doctor
    femrep init PROJECT
    femrep batch runs.json
    femrep gci grids.csv --out gci_runs.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from . import govern, workflow


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"doctor", "init", "batch", "gci"}:
        cmd = sys.argv[1]
        if cmd == "doctor":
            return doctor()
        if cmd == "init":
            return _cmd_init(sys.argv[2:])
        if cmd == "batch":
            return _cmd_batch(sys.argv[2:])
        if cmd == "gci":
            return _cmd_gci(sys.argv[2:])

    ap = argparse.ArgumentParser(
        prog="femrep",
        description="femis-governed FEM report generator.")
    ap.add_argument("result_file", type=Path, help="result file (.rst/.rth/.f06/.op2)")
    ap.add_argument("--log", type=Path, default=None, help="solve .out/.mntr log")
    ap.add_argument("--mode", choices=govern.MODES, default="ENGINEERING",
                    help=argparse.SUPPRESS)
    ap.add_argument("--gci", type=Path, default=None, help="gci_runs.json for mesh study")
    ap.add_argument("--qoi", default=None,
                    help="preferred primary QoI when supported")
    ap.add_argument("--deck", type=Path, default=None, help="input deck path")
    ap.add_argument("--out", type=Path, default=Path("femrep_report.pdf"),
                    help="output path; extension decides pdf/docx")
    ap.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml")
    ap.add_argument("--template", choices=sorted(workflow.TEMPLATES), default=None)
    ap.add_argument("--project", type=Path, default=None,
                    help="project folder created by femrep init")
    ap.add_argument("--run-name", default=None,
                    help="run folder name when --project is used")
    ap.add_argument("--supersedes", default=None,
                    help="report/run identifier superseded by this report")
    ap.add_argument("--html", action="store_true", help="write review.html beside the report")
    ap.add_argument("--package", action="store_true", help="write .femrep.zip package")
    ap.add_argument("--no-figures", action="store_true", help="skip figure generation")
    args = ap.parse_args()

    try:
        workflow.run_report(
            args.result_file,
            out=args.out,
            log=args.log,
            mode=args.mode,
            gci_path=args.gci,
            deck=args.deck,
            config_path=args.config,
            template=args.template,
            no_figures=args.no_figures,
            make_html=args.html,
            make_package=args.package,
            project=args.project,
            run_name=args.run_name,
            supersedes=args.supersedes,
            qoi=args.qoi,
        )
        return 0
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return 1


def _resolve_inputs(result_file: Path, deck: Path | None) -> tuple[Path, Path | None]:
    return workflow.resolve_inputs(result_file, deck)


def _cmd_init(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="femrep init")
    ap.add_argument("name")
    ap.add_argument("--root", type=Path, default=Path("femrep_projects"))
    args = ap.parse_args(argv)
    project = workflow.init_project(args.root, args.name)
    print(f"[femrep] project -> {project}")
    return 0


def _cmd_batch(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="femrep batch")
    ap.add_argument("batch_json", type=Path)
    args = ap.parse_args(argv)
    outputs = workflow.run_batch(args.batch_json)
    print(f"[femrep] batch complete: {len(outputs)} run(s)")
    return 0


def _cmd_gci(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="femrep gci")
    ap.add_argument("csv", type=Path, help="CSV with h,f columns")
    ap.add_argument("--out", type=Path, default=Path("gci_runs.json"))
    ap.add_argument("--qoi", default="QoI")
    args = ap.parse_args(argv)
    payload = workflow.build_gci_study_from_csv(args.csv, args.out, args.qoi)
    res = govern.run_gci(payload)
    print(f"[femrep] gci_runs -> {args.out}")
    print(f"[femrep] {res['verdict']}")
    return 0


def doctor() -> int:
    """Lightweight environment check. No solver calls, no license checkout."""
    checks = []

    def add(name: str, ok: bool, note: str):
        checks.append((name, ok, note))

    for mod in ("numpy", "matplotlib", "reportlab", "docx", "pyvista", "ansys.dpf.core"):
        try:
            __import__(mod)
            add(mod, True, "available")
        except Exception as e:
            add(mod, False, str(e).splitlines()[0])
    try:
        import pyvista as pv
        with TemporaryDirectory() as td:
            p = pv.Plotter(off_screen=True)
            p.add_mesh(pv.Sphere())
            p.export_html(str(Path(td) / "scene.html"))
            p.close()
        add("pyvista_html", True, "rotatable HTML export available")
    except Exception as e:
        add("pyvista_html", False, str(e).splitlines()[0])
    try:
        __import__("PySide6")
        add("PySide6", True, "available")
    except Exception as e:
        add("PySide6", False, f"GUI optional dependency missing: {e}".splitlines()[0])

    print("femrep doctor")
    for name, ok, note in checks:
        print(f"  {'OK' if ok else 'WARN'}  {name}: {note}")
    return 0 if all(ok for name, ok, _ in checks if name != "PySide6") else 1


def _load_config(path: Path) -> dict:
    return workflow.load_config(path)


if __name__ == "__main__":
    raise SystemExit(main())
