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
just pretty: every number is tied to its deck + result via a run manifest,
phrased through public report language, and backed by a gates checklist that is
computed — never invented to "pass."

## Supported backends

| Format | Backend | Notes |
|---|---|---|
| Ansys `.rst` | DPF | structural: von-Mises stress, displacement, contour |
| Ansys `.rth` | DPF | thermal: temperature; multi-set transient sequences |
| Nastran `.f06` | stdlib parser | SOL 153/159 thermal, transient + steady |
| Nastran `.op2` | pyNastran (not wired yet) | fails loudly with a `.f06` companion hint |

## Quick start

```bash
# install (editable, from the repo)
pip install -e ".[gui]"

# CLI — any backend
femrep path/to/result.rst --log solve.mntr --out report.pdf --html --package
femrep path/to/result.f06 --out report.docx --template client
femrep doctor

# project/run library
femrep init DemoProject
femrep path/to/result.f06 --project femrep_projects/DemoProject --run-name run001 --html --package

# mesh convergence wizard: CSV with h,f or h,result columns
femrep gci grids.csv --out gci_runs.json --qoi peak_temperature_K

# batch mode: JSON with {"runs":[{"result":"...","out":"..."}]}
femrep batch runs.json

# bundled demo data
femrep examples/tiny_thermal.f06 --out demo_report.pdf --html --package
femrep gci examples/gci_points.csv --out demo_gci_runs.json --qoi demo_temperature
femrep batch examples/runs.json

# custom report template (branding + section layout)
femrep path/to/result.f06 --out report.pdf --template-file my_company.json

# desktop GUI (build + reuse templates visually)
femrep-gui
```

## Report templates

A **template** is a reusable report definition — branding / title block (logo,
company, customer, document number, colours, fonts) plus the **section layout**
(which of the nine sections appear, in what order, with optional per-section
intro text). Templates are per-project JSON files under
`<project>/templates/<name>.json`.

Build and reuse them in the GUI: open a project, then **Manage templates…** to
create one from scratch or **seed it from a result file**, tick/reorder
sections, fill in your branding, and Save. Pick it from the **Template** dropdown
before *Generate report*. From the CLI, pass `--template-file <name>.json`. With
no template, the full nine-section report renders exactly as before.

### Russian GOST report (ГОСТ 7.32-2017)

A template can set `profile: "gost_ru"` to emit a **fully Russian отчёт о НИР** as
DOCX, structured and formatted per ГОСТ 7.32-2017 (титульный лист, реферат,
содержание, введение, нумерованная основная часть, заключение; Times New Roman
14, полуторный интервал, поля 30/15/20/20 мм, сквозная нумерация). The реферат,
введение, and заключение are auto-generated from the results to minimize manual
editing. Select **Профиль → ГОСТ 7.32-2017** in the GUI, or:

```bash
femrep result.f06 --out отчёт.docx --profile gost_ru
```

The profile uses extra title-page fields (организация, УДК, город, год,
руководители) editable in the template. The English default profile is
unaffected.

Both renderers (PDF via reportlab, DOCX via python-docx) emit the same content:
cover, summary, readiness, model, meshing, composites/CFRP, solve +
convergence, results (contour + time-history figures), mesh-independence (GCI),
governance (gates + manifest). The optional HTML review includes the evidence
dashboard, figure gallery, and a rotatable PyVista contour viewer when geometry
is available.

## Architecture

```
result file (.rst/.rth/.f06)
      │  backends/ (one adapter per format — same results.json schema)
      ▼
   extract.py        → results.json
      │
      ▼  govern.py (femis): manifest + claim phrasing + gates + GCI + readiness
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

- **Issued-report language** on the cover; internal execution modes stay out of
  customer-facing PDFs/DOCX files.
- **Gates checklist** — units, connectivity, equilibrium/heat balance,
  convergence, singularity, mesh-independence (GCI) — each computed, never
  invented.
- **Evidence readiness** — complete/missing/blocked evidence is summarized before
  export so limitations stay visible.
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
- **`.op2`** is intentionally blocked until the binary adapter is wired. Use `.f06`;
  if a same-stem companion exists, femrep points to it instead of rendering an empty report.
- **Convergence** is read from Ansys `.mntr` (substep history) or `.f06` output
  tables. The corpus is linear thermal — no Newton-Raphson residual history, and
  the claim phrasing says so honestly.
- **Distributed `.rst`** — point femrep at the consolidated `file.rst` (e.g. in a
  Workbench `..._files/dp0/.../MECH/` folder). The per-domain `file0.rst..fileN.rst`
  written by a multi-core solve are *not* time steps; femrep reads the
  consolidated file directly and never expands those domains. Numbered transient
  sequences are an Ansys *thermal* (`.rth`) concept only.
- **DPF transport** — femrep runs DPF locally against your own Ansys install and
  forces an in-process / unsecured-gRPC channel (`DPF_GRPC_MODE=insecure`), so a
  single-machine run never needs the mutual-TLS certificates that `ansys-dpf-core`
  ≥ 0.15 (Ansys 2026 R1) require by default. Override the env var if you connect
  to a secured remote DPF server.

## License

Apache-2.0.
