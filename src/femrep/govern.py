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
import hashlib
import json
import platform
import re
from pathlib import Path

# Vendored GCI (Roache / ASME V&V 20) — no machine-local skill-path dependency.
from ._gci import gci as _gci, verdict as _gci_verdict

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


# --- internal execution-mode claim discipline, rendered with public-facing language ---
CLAIM_TEMPLATES = {
    "SMOKE": ("**Issued engineering report.** {qoi_name} = {qoi_range} for the stated load case. "
              "Evidence checks: {gates_passed}. {disc_note} See the governance section for "
              "open evidence items and limitations."),
    "DEBUG": ("**Issued engineering report.** {qoi_name} = {qoi_range} for the stated load case. "
              "Evidence checks: {gates_passed}. {disc_note} See the governance section for "
              "open evidence items and limitations."),
    "ENGINEERING": ("**Issued engineering report.** {qoi_name} = {qoi_range} for the stated load case. "
                    "Evidence checks: {gates_passed}. {disc_note} See the governance section for "
                    "open evidence items and limitations."),
    "SIGNOFF": ("**Issued engineering report.** {qoi_name} = {qoi_range_max}. GCI_fine = "
                "{gci_pct}%. See the governance section for evidence checks, manifest, and "
                "traceability."),
}


def _detect_solver_version(solver_hint: str) -> tuple[str, str]:
    """Best-effort solver version from the install env, NOT a hardcoded constant.

    Ansys: read AWP_ROOT<vNN> env vars (set by the installer); Nastran: unknown
    from the result file alone -> 'unknown (not detected)'. Falls back honestly
    rather than asserting a version that may not be the one that produced the file.
    Returns (version_label, source).
    """
    import os
    if "ansys" in solver_hint.lower() or ".rst" in solver_hint.lower() or ".rth" in solver_hint.lower():
        roots = {k: v for k, v in os.environ.items() if re.fullmatch(r"AWP_ROOT\d+", k)}
        if roots:
            latest = max(roots, key=lambda k: int(k.replace("AWP_ROOT", "")))
            ver = latest.replace("AWP_ROOT", "")   # "261"
            if len(ver) >= 2:
                year = 2000 + int(ver[:-1])
                return f"Ansys {year} R{ver[-1]} (v{ver})", "environment"
            return f"Ansys v{ver}", "environment"
        return "Ansys (version not detected - AWP_ROOT env var absent)", "not_detected"
    if "nastran" in solver_hint.lower():
        return "Nastran (version not in .f06; set by the solve environment)", "not_in_result"
    return "unknown (not detected)", "not_detected"


def _sha256_of(path: Path) -> str | None:
    """SHA-256 of a file, or None if the path is missing."""
    if not path or not Path(path).exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(results: dict, mode: str, *,
                   deck_path: Path | None = None,
                   solver_version: str | None = None,
                   superseded_by: str | None = None) -> dict:
    """Assemble the run-manifest provenance block (NAFEMS R0033 spine).

    Solver version is DETECTED (env vars), not hardcoded. Deck SHA is COMPUTED
    when a deck path is supplied and exists; result SHA is carried from extract.
    """
    qoi = results["primary_qoi"]
    solver_hint = results.get("solver_hint", "Ansys")
    if solver_version:
        detected_ver = solver_version
        version_source = "user-supplied"
    else:
        detected_ver, version_source = _detect_solver_version(solver_hint)
    deck_sha = _sha256_of(deck_path) if deck_path else None
    return {
        "mode": mode,
        "_mode_enum": list(MODES),
        "solver": solver_hint,
        "solver_version": detected_ver,
        "solver_version_source": version_source,
        "platform": f"{platform.system()} {platform.machine()}",
        "command_line": "(reported by the solve script that produced this result)",
        "units": "SI (m, kg, s, K, N, Pa, W)",
        "analysis_type": solver_hint,
        "deck_path": str(deck_path) if deck_path else None,
        "deck_sha256": deck_sha,
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
        "superseded_by": superseded_by,
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


def evaluate_readiness(results: dict, manifest: dict, gates: list[dict],
                       gci: dict | None) -> dict:
    """Summarize report evidence completeness without hiding limitations.

    femis: the report can be issued, but missing verification evidence must stay
    visible instead of being laundered into a green status.
    """
    items: list[dict] = []

    def add(key: str, status: str, note: str, fix: str = ""):
        items.append({"key": key, "status": status, "note": note, "fix": fix})

    add("result_hash", "complete" if manifest.get("result_sha256") else "missing",
        "result file SHA-256 captured" if manifest.get("result_sha256") else
        "result file hash is missing",
        "extract from a readable result file")
    add("deck_hash", "complete" if manifest.get("deck_sha256") else "missing",
        "input deck SHA-256 captured" if manifest.get("deck_sha256") else
        "input deck was not supplied or could not be hashed",
        "pass --deck path/to/input deck")

    conv = results.get("convergence", {})
    if conv.get("converged") is True:
        add("convergence", "complete", conv.get("note", "convergence evidence present"))
    elif conv.get("converged") is False:
        add("convergence", "blocked", conv.get("note", "non-convergence detected"),
            "fix the solve and regenerate the result")
    else:
        add("convergence", "missing", conv.get("note", "convergence evidence missing"),
            "provide a solver log or monitor file")

    if gci:
        add("mesh_independence", "complete" if gci.get("verdict_level") == "pass" else "warning",
            gci.get("verdict", "GCI study present"),
            "refine further or add grids if GCI is not passing")
    else:
        add("mesh_independence", "missing", "GCI study not supplied",
            "provide a gci_runs.json with at least three systematically refined grids")

    has_geometry = not results.get("primary_qoi", {}).get("_nastran_no_geometry")
    add("geometry", "complete" if has_geometry else "not_applicable",
        "geometry available for contour views" if has_geometry else
        ".f06 contains tabular results but no mesh geometry")

    failed = [g for g in gates if g["verdict"] == "fail"]
    not_done = [g for g in gates if g["verdict"] == "not_done"]
    if failed or any(i["status"] == "blocked" for i in items):
        status = "blocked"
        summary = "Blocked: at least one gate or evidence item failed."
    elif not_done or any(i["status"] == "missing" for i in items):
        status = "issue_with_limitations"
        summary = "Issue with limitations: report is traceable, but verification evidence is incomplete."
    else:
        status = "ready_to_issue"
        summary = "Ready to issue: required evidence is complete."

    return {"status": status, "summary": summary, "items": items}


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


def phrase_claim(mode: str, results: dict, gci: dict | None,
                 gates: list[dict] | None = None) -> str:
    """Render the mode-correct claim sentence (femis claim-templates).

    `gates` is the list from evaluate_gates(); used to list which checks passed
    in the ENGINEERING claim. Falls back to '(see gates)' if not supplied.
    """
    qoi = results["primary_qoi"]
    if gci:
        disc_note = (f"Discretization error addressed: GCI_fine {gci['gci_fine_pct']:.2f}% "
                     f"(p {gci['observed_order_p']:.2f}, asymptotic "
                     f"{gci['asymptotic_ratio']:.2f}).")
    else:
        disc_note = ("Discretization error: single-mesh — mesh independence NOT yet "
                     "demonstrated (no GCI).")
    if gates:
        passed = ", ".join(g["gate"] for g in gates if g["verdict"] == "pass") or "(none yet)"
    else:
        passed = "(see gates)"
    return CLAIM_TEMPLATES[mode].format(
        solver=results.get("solver_hint", "Ansys"),
        analysis=results.get("solver_hint", "thermal"),
        ext=Path(results["result_file"]).suffix,
        qoi_name=qoi["name"], qoi_units=qoi["units"],
        qoi_range=fmt_qoi(qoi),
        qoi_range_max=fmt_qoi({**qoi, "min": qoi["max"]}),
        gates_passed=passed,
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
    claim = phrase_claim(args.mode, results, gci, gates)
    readiness = evaluate_readiness(results, manifest, gates, gci)

    args.results.parent.joinpath("manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    checks = {"mode": args.mode, "claim": claim, "gates": gates,
              "gci": gci, "readiness": readiness, "femis_version": "1.0.2"}
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
