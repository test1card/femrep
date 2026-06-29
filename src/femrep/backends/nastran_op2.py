"""femrep.backends.nastran_op2 — Nastran .op2 binary via pyNastran (M10, gated).

pyNastran may lack Python 3.14 wheels. The adapter guards the import; if it fails,
it returns an honest {supported: False, fallback: ".f06"} so the pipeline never
crashes and the report says so. Wired fully in M10; minimal stub here so the
backend registry import resolves.
"""
from __future__ import annotations

from pathlib import Path


def extract(result_file: Path, solve_log: Path | None = None) -> dict:
    """Try pyNastran; on any failure (no wheel, API drift, parse error) return an
    honest unsupported-payload pointing at the .f06 fallback. Never raises."""
    unsupported = {
        "solver_hint": "nastran .op2 (UNSUPPORTED — pyNastran not available)",
        "supported": False, "fallback": ".f06",
        "mesh": {"nodes": 0, "elements": {}, "element_types": {}},
        "primary_qoi": {"name": "n/a", "units": "",
                        "min": 0, "max": 0, "hot_node": 0, "cold_node": 0,
                        "hot_node_xyz_mm": [], "cold_node_xyz_mm": []},
        "time_freq": {"n_sets": 0, "n_sequence_files": 1, "sample_times_s": []},
        "available_results": [],
        "convergence": {"source": "nastran_op2", "file": None, "substeps": 0,
                        "final_total_time": None, "monitors_last": [],
                        "converged": None,
                        "note": "pyNastran unavailable (no Python 3.14 wheel); "
                                "use the .f06 companion file instead"},
    }
    try:
        import pyNastran  # noqa: F401
    except Exception:
        return unsupported
    # pyNastran importable but the full binary-parse adapter is future work;
    # be honest rather than ship a half-tested path.
    unsupported["note"] = ("pyNastran present but .op2 binary adapter not yet wired; "
                           "use the .f06 companion file for now")
    return unsupported
