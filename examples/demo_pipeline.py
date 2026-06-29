"""Example: run the full femrep pipeline programmatically (no CLI).

Demonstrates the layer-by-layer API: extract -> govern -> figures -> render.
Uses a synthetic in-memory thermal result so it runs with no external data.
For real backends, point `result_file` at a .rst/.rth/.f06.
"""
from __future__ import annotations
from pathlib import Path

from femrep import extract, govern
from femrep import figures as fig_mod
from femrep import report_pdf, cli as cli_mod


def demo(result_file: Path, out_dir: Path, mode: str = "ENGINEERING") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. extract (backend auto-selected by file suffix)
    results = extract.extract(result_file)
    (out_dir / "results.json").write_text(
        __import__("json").dumps(results, indent=2), encoding="utf-8")

    # 2. govern (femis: manifest + gates + claim phrasing)
    manifest = govern.build_manifest(results, mode, deck_path=None)
    gates = govern.evaluate_gates(results, mode, manifest, gci=None)
    claim = govern.phrase_claim(mode, results, gci=None)
    checks = {"mode": mode, "claim": claim, "gates": gates, "gci": None}
    (out_dir / "manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "checks.json").write_text(
        __import__("json").dumps(checks, indent=2), encoding="utf-8")

    # 3. figures
    figures = fig_mod.generate(results, None, out_dir)

    # 4. render PDF
    cfg = cli_mod._load_config(Path(__file__).resolve().parents[1]
                               / "src" / "femrep" / "config.yaml")
    out_pdf = out_dir / "report.pdf"
    report_pdf.render(results, manifest, checks, cfg, figures,
                      {"generated": "demo"}, out_pdf)
    return out_pdf


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m examples.demo_pipeline <result_file> [out_dir]")
        sys.exit(1)
    rf = Path(sys.argv[1])
    od = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("demo_out")
    pdf = demo(rf, od)
    print(f"report -> {pdf}")
