"""femrep.gui — PySide6 desktop app for the report generator.

Single window: pick a result file (and optional log/deck/GCI),
extract -> preview the contour + gate verdicts -> render PDF or DOCX.

The pipeline (extract/govern/figures/render) runs in a QThread worker because
DPF reads + pyvista rendering of 288MB+ files take 10–60s and must not freeze
the UI. Launch:  python -m femrep.gui
"""
from __future__ import annotations

import json
import sys
import traceback
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QRadioButton,
                               QScrollArea, QSplitter, QTextEdit, QVBoxLayout, QWidget)

from . import extract as extract_mod
from . import govern, cli as cli_mod
from . import report_pdf, report_docx
from . import templates as templates_mod
from . import workflow

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
            claim = govern.phrase_claim(self.mode, results, gci, gates)
            readiness = govern.evaluate_readiness(results, manifest, gates, gci)
            (self.out_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8")
            checks = {"mode": self.mode, "claim": claim, "gates": gates,
                      "gci": gci, "readiness": readiness}
            (self.out_dir / "checks.json").write_text(
                json.dumps(checks, indent=2), encoding="utf-8")

            figures = {}
            if self.gen_figures:
                self.progress.emit("rendering figures…")
                from . import figures as fig_mod
                figures = fig_mod.generate(results, gci, self.out_dir)
            review_html = workflow.render_html_review(results, manifest, checks, figures, self.out_dir)

            self.finished_ok.emit({"results": results, "manifest": manifest,
                                   "checks": checks, "figures": figures,
                                   "review_html": review_html})
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}")


class FemrepWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("femrep — femis-governed FEM report generator")
        self.resize(1100, 760)
        self.worker: PipelineWorker | None = None
        self.last_payload: dict | None = None
        self.report_mode = "SIGNOFF"
        self.project: Path | None = None
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

        # run controls
        row = QHBoxLayout()
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

        # --- template row: project + report template ---
        tr = QHBoxLayout()
        self.btn_project = QPushButton("Project…")
        self.btn_project.clicked.connect(self._pick_project)
        self.btn_project.setToolTip("Open or create a femrep project folder that holds your templates")
        self.lbl_project = QLabel("(no project — built-in layout)")
        self.lbl_project.setStyleSheet("color:#868e96;")
        self.cmb_template = QComboBox()
        self.cmb_template.addItem("Built-in default")
        self.btn_manage = QPushButton("Manage templates…")
        self.btn_manage.clicked.connect(self._manage_templates)
        self.btn_manage.setEnabled(False)
        tr.addWidget(self.btn_project); tr.addWidget(self.lbl_project, 1)
        tr.addWidget(QLabel("Template:")); tr.addWidget(self.cmb_template, 1)
        tr.addWidget(self.btn_manage)
        outer.addLayout(tr)

        # --- render row ---
        rr = QHBoxLayout()
        self.rb_pdf = QRadioButton("PDF"); self.rb_pdf.setChecked(True)
        self.rb_docx = QRadioButton("DOCX")
        rr.addWidget(QLabel("Render:")); rr.addWidget(self.rb_pdf); rr.addWidget(self.rb_docx)
        self.btn_render = QPushButton("Generate report"); self.btn_render.clicked.connect(self._render)
        self.btn_render.setEnabled(False)
        self.btn_review = QPushButton("Open review"); self.btn_review.clicked.connect(self._open_review)
        self.btn_review.setEnabled(False)
        rr.addStretch(); rr.addWidget(self.btn_review); rr.addWidget(self.btn_render)
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

    # --- project / templates ---
    def _pick_project(self):
        d = QFileDialog.getExistingDirectory(self, "Open or create a femrep project folder")
        if not d:
            return
        self.project = Path(d)
        templates_mod.templates_dir(self.project).mkdir(parents=True, exist_ok=True)
        self.lbl_project.setText(str(self.project)); self.lbl_project.setStyleSheet("")
        self.btn_manage.setEnabled(True)
        self._refresh_templates()

    def _refresh_templates(self, select: str | None = None):
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        self.cmb_template.addItem("Built-in default")
        if self.project:
            for name in templates_mod.list_templates(self.project):
                self.cmb_template.addItem(name)
        if select:
            i = self.cmb_template.findText(select)
            if i >= 0:
                self.cmb_template.setCurrentIndex(i)
        self.cmb_template.blockSignals(False)

    def _manage_templates(self):
        if not self.project:
            QMessageBox.information(self, "femrep", "Open a project first to store templates.")
            return
        dlg = TemplateDialog(self.project, self.last_payload, self)
        dlg.exec()
        self._refresh_templates(select=dlg.saved_name)

    def _selected_cfg(self):
        """Base config.yaml, overlaid with the selected project template (if any)."""
        cfg = cli_mod._load_config(HERE / "config.yaml")
        name = self.cmb_template.currentText()
        if self.project and name and name != "Built-in default":
            try:
                tpl = templates_mod.load_template(self.project, name)
                cfg.update(templates_mod.to_config(tpl))
            except (FileNotFoundError, ValueError) as e:
                QMessageBox.warning(self, "femrep", f"Could not load template {name!r}: {e}")
        return cfg

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
            self.result_file, self.report_mode,
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
        self.btn_review.setEnabled(bool(payload.get("review_html")))
        # preview contour
        figs = payload["figures"]
        cp = figs.get("contour_views") or figs.get("contour")
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
                 f"<b>Report:</b> {checks.get('readiness', {}).get('summary', 'issued engineering report')}", "",
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

    def _open_review(self):
        if self.last_payload and self.last_payload.get("review_html"):
            webbrowser.open(Path(self.last_payload["review_html"]).resolve().as_uri())

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
        cfg = self._selected_cfg()
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


class TemplateDialog(QDialog):
    """Create / edit / save per-project report templates: branding fields + a
    checkable, reorderable section list with per-section intro text. All logic
    lives in femrep.templates; this is a thin editor over it."""

    def __init__(self, project: Path, last_payload: dict | None = None, parent=None):
        super().__init__(parent)
        self.project = project
        self.last_payload = last_payload
        self.saved_name: str | None = None
        self.sec_intro: dict[str, str] = {}
        self.setWindowTitle("femrep — report templates")
        self.resize(820, 620)
        self._build()
        self._reload_list()

    def _build(self):
        outer = QHBoxLayout(self)

        # left: template list + actions
        left = QVBoxLayout()
        self.lst = QListWidget()
        self.lst.currentTextChanged.connect(self._on_pick)
        left.addWidget(QLabel("Templates in this project:"))
        left.addWidget(self.lst, 1)
        for label, slot in [("New blank", self._new_blank),
                            ("New from result…", self._new_from_result),
                            ("Duplicate", self._duplicate),
                            ("Delete", self._delete)]:
            b = QPushButton(label); b.clicked.connect(slot); left.addWidget(b)
        outer.addLayout(left, 1)

        # right: edit form
        right = QVBoxLayout()
        form_host = QWidget(); form = QFormLayout(form_host)
        self.f_name = QLineEdit()
        form.addRow("Name", self.f_name)
        self.brand_fields: dict[str, QLineEdit] = {}
        for key in templates_mod.DEFAULT_BRANDING:
            le = QLineEdit()
            self.brand_fields[key] = le
            if key == "logo":
                row = QHBoxLayout(); row.addWidget(le, 1)
                browse = QPushButton("…"); browse.setFixedWidth(28)
                browse.clicked.connect(self._pick_logo); row.addWidget(browse)
                host = QWidget(); host.setLayout(row); form.addRow(key, host)
            else:
                form.addRow(key, le)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(form_host)
        right.addWidget(QLabel("Branding / title block:")); right.addWidget(scroll, 2)

        right.addWidget(QLabel("Sections (tick to include, drag-free reorder with ↑/↓):"))
        self.lst_sec = QListWidget()
        self.lst_sec.currentRowChanged.connect(self._on_section_pick)
        right.addWidget(self.lst_sec, 2)
        secbtns = QHBoxLayout()
        for label, slot in [("↑", lambda: self._move_section(-1)),
                            ("↓", lambda: self._move_section(1))]:
            b = QPushButton(label); b.setFixedWidth(36); b.clicked.connect(slot); secbtns.addWidget(b)
        secbtns.addWidget(QLabel("Intro:"))
        self.f_intro = QLineEdit(); self.f_intro.setPlaceholderText("optional text under this section heading")
        self.f_intro.textEdited.connect(self._on_intro_edit)
        secbtns.addWidget(self.f_intro, 1)
        right.addLayout(secbtns)

        save = QPushButton("Save template"); save.clicked.connect(self._save)
        right.addWidget(save)
        outer.addLayout(right, 2)

    # --- list handling ---
    def _reload_list(self, select: str | None = None):
        self.lst.blockSignals(True)
        self.lst.clear()
        self.lst.addItems(templates_mod.list_templates(self.project))
        self.lst.blockSignals(False)
        if select:
            items = self.lst.findItems(select, Qt.MatchExactly)
            if items:
                self.lst.setCurrentItem(items[0])

    def _on_pick(self, name: str):
        if name:
            try:
                self._load_into_form(templates_mod.load_template(self.project, name))
            except (FileNotFoundError, ValueError):
                pass

    # --- form <-> template ---
    def _load_into_form(self, tpl: dict):
        tpl = templates_mod.validate(tpl)
        self.f_name.setText(tpl["name"])
        for key, le in self.brand_fields.items():
            val = tpl["branding"].get(key)
            le.setText("" if val is None else str(val))
        self.sec_intro = {s["key"]: s.get("intro", "") for s in tpl["sections"]}
        self.lst_sec.clear()
        for s in tpl["sections"]:
            item = QListWidgetItem(templates_mod.SECTION_TITLES[s["key"]])
            item.setData(Qt.UserRole, s["key"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if s["enabled"] else Qt.Unchecked)
            self.lst_sec.addItem(item)
        if self.lst_sec.count():
            self.lst_sec.setCurrentRow(0)

    def _collect(self) -> dict:
        branding = {}
        for key, le in self.brand_fields.items():
            text = le.text().strip()
            branding[key] = (None if (key == "logo" and not text) else text)
        sections = []
        for i in range(self.lst_sec.count()):
            item = self.lst_sec.item(i)
            key = item.data(Qt.UserRole)
            sections.append({"key": key, "enabled": item.checkState() == Qt.Checked,
                             "intro": self.sec_intro.get(key, "")})
        return {"femrep_template_version": templates_mod.TEMPLATE_VERSION,
                "name": self.f_name.text().strip() or "Untitled",
                "branding": branding, "sections": sections}

    # --- section editing ---
    def _on_section_pick(self, row: int):
        if 0 <= row < self.lst_sec.count():
            key = self.lst_sec.item(row).data(Qt.UserRole)
            self.f_intro.setText(self.sec_intro.get(key, ""))

    def _on_intro_edit(self, text: str):
        row = self.lst_sec.currentRow()
        if 0 <= row < self.lst_sec.count():
            self.sec_intro[self.lst_sec.item(row).data(Qt.UserRole)] = text

    def _move_section(self, delta: int):
        row = self.lst_sec.currentRow()
        new = row + delta
        if 0 <= row < self.lst_sec.count() and 0 <= new < self.lst_sec.count():
            item = self.lst_sec.takeItem(row)
            self.lst_sec.insertItem(new, item)
            self.lst_sec.setCurrentRow(new)

    # --- actions ---
    def _pick_logo(self):
        p, _ = QFileDialog.getOpenFileName(self, "Logo image", "", "Images (*.png *.jpg *.jpeg)")
        if p:
            self.brand_fields["logo"].setText(p)

    def _new_blank(self):
        name, ok = QInputDialog.getText(self, "New template", "Template name:", text="New template")
        if ok and name.strip():
            self._load_into_form(templates_mod.default_template(name.strip()))

    def _new_from_result(self):
        results = (self.last_payload or {}).get("results")
        if results is None:
            p, _ = QFileDialog.getOpenFileName(self, "Result file to seed from", "",
                                               "Results (*.rst *.rth *.f06 *.op2);;All (*.*)")
            if not p:
                return
            try:
                results = extract_mod.extract(Path(p))
            except Exception as e:
                QMessageBox.critical(self, "femrep", f"Could not read result for seeding:\n{e}")
                return
        self._load_into_form(templates_mod.seed_from_results(results, "From result"))

    def _duplicate(self):
        tpl = self._collect()
        tpl["name"] = f"{tpl['name']} copy"
        self._load_into_form(tpl)

    def _delete(self):
        item = self.lst.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "femrep", f"Delete template {item.text()!r}?") == QMessageBox.Yes:
            templates_mod.delete_template(self.project, item.text())
            self._reload_list()

    def _persist(self) -> Path:
        """Write the form's template to disk; returns the path. UI-feedback-free
        so it is testable without a modal dialog."""
        tpl = self._collect()
        path = templates_mod.save_template(self.project, tpl)
        self.saved_name = templates_mod.validate(tpl)["name"]
        self._reload_list(select=self.saved_name)
        return path

    def _save(self):
        path = self._persist()
        QMessageBox.information(self, "femrep", f"Saved template:\n{path}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("femrep")
    win = FemrepWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
