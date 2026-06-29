"""femrep.backends.nastran_op2 — Nastran .op2 binary via pyNastran.

Raises a clear error rather than silently producing an empty report. pyNastran
pins numpy 1.26.4 which does not build on Python 3.14, so the .op2 path is
currently unavailable; the user must use the .f06 companion file. When pyNastran
is installed AND the binary adapter is wired, this module will do the real parse.
"""
from __future__ import annotations

from pathlib import Path


class Op2UnsupportedError(RuntimeError):
    """Raised when .op2 cannot be read. Carries a hint to the .f06 fallback."""


def _f06_companion(op2_path: Path) -> Path | None:
    """Look for a same-stem .f06 beside the .op2."""
    cand = op2_path.with_suffix(".f06")
    return cand if cand.exists() else None


def extract(result_file: Path, solve_log: Path | None = None,
            qoi: str | None = None) -> dict:
    """Attempt .op2 read; raise Op2UnsupportedError with a redirect hint on failure."""
    companion = _f06_companion(result_file)
    hint = (f"Use the .f06 companion instead: {companion}" if companion
            else "Re-run the Nastran job with .f06 output, or supply the .f06 file.")
    try:
        import pyNastran  # noqa: F401  type: ignore[import-not-found]
    except Exception:
        raise Op2UnsupportedError(
            f".op2 binary parsing requires pyNastran, which is not installed "
            f"(its numpy pin does not build on this Python). {hint}")
    # pyNastran importable but the full binary adapter is not yet wired.
    raise Op2UnsupportedError(
        f"pyNastran is installed but the .op2 adapter is not wired yet. {hint}")
