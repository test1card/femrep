"""femrep.extract — read a result file into results.json via the backend registry.

Dispatches by file suffix to the right adapter (.rst/.rth -> DPF; .f06 -> Nastran
text parser; .op2 -> pyNastran, guarded). Each adapter returns the same schema, so
govern/figures/render are solver-agnostic. This module is now a thin dispatcher;
the DPF core lives in backends/ansys_dpf.py.

Run:  python -m femrep.extract <result_file> [--log solve.out/.mntr] [--out results.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import backends


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(result_file: Path, solve_log: Path | None = None) -> dict:
    """Read one result file -> results dict (the report's data spine)."""
    adapter = backends.adapter_for(result_file.suffix)
    if adapter is None:
        raise ValueError(f"no backend for {result_file.suffix} "
                         f"(supported: {list(backends.REGISTRY)})")
    payload = adapter(result_file, solve_log)
    # envelope: provenance + timestamp on top of whatever the adapter returned
    payload.update({
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result_file": str(result_file),
        "result_sha256": sha256_of(result_file),
    })
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract a result file to JSON.")
    ap.add_argument("result_file", type=Path)
    ap.add_argument("--log", type=Path, default=None,
                    help="solve .mntr/.out (Ansys) or .log/.f06 convergence")
    ap.add_argument("--out", type=Path, default=Path("results.json"))
    args = ap.parse_args()
    if not args.result_file.exists():
        print(f"ERROR: {args.result_file} not found", flush=True)
        return 1
    payload = extract(args.result_file, args.log)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    q = payload.get("primary_qoi", {})
    tr = payload.get("transient")
    mesh = payload.get("mesh", {})
    et = mesh.get("element_types") or {}
    n_elem = sum(et.values()) if isinstance(et, dict) else mesh.get("elements", 0)
    suffix = f", TRANSIENT {tr['n_sets']} sets" if tr else ", single-set"
    print(f"[femrep.extract] {payload.get('solver_hint')} | "
          f"{mesh.get('nodes',0):,} nodes, {n_elem:,} elems{suffix}", flush=True)
    if q.get("name") and q["name"] != "n/a":
        print(f"  {q['name']}: {q['min']} -> {q['max']} {q['units']}", flush=True)
    print(f"  -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
