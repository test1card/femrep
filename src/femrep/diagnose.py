"""femrep.diagnose — environment + DPF connectivity check, focused on Ansys/DPF.

Aimed at the Ansys 2021 R1/R2 & 2022 R1 case: those ship DPF server v4.0, which
only works with ansys-dpf-core 0.3-0.9 over LegacyGrpc on Python 3.10/3.11. This
script reports the versions, the installed Ansys, and — the real test — whether a
local DPF server actually starts, with the full traceback on failure.

Run:  python -m femrep.diagnose [optional path\\to\\result.rst]
It never raises itself; every check is guarded.
"""
from __future__ import annotations

import os
import platform
import sys
import traceback
from pathlib import Path


def _version(pkg: str) -> str:
    try:
        from importlib.metadata import version
        return version(pkg)
    except Exception as e:
        return f"? ({e})"


def _indent(text: str, n: int = 3) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in text.rstrip().splitlines())


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print("=" * 60)
    print(" femrep diagnostics — Ansys / DPF")
    print("=" * 60)
    print(f"Python         : {sys.version.split()[0]} {platform.architecture()[0]}")
    print(f"Executable     : {sys.executable}")
    print(f"femrep         : {_version('femrep')}")
    print(f"ansys-dpf-core : {_version('ansys-dpf-core')}")

    roots = sorted(k for k in os.environ if k.startswith("AWP_ROOT"))
    if roots:
        for k in roots:
            print(f"Ansys install  : {k} -> {os.environ[k]}")
    else:
        print("Ansys install  : no AWP_ROOT* found — Ansys not detected for this account")
    if any(k in ("AWP_ROOT211", "AWP_ROOT212", "AWP_ROOT221") for k in roots):
        print("Expected DPF   : v4.0 / LegacyGrpc (Ansys 2021-2022R1) —"
              " needs ansys-dpf-core 0.3-0.9 on Python 3.10/3.11")
    pyminor = sys.version_info[:2]
    if pyminor > (3, 11):
        print(f"WARNING        : Python {pyminor[0]}.{pyminor[1]} is too new for the"
              " legacy DPF (0.9). Use Python 3.10 or 3.11 for Ansys 2021/2022R1.")

    print("-" * 60)
    print("Importing ansys.dpf.core ...")
    try:
        from ansys.dpf import core as dpf
        print("  import OK")
    except Exception:
        print("  import FAILED:")
        print(_indent(traceback.format_exc()))
        print("\n=> ansys-dpf-core is not importable. For Ansys 2021/2022R1 install"
              " ansys-dpf-core==0.9.0 on Python 3.10/3.11 (install-ansys2021.bat).")
        return 1

    print("Starting a local DPF server (the real Ansys<->DPF check) ...")
    try:
        try:
            srv = dpf.start_local_server(timeout=60)
        except TypeError:
            srv = dpf.start_local_server()
        print("  DPF server STARTED")
        for attr in ("version", "ansys_path", "config"):
            try:
                val = getattr(srv, attr, None)
                if val is not None:
                    print(f"  {attr}: {val}")
            except Exception:
                pass
    except Exception:
        print("  DPF server FAILED to start:")
        print(_indent(traceback.format_exc()))
        print("\n=> The server could not start. On Ansys 2021/2022R1 this is usually a"
              " version mismatch: ansys-dpf-core must be 0.3-0.9 and Python 3.10/3.11.")
        return 1

    result = next((a for a in argv if not a.startswith("-")), None)
    if result:
        print("-" * 60)
        print(f"Reading {result} through femrep ...")
        try:
            from . import extract as extract_mod
            payload = extract_mod.extract(Path(result))
            q = payload.get("primary_qoi", {})
            print(f"  OK — {q.get('name')} in [{q.get('min')}, {q.get('max')}] {q.get('units')}")
        except Exception:
            print("  FAILED:")
            print(_indent(traceback.format_exc()))
            return 1

    print("=" * 60)
    print("All checks passed — DPF works in this environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
