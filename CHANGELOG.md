# Changelog

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
