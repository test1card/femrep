"""femrep.cli — entrypoint: ingest a result file, run the full pipeline.

    python -m femrep.cli <result_file> [--mode ENGINEERING] [--log solve.out]
                                       [--gci gci_runs.json] [--out report.pdf]

Drives extract -> govern -> render in one call. Each stage also writes its JSON
beside the report so you can re-run a later stage standalone.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from . import extract, govern


def main() -> int:
    ap = argparse.ArgumentParser(prog="femrep",
                                 description="femis-governed Ansys FEM report generator.")
    ap.add_argument("result_file", type=Path, help="Ansys .rst/.rth result file")
    ap.add_argument("--log", type=Path, default=None, help="solve .out/.mntr log")
    ap.add_argument("--mode", choices=govern.MODES, default="ENGINEERING")
    ap.add_argument("--gci", type=Path, default=None, help="gci_runs.json for mesh study")
    ap.add_argument("--deck", type=Path, default=None, help="input deck path (for manifest)")
    ap.add_argument("--out", type=Path, default=Path("femrep_report.pdf"),
                    help="output path; extension decides pdf/docx")
    ap.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml")
    ap.add_argument("--no-figures", action="store_true",
                    help="skip figure generation (text-only report)")
    args = ap.parse_args()

    if not args.result_file.exists():
        print(f"ERROR: {args.result_file} not found", flush=True)
        return 1

    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"

    # 1. extract
    print(f"[femrep] extracting {args.result_file} ...", flush=True)
    results = extract.extract(args.result_file, args.log)
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # 2. govern
    print(f"[femrep] applying femis governance (mode={args.mode}) ...", flush=True)
    gci = govern.run_gci(json.loads(args.gci.read_text(encoding="utf-8"))) if args.gci else None
    manifest = govern.build_manifest(results, args.mode, deck_path=args.deck)
    gates = govern.evaluate_gates(results, args.mode, manifest, gci)
    claim = govern.phrase_claim(args.mode, results, gci)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks = {"mode": args.mode, "claim": claim, "gates": gates, "gci": gci}
    (out_dir / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

    # 3. figures (M3) — optional, off for text-only M2
    figure_paths: dict = {}
    if not args.no_figures:
        try:
            from . import figures as fig_mod
            figure_paths = fig_mod.generate(results, gci, out_dir)
            print(f"[femrep] figures: {list(figure_paths)}", flush=True)
        except Exception as e:
            print(f"[femrep] figures skipped: {e}", flush=True)

    # 4. render
    config = _load_config(args.config)
    ext = args.out.suffix.lower()
    report_meta = {"generated": datetime.now().isoformat(timespec="seconds"),
                   "config_path": str(args.config)}
    if ext == ".docx":
        from . import report_docx
        report_docx.render(results, manifest, checks, config, figure_paths,
                           report_meta, args.out)
    else:
        from . import report_pdf
        report_pdf.render(results, manifest, checks, config, figure_paths,
                          report_meta, args.out)
    print(f"[femrep] report -> {args.out}", flush=True)
    return 0


def _load_config(path: Path) -> dict:
    """Tiny YAML reader for the flat key:value config (no yaml dep needed).

    Only strips comments that follow a quoted value: a `#` inside quotes is kept,
    so hex colors like "#1f3a5f" survive. (ponytail: no yaml dep until nesting is needed.)
    """
    cfg = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # find the first ':' outside any quote
        in_q = False
        for i, ch in enumerate(line):
            if ch == '"':
                in_q = not in_q
            elif ch == ":" and not in_q:
                k, v = line[:i].strip(), line[i + 1:]
                break
        else:
            continue
        # strip a trailing comment (after a quoted value or a bare value)
        v = v.strip()
        if v.startswith('"'):
            end = v.find('"', 1)
            v = v[1:end] if end != -1 else v.strip('"')
        else:
            v = v.split("#", 1)[0].strip()
        cfg[k] = None if v.lower() == "null" else v
    return cfg


if __name__ == "__main__":
    raise SystemExit(main())
