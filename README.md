# femrep — femis-governed FEM report generator

Turns Ansys / Nastran result files (`.rst`, `.rth`, `.f06`) into **defensible,
standardized engineering reports** (PDF + DOCX). Reporter only — it ingests
results your solve scripts already produce; it never drives the solver.

Governed by [femis](https://github.com/test1card/femis-skill) (engineering claim
discipline, provenance, gates, no autonomous sign-off) and disciplined by
[ponytail](https://github.com/DietrichGebert/ponytail) (minimalism / YAGNI).

## Why it exists

A "beautiful" CAE report that omits provenance, gate verdicts, and honest claim
phrasing is *worse than a plain one* — it looks authoritative while being
untrustworthy. femrep is the thin layer that makes a report **defensible**, not
just pretty: every number is tied to its deck + result via a run manifest, phrased
at the altitude its execution mode (SMOKE/DEBUG/ENGINEERING/SIGNOFF) earns, and
backed by a gates checklist that is computed — never invented to "pass."

## Supported backends

| Format | Backend | Notes |
|---|---|---|
| Ansys `.rst` | DPF | structural: von-Mises stress, displacement, contour |
| Ansys `.rth` | DPF | thermal: temperature; multi-set transient sequences |
| Nastran `.f06` | stdlib parser | SOL 153/159 thermal, transient + steady |
| Nastran `.op2` | pyNastran (gated) | falls back to `.f06` if pyNastran unavailable |

## Quick start

```bash
# install (editable, from the repo)
pip install -e ".[gui]"

# CLI — any backend
femrep path/to/result.rst --mode ENGINEERING --log solve.mntr --out report.pdf
femrep path/to/result.f06 --mode ENGINEERING --out report.docx

# desktop GUI
femrep-gui
```

Both renderers (PDF via reportlab, DOCX via python-docx) emit the same content:
cover, summary (mode-correct claim), model, meshing, composites/CFRP, solve +
convergence, results (contour + time-history figures), mesh-independence (GCI),
governance (gates + manifest).

## Architecture

```
result file (.rst/.rth/.f06)
      │  backends/ (one adapter per format — same results.json schema)
      ▼
   extract.py        → results.json
      │
      ▼  govern.py (femis): manifest + execution-mode label + claim phrasing + gates + GCI
   manifest.json + checks.json
      │
      ▼  figures.py: pyvista contour + matplotlib time-history
   *.png
      │
      ▼  report_pdf.py / report_docx.py
   report.pdf / report.docx
```

Each layer reads the previous layer's JSON and is runnable standalone — the
repo's incremental `stage()` philosophy.

## femis governance, enforced

- **Execution-mode label** on the cover; claim phrased via the mode's template.
- **Gates checklist** — units, connectivity, equilibrium/heat balance,
  convergence, singularity, mesh-independence (GCI) — each computed, never
  invented. A SMOKE solve printed as "the stress is 180 MPa" is a lie even if the
  number is right.
- **Run manifest** — solver + version, deck + result SHA-256, command line, units,
  mesh, material sources. NAFEMS R0033 traceability spine.
- **No autonomous sign-off** — femrep *assembles evidence*; a qualified engineer
  *accepts* it.

## Composites / CFRP

No ACP/CFRP data ships with the project. The composite section renders a
synthetic `[0/90/0]` T300/5208 CLT validation case (`cases/clt_synthetic.py`) —
ABD matrix, B≈0 (symmetric), Tsai-Wu first-ply-failure — so the section's
governance (failure philosophy, mesh-objectivity regularization, as-draped
angles) is demonstrated. Real ACP/`.rmed` data is wired when supplied.

## Honest limitations

- **Reporter only** — no solver orchestration. GCI ingests 3 pre-run results.
- **`.op2`** requires pyNastran, which does not build on Python 3.14; use `.f06`.
- **Convergence** is read from Ansys `.mntr` (substep history) or `.f06` output
  tables. The corpus is linear thermal — no Newton-Raphson residual history, and
  the claim phrasing says so honestly.

## License

Apache-2.0.
