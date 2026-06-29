"""femrep.gui — PySide6 desktop app for the report generator.

Single window: pick a result file (and optional log/deck/GCI), choose a mode,
extract -> preview the contour + gate verdicts -> render PDF or DOCX.

The pipeline (extract/govern/figures/render) runs in a QThread worker because
DPF reads + pyvista rendering of 288MB+ files take 10–60s and must not freeze
the UI. Launch:  python -m femrep.gui
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QRadioButton, QScrollArea,
                               QSplitter, QTextEdit, QVBoxLayout, QWidget)

from . import extract as extract_mod
from . import govern, cli as cli_mod
from . import report_pdf, report_docx

MODES = govern.MODES
HERE = Path(__file__).parent


class PipelineWorker(QThread):
    """Runs extract -> govern (-> figures) off the UI thread. Emits progress + result."""
    progress = Signal(str)
    finished_ok = Signal(dict)   # carries results/manifest/checks/figures
    failed = Signal(str)

    def __init__(self, result_file: Path, mode: str, log: Path | None,
                 deck: Path | None, gci: Path | None, out_dir: Path,
                 gen_figures: bool):
        super().__init__()
        self.result_file, self.mode = result_file, mode
        self.log, self.deck, self.gci = log, deck, gci
        self.out_dir, self.gen_figures = out_dir, gen_figures

    def run(self):
        try:
            self.progress.emit("extracting…")
            results = extract_mod.extract(self.result_file, self.log)
            (self.out_dir / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8")

            self.progress.emit("governing…")
            gci = govern.run_gci(json.loads(self.gci.read_text(encoding="utf-8"))) \
                if self.gci and self.gci.exists() else None
            manifest = govern.build_manifest(results, self.mode, deck_path=self.deck)
            gates = govern.evaluate_gates(results, self.mode, manifest, gci)
            claim = govern.phrase_claim(self.mode, results, gci)
            (self.out_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8")
            checks = {"mode": self.mode, "claim": claim, "gates": gates, "gci": gci}
            (self.out_dir / "checks.json").write_text(
                json.dumps(checks, indent=2), encoding="utf-8")

            figures = {}
            if self.gen_figures:
                self.progress.emit("rendering figures…")
                from . import figures as fig_mod
                figures = fig_mod.generate(results, gci, self.out_dir)

            self.finished_ok.emit({"results": results, "manifest": manifest,
                                   "checks": checks, "figures": figures})
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}")


class FemrepWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("femrep — femis-governed FEM report generator")
        self.resize(1100, 760)
        self.worker: PipelineWorker | None = None
        self.last_payload: dict | None = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        # --- input row ---
        inp = QHBoxLayout()
        self.btn_result = QPushButton("Pick result file…")
        self.btn_result.clicked.connect(self._pick_result)
        self.lbl_result = QLabel("no file selected")
        self.lbl_result.setStyleSheet("color:#868e96;")
        inp.addWidget(self.btn_result); inp.addWidget(self.lbl_result, 1)
        outer.addLayout(inp)

        # log / deck / gci (optional, compact)
        opts = QHBoxLayout()
        self.btn_log = QPushButton("log (.mntr/.out)…"); self.btn_log.clicked.connect(self._pick_log)
        self.lbl_log = QLabel("—"); self.lbl_log.setStyleSheet("color:#868e96;")
        self.btn_gci = QPushButton("gci_runs.json…"); self.btn_gci.clicked.connect(self._pick_gci)
        self.lbl_gci = QLabel("—"); self.lbl_gci.setStyleSheet("color:#868e96;")
        opts.addWidget(self.btn_log); opts.addWidget(self.lbl_log, 1)
        opts.addWidget(self.btn_gci); opts.addWidget(self.lbl_gci, 1)
        outer.addLayout(opts)

        # mode + run
        row = QHBoxLayout()
        row.addWidget(QLabel("Execution mode:"))
        self.cmb_mode = QComboBox(); self.cmb_mode.addItems(MODES); self.cmb_mode.setCurrentText("ENGINEERING")
        row.addWidget(self.cmb_mode)
        self.chk_figs = QRadioButton("with figures"); self.chk_figs.setChecked(True)
        row.addWidget(self.chk_figs)
        self.btn_run = QPushButton("Extract + govern"); self.btn_run.clicked.connect(self._run)
        self.btn_run.setDefault(True)
        row.addWidget(self.btn_run); row.addStretch()
        outer.addLayout(row)

        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.lbl_status = QLabel("")
        outer.addWidget(self.progress); outer.addWidget(self.lbl_status)

        # --- splitter: preview | status/gates ---
        split = QSplitter(Qt.Horizontal)

        self.preview = QLabel("contour preview appears here after extract")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#f8f9fa; border:1px solid #dee2e6;")
        self.preview.setMinimumWidth(420)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.preview)
        split.addWidget(scroll)

        self.txt_status = QTextEdit(); self.txt_status.setReadOnly(True)
        self.txt_status.setFont(QFont("Consolas", 9))
        split.addWidget(self.txt_status)
        split.setSizes([560, 480])
        outer.addWidget(split, 1)

        # --- render row ---
        rr = QHBoxLayout()
        self.rb_pdf = QRadioButton("PDF"); self.rb_pdf.setChecked(True)
        self.rb_docx = QRadioButton("DOCX")
        rr.addWidget(QLabel("Render:")); rr.addWidget(self.rb_pdf); rr.addWidget(self.rb_docx)
        self.btn_render = QPushButton("Generate report"); self.btn_render.clicked.connect(self._render)
        self.btn_render.setEnabled(False)
        rr.addStretch(); rr.addWidget(self.btn_render)
        outer.addLayout(rr)

    # --- pickers ---
    def _pick_result(self):
        p, _ = QFileDialog.getOpenFileName(self, "Result file", "",
                                           "Results (*.rst *.rth *.f06 *.op2);;All (*.*)")
        if p:
            self.result_file = Path(p); self.lbl_result.setText(p); self.lbl_result.setStyleSheet("")

    def _pick_log(self):
        p, _ = QFileDialog.getOpenFileName(self, "Solve log", "",
                                           "Logs (*.mntr *.out *.log *.f06);;All (*.*)")
        if p:
            self.log_file = Path(p); self.lbl_log.setText(Path(p).name)

    def _pick_gci(self):
        p, _ = QFileDialog.getOpenFileName(self, "GCI runs", "", "JSON (*.json)")
        if p:
            self.gci_file = Path(p); self.lbl_gci.setText(Path(p).name)

    # --- run ---
    def _run(self):
        if not hasattr(self, "result_file"):
            QMessageBox.warning(self, "femrep", "Pick a result file first.")
            return
        self.out_dir = Path.cwd() / "femrep_out" / self.result_file.stem
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.btn_run.setEnabled(False); self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.lbl_status.setText("running…"); self.txt_status.clear()
        self.worker = PipelineWorker(
            self.result_file, self.cmb_mode.currentText(),
            getattr(self, "log_file", None), None,
            getattr(self, "gci_file", None), self.out_dir, self.chk_figs.isChecked())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_progress(self, msg):
        self.lbl_status.setText(msg)

    def _on_done(self, payload):
        self.last_payload = payload
        self.progress.setVisible(False); self.btn_run.setEnabled(True)
        self.btn_render.setEnabled(True)
        # preview contour
        figs = payload["figures"]
        cp = figs.get("contour")
        if cp and Path(cp).exists():
            pix = QPixmap(str(cp))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaledToWidth(540, Qt.SmoothTransformation))
        else:
            self.preview.setText("no contour (e.g. .f06 has no geometry) — see time-history in the report")
        # gate status pane
        self._render_status(payload)

    def _render_status(self, payload):
        checks = payload["checks"]; results = payload["results"]; manifest = payload["manifest"]
        q = results["primary_qoi"]
        lines = [f"<b>{manifest['solver']} {manifest.get('solver_version','')}</b>",
                 f"<b>QoI:</b> {q['name']} = {q['min']} .. {q['max']} {q['units']}",
                 f"<b>Mode:</b> {checks['mode']}", "",
                 "<b>Gates (femis):</b>"]
        for g in checks["gates"]:
            color = {"pass": "#2b8a3e", "fail": "#c92a2a", "not_done": "#868e96"}[g["verdict"]]
            sym = {"pass": "✓", "fail": "✗", "not_done": "—"}[g["verdict"]]
            lines.append(f"<font color='{color}'><b>{sym} {g['gate']}</b></font> — {g['note']}")
        lines += ["", "<b>Claim:</b>", checks["claim"]]
        if checks.get("gci"):
            gi = checks["gci"]
            lines += ["", f"<b>GCI:</b> fine {gi['gci_fine_pct']:.3f}%, R {gi['convergence_ratio_R']:.3f}, "
                          f"p {gi['observed_order_p']:.2f}", gi["verdict"]]
        self.txt_status.setHtml("<br>".join(lines))
        self.lbl_status.setText("done — review gates, then Generate report")

    def _on_fail(self, msg):
        self.progress.setVisible(False); self.btn_run.setEnabled(True)
        self.lbl_status.setText("FAILED")
        self.txt_status.setPlainText(msg)

    # --- render ---
    def _render(self):
        if not self.last_payload:
            return
        ext = ".pdf" if self.rb_pdf.isChecked() else ".docx"
        p, _ = QFileDialog.getSaveFileName(self, "Save report",
                                           str(self.out_dir / ("report" + ext)),
                                           f"Report (*{ext})")
        if not p:
            return
        cfg = cli_mod._load_config(HERE / "config.yaml")
        from datetime import datetime
        meta = {"generated": datetime.now().isoformat(timespec="seconds")}
        try:
            if ext == ".docx":
                report_docx.render(self.last_payload["results"], self.last_payload["manifest"],
                                   self.last_payload["checks"], cfg,
                                   self.last_payload["figures"], meta, Path(p))
            else:
                report_pdf.render(self.last_payload["results"], self.last_payload["manifest"],
                                  self.last_payload["checks"], cfg,
                                  self.last_payload["figures"], meta, Path(p))
            self.lbl_status.setText(f"report saved -> {p}")
            QMessageBox.information(self, "femrep", f"Report saved:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "femrep", f"Render failed:\n{e}\n{traceback.format_exc()[-600:]}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("femrep")
    win = FemrepWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
