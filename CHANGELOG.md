# Changelog

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
