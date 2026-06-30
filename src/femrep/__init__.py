"""femrep — femis-governed Ansys / Nastran FEM report generator.

Reporter only: ingests result files (.rst/.rth/.f06) and solver logs that
existing solve scripts already produce, then renders branded PDF + DOCX
reports. Never drives the solver (femis: governance layer, not the executor).

Layers (each reads the previous layer's JSON, each runnable standalone):
    extract.py  -> results.json   (backend registry; .rst/.rth via DPF, .f06 stdlib)
    govern.py   -> manifest.json + checks.json (femis governance + GCI)
    figures.py  -> *.png           (pyvista contour + matplotlib time-history)
    report_pdf.py / report_docx.py -> PDF / DOCX

Invoke:  femrep <result_file>                         (CLI)
         femrep-gui                                     (PySide6 desktop)
"""
__version__ = "0.6.0"
