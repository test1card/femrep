"""Smoke tests: no external data required. Run with: pytest tests/

These verify the pure-stdlib pieces (governance logic, CLT math, config loading)
that don't need a 288MB .rth. The DPF/pyvista backends are exercised via the
examples/ against real data, not here.
"""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path

# make src/ importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_modes_constant():
    from femrep.govern import MODES
    assert MODES == ("SMOKE", "DEBUG", "ENGINEERING", "SIGNOFF")


def test_claim_templates_have_all_modes():
    from femrep.govern import CLAIM_TEMPLATES
    for m in ("SMOKE", "DEBUG", "ENGINEERING", "SIGNOFF"):
        assert m in CLAIM_TEMPLATES, f"missing claim template for {m}"


def test_fmt_qoi_stress_mpa():
    from femrep.govern import fmt_qoi
    q = {"min": 0.0, "max": 7490828.25, "units": "Pa"}
    out = fmt_qoi(q)
    # Pa must reduce to MPa; both endpoints present
    assert "MPa" in out and "0 MPa" in out and "7.49 MPa" in out


def test_fmt_qoi_temperature_k():
    from femrep.govern import fmt_qoi
    q = {"min": -270.15, "max": 16.85, "units": "K"}
    out = fmt_qoi(q)
    # K stays K (no unit conversion); both endpoints present
    assert "K" in out and "16.85 K" in out and "-270" in out


def test_clt_symmetric_laminate_b_is_zero():
    """femis self-check: [0/90/0] symmetric -> B (coupling) = 0."""
    import numpy as np
    from femrep.cases.clt_synthetic import abd_matrix, LAYUP
    _, B, _ = abd_matrix(LAYUP)
    assert np.max(np.abs(B)) < 1e-6, "symmetric layup must have B≈0"


def test_clt_fpf_yields_irf_one():
    """femis self-check: the computed FPF load gives Tsai-Wu IRF ≈ 1.0."""
    from femrep.cases.clt_synthetic import tsai_wu_irf, case, LAYUP
    fpf = case()["fpf_Nx_N_per_mm"]
    irf = tsai_wu_irf(fpf, LAYUP)
    assert abs(irf - 1.0) < 0.01


def test_config_loads():
    from femrep import cli
    cfg = cli._load_config(Path(__file__).resolve().parents[1] / "src" / "femrep" / "config.yaml")
    assert cfg.get("color_primary", "").startswith("#")
    assert "title" in cfg


def test_backend_registry_has_all_formats():
    from femrep.backends import REGISTRY
    for ext in (".rth", ".rst", ".f06", ".op2"):
        assert ext in REGISTRY


def _minimal_results() -> dict:
    return {
        "solver_hint": "nastran steady_thermal (.f06)",
        "result_file": "tiny.f06",
        "result_sha256": "abc123",
        "mesh": {"nodes": 2, "elements": {}, "element_types": {}},
        "primary_qoi": {
            "name": "temperature",
            "units": "K",
            "min": 300.0,
            "max": 305.0,
            "hot_node": 0,
            "cold_node": 0,
        },
        "convergence": {
            "converged": True,
            "substeps": 1,
            "note": "output tables complete",
        },
    }


def test_manifest_hashes_supplied_deck(tmp_path):
    from femrep import govern

    deck = tmp_path / "model.dat"
    deck.write_text("GRID,1\n", encoding="utf-8")

    manifest = govern.build_manifest(_minimal_results(), "ENGINEERING", deck_path=deck)

    assert manifest["deck_sha256"] == hashlib.sha256(deck.read_bytes()).hexdigest()
    assert manifest["deck_path"] == str(deck)
    assert manifest["solver_version"] != "2026R1 (v261)"


def test_phrase_claim_lists_passed_gates():
    from femrep import govern

    results = _minimal_results()
    manifest = govern.build_manifest(results, "ENGINEERING")
    gates = govern.evaluate_gates(results, "ENGINEERING", manifest, gci=None)
    claim = govern.phrase_claim("ENGINEERING", results, gci=None, gates=gates)

    assert "Evidence checks: units, thermal_connectivity, convergence." in claim
    assert "(see gates)" not in claim


def test_readiness_reports_missing_verification_items():
    from femrep import govern

    results = _minimal_results()
    manifest = govern.build_manifest(results, "ENGINEERING")
    gates = govern.evaluate_gates(results, "ENGINEERING", manifest, gci=None)
    readiness = govern.evaluate_readiness(results, manifest, gates, gci=None)

    assert readiness["status"] == "issue_with_limitations"
    statuses = {item["key"]: item["status"] for item in readiness["items"]}
    assert statuses["result_hash"] == "complete"
    assert statuses["deck_hash"] == "missing"
    assert statuses["mesh_independence"] == "missing"


def test_cli_resolves_op2_to_f06_companion(tmp_path):
    from femrep import cli

    op2 = tmp_path / "run.op2"
    op2.write_bytes(b"op2")
    f06 = tmp_path / "run.f06"
    f06.write_text("SOL 153\n", encoding="utf-8")

    result, deck = cli._resolve_inputs(op2, None)

    assert result == f06
    assert deck is None


def test_extract_adds_qoi_catalog(tmp_path):
    from femrep import extract

    payload = extract.extract(_tiny_f06(tmp_path))

    assert payload["qoi_catalog"][0]["name"] == "temperature"
    assert payload["qoi_catalog"][0]["role"] == "primary"


def test_extract_honors_supported_qoi_and_rejects_unknown(tmp_path):
    from femrep import extract

    f06 = _tiny_f06(tmp_path)
    assert extract.extract(f06, qoi="temperature")["primary_qoi"]["name"] == "temperature"
    try:
        extract.extract(f06, qoi="von_mises_stress")
    except ValueError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("unsupported .f06 QoI should fail loudly")


def test_f06_repeated_block_bodies_keep_distinct_times():
    from femrep.backends.nastran_f06 import _parse_temperature_blocks

    text = """
SOL 159
TIME = 1.0
 T E M P E R A T U R E   V E C T O R
      1 S  300.0 301.0
TIME = 2.0
 T E M P E R A T U R E   V E C T O R
      1 S  300.0 301.0
"""

    blocks = _parse_temperature_blocks(text)

    assert [b["time"] for b in blocks] == [1.0, 2.0]


def test_op2_backend_fails_loudly(tmp_path):
    from femrep.backends.nastran_op2 import Op2UnsupportedError, extract

    op2 = tmp_path / "run.op2"
    op2.write_bytes(b"not really op2")
    f06 = tmp_path / "run.f06"
    f06.write_text("SOL 153\n", encoding="utf-8")

    try:
        extract(op2)
    except Op2UnsupportedError as exc:
        assert str(f06) in str(exc)
    else:
        raise AssertionError(".op2 backend must not return an empty report payload")


def _import_ansys_dpf_backend():
    """Import the DPF backend with ansys.dpf/numpy stubbed, so the pure-stdlib
    file-sequence logic is testable on a machine without Ansys installed."""
    import types

    sys.modules.setdefault("numpy", types.ModuleType("numpy"))
    ansys = sys.modules.setdefault("ansys", types.ModuleType("ansys"))
    dpf_pkg = sys.modules.setdefault("ansys.dpf", types.ModuleType("ansys.dpf"))
    core = sys.modules.setdefault("ansys.dpf.core", types.ModuleType("ansys.dpf.core"))
    ansys.dpf = dpf_pkg
    dpf_pkg.core = core
    from femrep.backends import ansys_dpf
    return ansys_dpf


def test_rst_distributed_domains_not_expanded(tmp_path):
    """Workbench dp0 distributed solve: file.rst sits beside file0.rst..fileN.rst
    (per-domain files, NOT time steps). femrep must read file.rst as given, never
    expand the domains into a bogus transient sequence."""
    ansys_dpf = _import_ansys_dpf_backend()
    for name in ("file.rst", "file0.rst", "file1.rst", "file2.rst"):
        (tmp_path / name).write_bytes(b"x")

    assert [p.name for p in ansys_dpf._sequence_files(tmp_path / "file.rst")] == ["file.rst"]
    # even pointing straight at a domain file must not expand
    assert [p.name for p in ansys_dpf._sequence_files(tmp_path / "file0.rst")] == ["file0.rst"]


def test_rth_thermal_transient_sequence_still_expands(tmp_path):
    """Thermal .rth transients genuinely split sets across file0.rth..fileN.rth;
    that expansion must be preserved."""
    ansys_dpf = _import_ansys_dpf_backend()
    for name in ("file.rth", "file0.rth", "file1.rth", "file2.rth"):
        (tmp_path / name).write_bytes(b"x")

    expanded = [p.name for p in ansys_dpf._sequence_files(tmp_path / "file.rth")]
    assert expanded == ["file0.rth", "file1.rth", "file2.rth"]
    # a lone .rth with no siblings reads as itself
    (tmp_path / "single.rth").write_bytes(b"x")
    assert [p.name for p in ansys_dpf._sequence_files(tmp_path / "single.rth")] == ["single.rth"]


def test_dpf_grpc_transport_defaults_to_insecure():
    """Importing the DPF backend must pre-set an unsecured gRPC transport so a
    local run never hits the 2026 R1 mutual-TLS cert requirement."""
    import os

    _import_ansys_dpf_backend()
    assert os.environ.get("DPF_GRPC_MODE") == "insecure"
    assert os.environ.get("DPF_DEFAULT_GRPC_MODE") == "insecure"


def _tiny_f06(tmp_path: Path) -> Path:
    f06 = tmp_path / "tiny.f06"
    f06.write_text(
        "SOL 153\n"
        "TIME = 1.0\n"
        " T E M P E R A T U R E   V E C T O R\n"
        "      1 S  300.0 301.0 302.0\n",
        encoding="ascii",
    )
    (tmp_path / "tiny.dat").write_text("GRID,1\n", encoding="ascii")
    return f06


def test_workflow_report_html_package_and_project_index(tmp_path):
    from femrep import workflow

    f06 = _tiny_f06(tmp_path)
    project = workflow.init_project(tmp_path / "projects", "Demo")
    artifacts = workflow.run_report(
        f06,
        out=tmp_path / "report.pdf",
        no_figures=True,
        make_html=True,
        make_package=True,
        project=project,
        run_name="run001",
    )

    run_dir = project / "runs" / "run001"
    assert (run_dir / "report.pdf").exists()
    assert artifacts["html"] and artifacts["html"].exists()
    assert artifacts["package"] and artifacts["package"].exists()
    with zipfile.ZipFile(artifacts["package"]) as z:
        assert "PACKAGE_MANIFEST.json" in z.namelist()
    assert (run_dir / "inputs" / "tiny.f06").exists()
    assert "run001" in (project / "runs_index.csv").read_text(encoding="utf-8")


def test_gci_study_from_csv_and_batch_accepts_bom(tmp_path):
    from femrep import workflow

    csv_path = tmp_path / "gci.csv"
    csv_path.write_text("h,f\n0.25,100\n0.5,102\n1.0,106\n", encoding="ascii")
    gci_json = tmp_path / "gci_runs.json"
    payload = workflow.build_gci_study_from_csv(csv_path, gci_json, "peak_temperature_K")
    assert payload["qoi"] == "peak_temperature_K"
    assert len(payload["grids"]) == 3

    f06 = _tiny_f06(tmp_path)
    batch = tmp_path / "batch.json"
    spec = {"runs": [{"result": str(f06), "out": str(tmp_path / "batch.pdf"),
                      "no_figures": True, "html": True, "package": True}]}
    batch.write_text(json.dumps(spec), encoding="utf-8-sig")
    outputs = workflow.run_batch(batch)
    assert len(outputs) == 1
    assert (tmp_path / "batch.pdf").exists()


def test_gci_study_can_extract_qoi_from_result_csv(tmp_path):
    from femrep import workflow

    f06 = _tiny_f06(tmp_path)
    csv_path = tmp_path / "gci_results.csv"
    csv_path.write_text(f"h,result\n0.5,{f06}\n1.0,{f06}\n2.0,{f06}\n", encoding="utf-8")
    payload = workflow.build_gci_study_from_csv(csv_path, tmp_path / "gci_from_results.json")

    assert payload["grids"][0]["f"] == 302.0
