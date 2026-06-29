"""femrep.convergence — parse solver convergence history from the honest source.

The recon found the corpus is LINEAR THERMAL: the .out files have no Newton-
Raphson residuals, only SUBSTEP-COMPLETED markers. The real convergence story
lives in the Ansys .mntr (solution monitor): a substep table with total time,
elapsed, and the monitor variables (often the QoI itself). This module parses
.mntr as the primary source and falls back honestly when absent.

femis gate stays honest: 'converged' means the substep table reaches the final
time without an abort marker. We never invent residual orders that aren't there.
"""
from __future__ import annotations

import re
from pathlib import Path

# .mntr substep rows look like:
#     1     43    1     1     43    6598.2      0.16560E+06   0.0000   8.7764  -270.15  0.0000   0.0000
# columns: load_step, sub_step, attempt, iter, cum_iter, inc_time, total_time,
#          elapsed, mem, monitor1..5
_MNTR_ROW = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
    r"([0-9.eE+\-]+)\s+([0-9.eE+\-]+)\s+([0-9.eE+\-]+)\s+([0-9.eE+\-]+)"
    r"((?:\s+[0-9.eE+\-]+)*)\s*$"
)


def parse_mntr(mntr_path: Path | None) -> dict:
    """Parse an Ansys .mntr solution-monitor file.

    Returns {substeps, final_total_time, monitors_last, converged, note}.
    converged is True if rows are present and no abort/error marker; None if no file.
    """
    out = {"source": "ansys_mntr", "file": str(mntr_path) if mntr_path else None,
           "substeps": 0, "final_total_time": None, "monitors_last": [],
           "converged": None, "note": ""}
    if not mntr_path or not mntr_path.exists():
        out["note"] = "no .mntr monitor file provided"
        return out
    text = mntr_path.read_text(errors="replace")
    if "aborted" in text.lower() or "is stopped" in text.lower():
        out["converged"] = False
        out["note"] = "abort/stop marker in .mntr"
        return out
    rows = []
    for line in text.splitlines():
        m = _MNTR_ROW.match(line)
        if m:
            monitors = [float(x) for x in m.group(10).split()] if m.group(10).strip() else []
            rows.append({
                "load_step": int(m.group(1)), "sub_step": int(m.group(2)),
                "total_time": float(m.group(7)),
                "monitors": monitors,
            })
    if not rows:
        out["converged"] = None
        out["note"] = ".mntr present but no substep rows parsed"
        return out
    out["substeps"] = len(rows)
    out["final_total_time"] = rows[-1]["total_time"]
    out["monitors_last"] = rows[-1]["monitors"]
    out["converged"] = True
    out["note"] = (f"{len(rows)} substeps completed to t={rows[-1]['total_time']:g} "
                   f"(linear solve; no Newton-Raphson residuals in this deck)")
    out["time_series"] = [r["total_time"] for r in rows]  # for an optional convergence plot
    return out


def parse(log_path: Path | None) -> dict:
    """Dispatch by file type. .mntr is the honest primary source for this corpus.

    The old .out heuristic (HEAT residual regex) is kept only as a fallback for
    decks that genuinely carry residuals — not these linear-thermal runs.
    """
    if log_path and log_path.suffix.lower() == ".mntr":
        return parse_mntr(log_path)
    # fallback: minimal .out marker scan (no invented residuals)
    out = {"source": "ansys_out", "file": str(log_path) if log_path else None,
           "substeps": 0, "final_total_time": None, "monitors_last": [],
           "converged": None, "note": ""}
    if not log_path or not log_path.exists():
        out["note"] = "no solve log provided; convergence verdict deferred"
        return out
    text = log_path.read_text(errors="replace")
    out["substeps"] = len(re.findall(r"SUBSTEP\s+\d+\s+COMPLETED", text))
    if "is stopped" in text.lower() or "error termination" in text.lower():
        out["converged"] = False
        out["note"] = "stop/error marker in .out"
    elif out["substeps"] > 0:
        out["converged"] = True
        out["note"] = f"{out['substeps']} SUBSTEP-COMPLETED markers (no residual data in linear deck)"
    else:
        out["converged"] = None
        out["note"] = ".out provided but no convergence markers recognized"
    return out
