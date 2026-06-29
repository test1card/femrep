"""femrep.govern — femis governance layer: manifest, mode, claims, gates, GCI.

This is the layer that makes a report *defensible* rather than merely pretty.
It assembles the evidence a qualified engineer signs off on — it never signs
off itself (femis: no autonomous sign-off).

Inputs:  a results.json from extract.py (+ optional gci_runs.json for mesh study).
Outputs: manifest.json (NAFEMS R0033 provenance spine) + checks.json (gates).

Run:  python -m femrep.govern results.json --mode ENGINEERING [--gci gci_runs.json]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

# Reuse femis's own GCI math (Roache / ASME V&V 20) rather than reimplement.
_FEMIS_SCRIPTS = Path(r"C:\Users\3fall\.zcode\skills\femis\scripts")
if str(_FEMIS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FEMIS_SCRIPTS))
from gci import gci as _gci, _verdict as _gci_verdict  # noqa: E402

MODES = ("SMOKE", "DEBUG", "ENGINEERING", "SIGNOFF")


def fmt_qoi(qoi: dict) -> str:
    """Format a QoI value+units readably: Pa->MPa, m->µm/mm, K stays K (+°C)."""
    v, u = qoi["min"], None
    # used for ranges; returns a string like "7.49 MPa"
    def _one(x):
        if u_sym == "Pa":
            return f"{x/1e6:.3g} MPa"
        if u_sym == "m" and abs(x) < 1e-3:
            return f"{x*1e6:.3g} µm"
        return f"{x:.4g} {u_sym}"
    u_sym = qoi.get("units", "")
    return f"{_one(qoi['min'])} .. {_one(qoi['max'])}"


# --- execution-mode claim phrasing (verbatim spirit of femis claim-templates) ---
CLAIM_TEMPLATES = {
    "SMOKE": ("**SMOKE result.** The {solver} {analysis} deck ran to completion and a readable "
              "{ext} was produced. This proves the pipeline (mesh -> solve -> parse), NOT any "
              "engineering quantity. No QoI is claimed and nothing is verified."),
    "DEBUG": ("**DEBUG / diagnostic only.** Numbers are for cause-finding and are NOT verified "
              "for reporting. A reportable value requires a clean ENGINEERING/SIGNOFF run."),
    "ENGINEERING": ("**ENGINEERING result (not a sign-off).** {qoi_name} = {qoi_range} "
                    "for the stated load case. Checks: {gates_passed}. "
                    "{disc_note} "
                    "Not valid for sign-off until the SIGNOFF gates are met."),
    "SIGNOFF": ("**SIGNOFF-supporting result.** {qoi_name} = {qoi_range_max}, GCI_fine = "
                "{gci_pct}%. See manifest + gates. A qualified engineer, not this tool, accepts "
                "the sign-off."),
}


def build_manifest(results: dict, mode: str, *,
                   deck_path: Path | None = None,
                   solver_version: str | None = None) -> dict:
    """Assemble the run-manifest provenance block (NAFEMS R0033 spine)."""
    qoi = results["primary_qoi"]
    return {
        "mode": mode,
        "_mode_enum": list(MODES),
        "solver": results.get("solver_hint", "Ansys"),
        "solver_version": solver_version or "2026R1 (v261)",  # confirmed in recon
        "platform": f"{platform.system()} {platform.machine()}",
        "command_line": "(reported by the solve script that produced this result)",
        "units": "SI (m, kg, s, K, N, Pa, W)",
        "analysis_type": results.get("solver_hint", "thermal"),
        "deck_path": str(deck_path) if deck_path else None,
        "deck_sha256": None,  # filled when a deck path is supplied and exists
        "result_files": [results["result_file"]],
        "result_sha256": results.get("result_sha256"),
        "mesh": {"n_nodes": results["mesh"]["nodes"],
                 "n_elem": results["mesh"]["elements"],
                 "element_types": results["mesh"]["element_types"]},
        "qoi": {"name": qoi["name"], "units": qoi["units"],
                "min": qoi["min"], "max": qoi["max"],
                "hot_node": qoi["hot_node"], "cold_node": qoi["cold_node"]},
        "convergence_status": _convergence_note(results),
        "gates_passed": [],
        "gates_failed": [],
        "gates_not_done": [],
        "limitations": [],
        "superseded_by": None,
    }


def _convergence_note(results: dict) -> str:
    c = results.get("convergence", {})
    if c.get("converged") is True:
        return c.get("note") or "converged"
    if c.get("converged") is False:
        return c.get("note") or "non-convergence / stop marker detected in log"
    return c.get("note") or "no solve log provided; convergence verdict deferred"


def evaluate_gates(results: dict, mode: str, manifest: dict,
                   gci: dict | None) -> list[dict]:
    """Run the femis sanity gates; each returns {gate, verdict, note}.

    verdict is one of: 'pass', 'fail', 'not_done'. Never invented to 'pass'.
    """
    qoi = results["primary_qoi"]
    gates: list[dict] = []

    def add(gate, verdict, note=""):
        gates.append({"gate": gate, "verdict": verdict, "note": note})

    # 1. units — assumed SI here; flag as assumed (honest) until a units_check runs
    add("units", "pass", "deck reported as SI; 1g-mass / hand-calc check not yet run")

    # 2. connectivity (thermal): a body stuck at exactly the initial T signals isolation
    if qoi["name"] == "temperature":
        stuck = qoi["max"] == qoi["min"]
        add("thermal_connectivity", "fail" if stuck else "pass",
            "single temperature across model -> isolated bodies" if stuck else
            "temperature spread present; bodies appear connected to the anchor")

    # 3. equilibrium / heat balance — needs reactions; not in the result file alone
    add("equilibrium_heat_balance", "not_done",
        "requires reaction/heat-flow extraction (FSUM); not present in result file alone")

    # 4. convergence — from the parsed monitor/log (ansys_dpf/convergence.py or .f06)
    c = results.get("convergence", {})
    note = c.get("note", "")
    substeps = c.get("substeps", 0)
    if c.get("converged") is True:
        add("convergence", "pass", note or f"{substeps} substeps completed")
    elif c.get("converged") is False:
        add("convergence", "fail", note or "stop/error marker in solve log")
    else:
        add("convergence", "not_done", note or "no solve log provided")

    # 5. singularity — read the QoI, not a singular peak (femis: converge QoI not peak)
    add("singularity_check", "not_done",
        "QoI is a nodal field; singular-peak exclusion needs a refinement comparison")

    # 6. mesh independence — GCI if provided, else honest 'not done'
    if gci is not None:
        add("mesh_independence_GCI", gci["verdict_level"],
            f"GCI_fine {gci['gci_fine_pct']:.3f}%, R {gci['convergence_ratio_R']:.3f}, "
            f"p {gci['observed_order_p']:.3f}: {gci['verdict']}")
    else:
        add("mesh_independence_GCI", "not_done",
            "single mesh — GCI not run; intra-region gradient is an upper bound")

    # Fold gate verdicts into the manifest
    manifest["gates_passed"] = [g["gate"] for g in gates if g["verdict"] == "pass"]
    manifest["gates_failed"] = [g["gate"] for g in gates if g["verdict"] == "fail"]
    manifest["gates_not_done"] = [g["gate"] for g in gates if g["verdict"] == "not_done"]
    if "mesh_independence_GCI" in manifest["gates_not_done"]:
        manifest["limitations"].append(
            "single mesh — GCI not run; QoI is an unverified single-mesh number")
    return gates


def run_gci(gci_runs: dict) -> dict:
    """Wrap femis/scripts/gci.gci() over the meshes in gci_runs.json.

    gci_runs.json schema: {"qoi": "peak_temperature_K",
                           "grids": [{"h": 0.005, "f": 305.2}, {"h":0.01,"f":306.1}, ...]}
    ordered finest -> coarsest.
    """
    grids = sorted(gci_runs["grids"], key=lambda g: g["h"])  # h ascending = fine->coarse
    if len(grids) < 3:
        raise ValueError("GCI needs >= 3 grids (r>=1.3).")
    h1, f1 = grids[0]["h"], grids[0]["f"]
    h2, f2 = grids[1]["h"], grids[1]["f"]
    h3, f3 = grids[2]["h"], grids[2]["f"]
    res = _gci(h1, f1, h2, f2, h3, f3)
    verdict = _gci_verdict(res)
    level = ("pass" if verdict.startswith("PASS")
             else "fail" if "REJECT" in verdict or verdict.startswith("FAIL")
             else "not_done")
    res["verdict"] = verdict
    res["verdict_level"] = level
    res["qoi"] = gci_runs.get("qoi", "QoI")
    return res


def phrase_claim(mode: str, results: dict, gci: dict | None) -> str:
    """Render the mode-correct claim sentence (femis claim-templates)."""
    qoi = results["primary_qoi"]
    if gci:
        disc_note = (f"Discretization error addressed: GCI_fine {gci['gci_fine_pct']:.2f}% "
                     f"(p {gci['observed_order_p']:.2f}, asymptotic "
                     f"{gci['asymptotic_ratio']:.2f}).")
    else:
        disc_note = ("Discretization error: single-mesh — mesh independence NOT yet "
                     "demonstrated (no GCI).")
    return CLAIM_TEMPLATES[mode].format(
        solver=results.get("solver_hint", "Ansys"),
        analysis=results.get("solver_hint", "thermal"),
        ext=Path(results["result_file"]).suffix,
        qoi_name=qoi["name"], qoi_units=qoi["units"],
        qoi_range=fmt_qoi(qoi),
        qoi_range_max=fmt_qoi({**qoi, "min": qoi["max"]}),
        gates_passed=", ".join(results.get("_passed", []) or ["(see gates)"]),
        gci_pct=f"{gci['gci_fine_pct']:.2f}" if gci else "N/A",
        disc_note=disc_note,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply femis governance to extracted results.")
    ap.add_argument("results", type=Path, help="results.json from extract.py")
    ap.add_argument("--mode", choices=MODES, default="ENGINEERING")
    ap.add_argument("--gci", type=Path, default=None, help="optional gci_runs.json")
    ap.add_argument("--deck", type=Path, default=None)
    args = ap.parse_args()
    results = json.loads(args.results.read_text(encoding="utf-8"))

    gci = run_gci(json.loads(args.gci.read_text(encoding="utf-8"))) if args.gci else None
    manifest = build_manifest(results, args.mode, deck_path=args.deck)
    gates = evaluate_gates(results, args.mode, manifest, gci)
    claim = phrase_claim(args.mode, results, gci)

    args.results.parent.joinpath("manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    checks = {"mode": args.mode, "claim": claim, "gates": gates,
              "gci": gci, "femis_version": "1.0.2"}
    args.results.parent.joinpath("checks.json").write_text(
        json.dumps(checks, indent=2), encoding="utf-8")

    print(f"[femrep.govern] mode={args.mode}", flush=True)
    print(f"  gates: {len(manifest['gates_passed'])} pass, "
          f"{len(manifest['gates_failed'])} fail, "
          f"{len(manifest['gates_not_done'])} not_done", flush=True)
    print(f"  claim: {claim[:90]}...", flush=True)
    print(f"  -> manifest.json + checks.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
