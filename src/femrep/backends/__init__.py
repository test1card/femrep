"""femrep.backends — backend registry: one adapter per solver/result format.

Each adapter has signature  extract(result_file: Path, solve_log: Path|None, qoi: str|None) -> dict
and returns the SAME results.json schema, so govern/figures/render are untouched.
"""
from __future__ import annotations

from pathlib import Path


def _ansys_adapter(result_file: Path, solve_log: Path | None = None,
                   qoi: str | None = None) -> dict:
    """Lazy: import ansys.dpf only when an .rst/.rth is actually read, so launching
    the GUI or reading a Nastran .f06 never loads (or crashes on) ansys-dpf-core."""
    from . import ansys_dpf
    return ansys_dpf.extract(result_file, solve_log, qoi)


def _op2_adapter(result_file: Path, solve_log: Path | None = None,
                 qoi: str | None = None) -> dict:
    """Placeholder until M10: .op2 routes to the .f06 companion or reports unsupported."""
    from . import nastran_op2
    return nastran_op2.extract(result_file, solve_log, qoi)


def _f06_adapter(result_file: Path, solve_log: Path | None = None,
                 qoi: str | None = None) -> dict:
    from . import nastran_f06
    return nastran_f06.extract(result_file, solve_log, qoi)


REGISTRY = {
    ".rth": _ansys_adapter,
    ".rst": _ansys_adapter,
    ".f06": _f06_adapter,
    ".op2": _op2_adapter,
}


def adapter_for(suffix: str):
    return REGISTRY.get(suffix.lower())
