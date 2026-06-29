"""femrep.backends.nastran_f06 — stdlib parser for Nastran .f06 (SOL 153/159 thermal).

.f06 is the human-readable Nastran output: EXECUTIVE CONTROL (SOL n), and result
tables. For thermal, the key table is the TEMPERATURE VECTOR, which appears once
per requested time in SOL 159 (transient) or once in SOL 153 (steady). Each row:
       POINT ID.   TYPE      ID   VALUE     ID+1 VALUE  ... (up to 6 values per line)
Pure stdlib regex parse, CRLF-safe. Returns the same results.json schema as the DPF
backend so govern/figures/render are untouched. No DPF, no new dep.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_SOL_RE = re.compile(r"^\s*SOL\s+(\d+)", re.MULTILINE)
_TIME_RE = re.compile(r"^\s*TIME\s*=\s*([0-9.eE+\-]+)", re.MULTILINE)
# a temperature-vector data row: <int>  S  <float> <float> ... (the leading int is POINT ID)
_TEMP_ROW_RE = re.compile(r"^\s*(\d+)\s+S\s+([0-9.eE+\-]+(?:\s+[0-9.eE+\-]+){0,5})")
_SOL_NAME = {"153": "steady_thermal", "159": "transient_thermal",
             "101": "static", "103": "modal", "106": "static"}


def _parse_temperature_blocks(text: str) -> list[dict]:
    """Return [{time, values:[per-grid T]}] for each TIME + TEMPERATURE VECTOR block."""
    blocks = []
    # split on the TEMPERATURE VECTOR header; the TIME line precedes it
    parts = re.split(r"T E M P E R A T U R E\s+V E C T O R", text)
    for part in parts[1:]:  # parts[0] is preamble
        # find the most recent TIME = before this block (search backward in the preceding text)
        preceding = text[: text.find(part)]
        tm = list(_TIME_RE.finditer(preceding))
        t = float(tm[-1].group(1)) if tm else 0.0
        vals = []
        for line in part.splitlines():
            m = _TEMP_ROW_RE.match(line)
            if m:
                vals.extend(float(x) for x in m.group(2).split())
        if vals:
            blocks.append({"time": t, "values": vals})
    # dedupe by time (a table can be echoed twice), keep first
    seen = set()
    out = []
    for b in blocks:
        if b["time"] not in seen:
            seen.add(b["time"])
            out.append(b)
    return out


def extract(result_file: Path, solve_log: Path | None = None) -> dict:
    text = result_file.read_text(errors="replace")
    sol_m = _SOL_RE.search(text)
    sol = sol_m.group(1) if sol_m else "?"
    sol_name = _SOL_NAME.get(sol, f"SOL{sol}")
    blocks = _parse_temperature_blocks(text)

    is_transient = len(blocks) > 1
    primary = blocks[-1]["values"] if blocks else []  # last/only time step
    arr = np.asarray(primary, dtype=float) if primary else np.array([0.0])

    n_grid = len(arr)
    # Nastran thermal has no mesh element histogram in .f06 (it's a node/point dump);
    # report grid points as "nodes" and leave elements empty honestly.
    payload = {
        "solver_hint": f"nastran {sol_name} (.f06)",
        "mesh": {"nodes": n_grid, "elements": {}, "element_types": {}},
        "primary_qoi": {
            "name": "temperature", "units": "K",
            "min": float(arr.min()), "max": float(arr.max()),
            "min_C": round(float(arr.min()) - 273.15, 3),
            "max_C": round(float(arr.max()) - 273.15, 3),
            "hot_node": 0, "cold_node": 0,  # no node-id tracking at schema level; honest zeros
            "hot_node_xyz_mm": [], "cold_node_xyz_mm": [],
            "_nastran_no_geometry": True,  # .f06 carries no XYZ; flagged honestly downstream
        },
        "time_freq": {"n_sets": len(blocks), "n_sequence_files": 1,
                      "sample_times_s": [round(b["time"], 4) for b in blocks[:50]]},
        "available_results": ["temperature"],
        "convergence": _f06_convergence(text, sol, blocks),
    }
    if is_transient:
        all_vals = np.asarray([b["values"] for b in blocks], dtype=float)
        payload["transient"] = {
            "n_sets": len(blocks),
            "times": [round(b["time"], 4) for b in blocks],
            "min": [round(float(v.min()), 4) for v in all_vals],
            "max": [round(float(v.max()), 4) for v in all_vals],
            "mean": [round(float(v.mean()), 4) for v in all_vals],
            "time_source": "f06_TIME_markers",
            "note": "per-time-step temperature min/max/mean from the .f06 TEMPERATURE VECTOR blocks",
        }
    return payload


def _f06_convergence(text: str, sol: str, blocks: list[dict]) -> dict:
    """Honest convergence story for .f06: did the run complete its output tables?"""
    fatal = "FATAL" in text or "M O D E L   I N C O R R E C T" in text
    completed = len(blocks) > 0 and not fatal
    return {
        "source": "nastran_f06",
        "file": None,
        "substeps": len(blocks),
        "final_total_time": blocks[-1]["time"] if blocks else None,
        "monitors_last": [],
        "converged": None if fatal else completed,
        "note": (f"SOL {sol}: {len(blocks)} temperature-output time(s) present; "
                 + ("FATAL marker found" if fatal else "no fatal markers; output tables complete")
                 + " (Nastran .f06 carries no per-iteration residual history)"),
    }
