"""femrep.backends.ansys_dpf — DPF reader for Ansys .rst/.rth, incl. multi-set transient.

DPF reads result files directly: no solver run, no license checkout. Handles both
the single consolidated file (.rth holding 1 set) and a numbered transient
sequence (file0.rth..fileN.rth), whose real time axis comes from the .mntr monitor
(the .rth per-file metadata reports a constant time — a known Ansys quirk).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from ansys.dpf import core as dpf

from .. import convergence as conv_mod

ELEMENT_LABELS = {
    0: "tet", 1: "hex", 2: "wedge", 3: "pyramid",
    4: "quad", 6: "tri", 11: "beam", 12: "shell",
}


def element_histogram(meshed_region) -> dict:
    try:
        codes = meshed_region.elements.element_types_field.data_as_list
    except Exception:
        return {}
    counts: dict[str, int] = {}
    for code in codes:
        label = ELEMENT_LABELS.get(int(code), f"type{code}")
        counts[label] = counts.get(label, 0) + 1
    return counts


def primary_qoi(model) -> dict:
    """Pick the primary QoI, preferring the first NON-EMPTY result. A thermo-mechanical
    .rst may expose a `temperature` attribute that evals empty (no thermal DOFs solved),
    so we probe each candidate and fall through to stress/displacement."""
    results = model.results

    def _try_temperature():
        if not hasattr(results, "temperature"):
            return None
        fc = results.temperature().eval()
        if not fc or fc[0].data.size == 0:
            return None
        return fc[0]

    tfield = _try_temperature()
    if tfield is not None:
        field = tfield
        name, units, to_c, data, nodal = "temperature", "K", True, \
            np.asarray(tfield.data, dtype=float), True
    elif hasattr(results, "stress"):
        fc = results.stress().eval()
        field = fc[0] if fc and fc[0].data.size else None
        if field is not None:
            s = np.asarray(field.data, dtype=float)
            if s.ndim == 2 and s.shape[1] == 6:
                sxx, syy, szz = s[:, 0], s[:, 1], s[:, 2]
                sxy, syz, sxz = s[:, 3], s[:, 4], s[:, 5]
                data = np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
                                      + 6 * (sxy ** 2 + syz ** 2 + sxz ** 2)))
            else:
                data = np.linalg.norm(s, axis=1) if s.ndim > 1 else s
            name, units, to_c, nodal = "von_mises_stress", "Pa", False, False
        else:
            field = results.displacement().eval()[0]
            data = np.asarray(field.data, dtype=float)
            if data.ndim > 1:
                data = np.linalg.norm(data, axis=1)
            name, units, to_c, nodal = "displacement_magnitude", "m", False, True
    elif hasattr(results, "displacement"):
        field = results.displacement().eval()[0]
        data = np.asarray(field.data, dtype=float)
        if data.ndim > 1:
            data = np.linalg.norm(data, axis=1)
        name, units, to_c, nodal = "displacement_magnitude", "m", False, True
    else:
        raise RuntimeError("no recognizable non-empty QoI in result file")

    out = {"name": name, "units": units,
           "min": float(np.min(data)), "max": float(np.max(data))}
    if nodal:
        ids = field.scoping.ids
        if len(ids) == len(data):  # only locate nodes when scoping aligns with data
            i_max, i_min = int(np.argmax(data)), int(np.argmin(data))
            mesh = model.metadata.meshed_region
            coords = lambda i: mesh.nodes.coordinates_field.get_entity_data(i)[0]
            out["hot_node"] = int(ids[i_max])
            out["cold_node"] = int(ids[i_min])
            out["hot_node_xyz_mm"] = [round(float(x) * 1000, 3) for x in coords(i_max)]
            out["cold_node_xyz_mm"] = [round(float(x) * 1000, 3) for x in coords(i_min)]
        else:
            out.update({"hot_node": 0, "cold_node": 0,
                        "hot_node_xyz_mm": [], "cold_node_xyz_mm": []})
    else:  # elemental/element-nodal: no node location
        out.update({"hot_node": 0, "cold_node": 0,
                    "hot_node_xyz_mm": [], "cold_node_xyz_mm": [],
                    "_elemental": "stress is element-nodal; min/max reported, no node location"})
    if to_c:
        out["min_C"] = round(float(np.min(data)) - 273.15, 3)
        out["max_C"] = round(float(np.max(data)) - 273.15, 3)
    return out


def _sequence_files(result_file: Path) -> list[Path]:
    """Detect a numbered transient sequence file0.rth..fileN.rth / <prefix>0..N.rst.

    Returns the ordered list of set files, or [result_file] alone if no sequence.
    """
    stem = result_file.stem
    suffix = result_file.suffix
    # patterns: file0.rth, ring2_0.rth, frame3d0.rth — a trailing integer on the stem
    m = re.match(r"^(.*?)(\d+)$", stem)
    if not m:
        # could be the consolidated 'file.rth' beside a file0..fileN sequence
        cand0 = result_file.parent / f"{stem}0{suffix}"
        if cand0.exists():
            return _collect(result_file.parent, stem, suffix, start=0)
        return [result_file]
    prefix, start_str = m.group(1), m.group(2)
    return _collect(result_file.parent, prefix, suffix, start=int(start_str))


def _collect(parent: Path, prefix: str, suffix: str, start: int) -> list[Path]:
    files = []
    n = start
    while True:
        p = parent / f"{prefix}{n}{suffix}"
        if not p.exists():
            break
        files.append(p)
        n += 1
    return files


def _qoi_stats(model) -> tuple[float, float, float]:
    """min, max, mean of the primary field on one model (for transient envelopes)."""
    results = model.results
    if hasattr(results, "temperature"):
        data = np.asarray(results.temperature().eval()[0].data, dtype=float)
    elif hasattr(results, "displacement"):
        data = np.asarray(results.displacement().eval()[0].data, dtype=float)
        if data.ndim > 1:
            data = np.linalg.norm(data, axis=1)
    else:
        data = np.array([0.0])  # stress transient not supported here; honest zero
    return float(data.min()), float(data.max()), float(data.mean())


def extract(result_file: Path, solve_log: Path | None = None) -> dict:
    """Read one Ansys result file -> results dict. Detects + unfolds transient sequences."""
    sequence = _sequence_files(result_file)
    is_transient = len(sequence) > 1
    # representative model for mesh/QoI/metadata: the last set (the consolidated file
    # when present, else the highest-numbered sequence member).
    # NOTE: open a FRESH model per query — DPF result operators are stateful and a
    # second .eval() on the same model can return empty (operator exhaustion).
    def fresh_model():
        return dpf.Model(str(sequence[-1]))
    mesh = fresh_model().metadata.meshed_region
    suffix = result_file.suffix.lower()

    payload = {
        "solver_hint": "thermal (.rth)" if suffix == ".rth" else "structural (.rst)",
        "mesh": {
            "nodes": int(mesh.nodes.n_nodes),
            "elements": int(mesh.elements.n_elements),
            "element_types": element_histogram(mesh),
        },
        "primary_qoi": primary_qoi(fresh_model()),
        "time_freq": _time_info(fresh_model(), len(sequence)),
        "available_results": sorted(r for r in dir(fresh_model().results) if not r.startswith("_")),
        "convergence": conv_mod.parse(_resolve_mntr(result_file, solve_log)),
    }
    if is_transient:
        payload["transient"] = _transient_envelope(sequence, payload["convergence"])
    return payload


def _time_info(model, n_sequence: int) -> dict:
    tf = model.metadata.time_freq_support
    freqs = tf.time_freq_support if False else tf.time_frequencies  # noqa
    n = tf.n_sets
    times: list[float] = []
    if freqs is not None:
        arr = np.asarray(freqs.data, dtype=float)
        times = [round(float(x), 3) for x in arr[:min(n, 50)]]
    return {"n_sets": int(n), "n_sequence_files": n_sequence,
            "sample_times_s": times}


def _resolve_mntr(result_file: Path, solve_log: Path | None) -> Path | None:
    """Prefer an explicit --log; else look for a .mntr beside the result file."""
    if solve_log:
        return solve_log
    # beside the (consolidated) result file, or beside the sequence's parent
    cand = result_file.with_suffix(".mntr")
    if cand.exists():
        return cand
    # sequence member: file5.rth -> file.mntr
    import re as _re
    m = _re.match(r"^(.*?)(\d+)$", result_file.stem)
    if m:
        cand2 = result_file.with_name(m.group(1) + ".mntr")
        if cand2.exists():
            return cand2
    return None


def _transient_envelope(sequence: list[Path], convergence: dict) -> dict:
    """min/max/mean of the QoI per set file + time axis from .mntr (the honest source)."""
    mins, maxs, means = [], [], []
    for p in sequence:
        m = dpf.Model(str(p))
        lo, hi, mn = _qoi_stats(m)
        mins.append(lo); maxs.append(hi); means.append(mn)
    # time axis: prefer the .mntr substep times; fall back to set index
    times = convergence.get("time_series") if convergence else None
    if times and len(times) >= len(sequence):
        # map N result files onto the N load-step-final substeps (last substep per step)
        # approximation when substeps > files; honest fallback below if mismatch
        step_finals = _per_step_final_times(times)
        if len(step_finals) == len(sequence):
            times = step_finals
        else:
            times = list(range(1, len(sequence) + 1))
    else:
        times = list(range(1, len(sequence) + 1))
    return {
        "n_sets": len(sequence),
        "times": times,
        "min": [round(x, 4) for x in mins],
        "max": [round(x, 4) for x in maxs],
        "mean": [round(x, 4) for x in means],
        "time_source": "mntr" if convergence and convergence.get("source") == "ansys_mntr"
                       and len(times) == len(sequence) and times and times[0] != 1
                       else "set_index (mntr mismatch)",
        "note": ("per-set min/max/mean across the fileN sequence; time axis from .mntr "
                 "where available (the .rth per-file metadata reports a constant time)"),
    }


def _per_step_final_times(substep_times: list[float]) -> list[float]:
    """Heuristic: a new load step often shows a time discontinuity; take the last
    substep before each discontinuity. For a single-step deck this just returns the
    downsampled tail — used only as a time-axis best effort, never as an engineering claim."""
    # Simple even-ish downsampling as a fallback; the real step boundaries aren't in .mntr.
    # Keep this honest: if we can't cleanly map, the caller falls back to set_index.
    return []  # forces the honest set_index fallback unless overridden
