# Changelog

## v0.5.6

**Whole-class hardening for legacy Ansys (Codex + GLM 5.2 dual review).**

- **Critical:** `setuptools` must be pinned `<81` — setuptools ≥81 removed
  `pkg_resources`, so v0.5.5's bare `setuptools` still left it missing. Both
  installers now pin `setuptools<81`.
- **Multi-Ansys machines:** DPF 0.9 picks the newest installed Ansys (whose v8.0
  server a 0.9 client can't reach). `ansys_dpf` now starts an explicit LegacyGrpc
  server against the legacy install (`AWP_ROOT212/221/211`, or `ANSYS_DPF_PATH`)
  when a legacy Ansys is present; modern installs are untouched (fail-safe).
- `femrep diagnose` reports `ANSYS_DPF_PATH` and forces LegacyGrpc in its check.
- Installer warns that Ansys 2021 R1 (DPF 1.0) is a different bucket from 2021 R2.
- Verified non-issues (left as-is): protobuf/numpy floats (dpf 0.9 is pure-Python;
  modern stubs work), the inert `DPF_GRPC_MODE` env vars, and the DPF API surface.

## v0.5.5

**Fix: `No module named pkg_resources` on the legacy Ansys path.**

- `ansys-dpf-core` 0.9 imports `pkg_resources` (part of `setuptools`) but doesn't
  declare it, and modern venvs (uv / Python 3.12+) omit it. Both installers now
  install `setuptools`. `femrep diagnose` reports whether `pkg_resources` is present.

## v0.5.4

**Ansys 2021/2022R1 diagnostics.**

- New `femrep.diagnose` (`femrep diagnose [result.rst]` or
  `python -m femrep.diagnose`): reports Python + ansys-dpf-core versions, the
  installed Ansys (`AWP_ROOT*`), and — the real test — whether a local DPF server
  starts, with the full traceback on failure and version-specific hints.
- New `debug-ansys2021.bat`: runs the diagnostic against the installed env and
  saves it to a log; drag a `.rst` onto it to also test reading.

## v0.5.3

**Fix: GUI crashed silently at startup on old Ansys (lazy DPF import).**

- The backend registry imported `ansys.dpf` eagerly, so merely launching the GUI
  loaded `ansys-dpf-core`; with the legacy 0.9 build that import could abort and
  the windowed launcher closed with no message. The Ansys backend is now imported
  lazily — only when an `.rst`/`.rth` is actually read. The GUI and the `.f06`
  path no longer touch DPF.
- `main()` now logs any startup exception to `%LOCALAPPDATA%/femrep/femrep-crash.log`
  and shows it in a dialog. Added `femrep-debug.bat` to launch with a console.

## v0.5.2

**One-click Ansys 2021/2022R1 installer — gets its own Python 3.11.**

- New `install-ansys2021.bat`: fully automatic for legacy Ansys. It obtains an
  isolated Python 3.11 just for femrep (via the `py` launcher if present, else
  `uv` downloads a standalone build — the system Python is untouched), pins
  `ansys-dpf-core==0.9.0`, installs, and makes the desktop shortcut. No manual
  Python install needed.

## v0.5.1

**Ansys 2021 R1/R2 & 2022 R1 support (DPF v4.0 / LegacyGrpc).**

- These releases ship DPF server v4.0, which only works with `ansys-dpf-core`
  0.3–0.9 over LegacyGrpc — the latest DPF client cannot talk to them. The
  dependency lower bound is loosened to `>=0.9`, and `install.bat` now
  auto-detects an old Ansys (`AWP_ROOT211/212/221`) and pins
  `ansys-dpf-core==0.9.0`. Note: that DPF needs Python 3.10 or 3.11 (not 3.12+).
- Nastran `.f06` is unaffected — it never used DPF and works on any setup.

## v0.5.0

**Guided wizard GUI + Russian report in a real engineering register.**

- Rebuilt the desktop GUI as a polished 4-step wizard (Результат → Проверка →
  Шаблон → Экспорт), minimalist light theme. Step 1 is a universal attach zone
  (drop/multi-select; each file auto-classified результат/журнал/GCI/расчётная
  модель). Step 2 shows the femis gate verdicts in Russian as pastel badges.
  Step 3 has a live «Содержание отчёта» panel with per-section availability.
- GOST 7.32 Russian report: реферат / введение / заключение and section text
  rewritten in the Russian academic technical register (subject acts not author,
  density-as-ethics, no sales-pitch); fully Russian title page, units, solver line.
- Bug fixes from a Codex + GLM 5.2 dual review: GUI `.op2`→`.f06` fallback, GOST
  English title/solver-version leaks, optional (non-fatal) GUI figures, non-GCI
  `.json` misclassification, structural-`.f06` analysis label, реферат table count.

## v0.4.0

**ГОСТ 7.32-2017 — полностью русскоязычный отчёт (DOCX).**

- New `gost_ru` report profile: a dedicated Russian DOCX renderer
  (`report_gost_docx`) producing the ГОСТ 7.32-2017 structure — титульный лист,
  реферат (с автоподсчётом объёма полем NUMPAGES), содержание (поле TOC),
  введение, нумерованная основная часть, заключение. Formatting per the
  standard: Times New Roman 14, полуторный интервал, поля 30/15/20/20 мм,
  абзацный отступ 1.25 см, выравнивание по ширине, сквозная нумерация страниц.
- `locale_ru` Russian string layer: every label, verdict, and the auto-generated
  реферат/введение/заключение prose. A test enforces zero English label words.
- Template gains `profile` + ГОСТ титульный-лист fields (организация, УДК, город,
  год, руководители, вид отчёта). Select it in the GUI (Профиль) or CLI
  (`--profile gost_ru`); the English PDF/DOCX default is untouched.

## v0.3.0

**Report templates — build customized reports in the GUI.**

- New `femrep.templates` module: a per-project template model (branding / title
  block + section layout with per-section intro text), validation/repair of
  hand-edited files, and JSON persistence at `<project>/templates/<name>.json`.
- Both renderers refactored to a shared 9-section registry: a template selects,
  reorders, and annotates sections; numbering is dynamic. With no template the
  full report renders exactly as before (byte-for-byte default output).
- GUI: open/create a project, **Manage templates…** to create from scratch or
  seed from a result file, tick/reorder sections, edit branding, Save; pick a
  template from the report-screen dropdown before generating.
- CLI: `--template-file <name>.json`; batch runs accept `template_file`.

## v0.2.1

- Fix DPF `certs\ca.crt` mutual-TLS failure: default the local gRPC transport to
  insecure (`ansys-dpf-core` ≥ 0.15 / Ansys 2026 R1 require certs otherwise).
- Fix distributed-`.rst` misdetection: `file.rst` beside per-domain
  `file0.rst..fileN.rst` in a Workbench `dp0` folder is read directly; numbered
  multi-file sequences apply only to thermal `.rth`.

## v0.2.0

- Initial release: femis-governed Ansys/Nastran FEM report generator
  (PDF/DOCX), GCI study, project/run library, HTML review, desktop GUI.
- Windows double-click installer.
