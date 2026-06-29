"""Smoke tests: no external data required. Run with: pytest tests/

These verify the pure-stdlib pieces (governance logic, CLT math, config loading)
that don't need a 288MB .rth. The DPF/pyvista backends are exercised via the
examples/ against real data, not here.
"""
from __future__ import annotations
import sys
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
