"""femrep.gui — PySide6 desktop app for the report generator.

A polished 4-step wizard: (1) pick a result file (and optional log/deck/GCI),
(2) review the QoI + femis gate verdicts, (3) choose a project template,
(4) export a PDF / DOCX report.

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
                               QFormLayout, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QSizePolicy, QStackedWidget,
                               QTextEdit, QVBoxLayout, QWidget)

from . import extract as extract_mod
from . import govern, cli as cli_mod
from . import report_pdf, report_docx
from . import templates as templates_mod
from . import workflow
from . import gui_style
from . import locale_ru

MODES = govern.MODES
HERE = Path(__file__).parent

# femis gate verdict -> pastel badge property + Russian label
_BADGE = {"pass": "ok", "not_done": "warn", "fail": "bad"}
_VERDICT_RU = {"pass": "соответствует", "not_done": "не выполнено",
               "fail": "не соответствует"}

# Universal-attach role -> Russian label + pastel badge property.
_ROLE_RU = {"result": "результат", "log": "журнал", "gci": "сетки GCI",
            "deck": "расчётная модель", "unknown": "не распознан"}
_ROLE_BADGE = {"result": "ok", "log": "warn", "gci": "warn",
               "deck": "warn", "unknown": "bad"}

STEPS = ["step_result", "step_check", "step_template", "step_export"]


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
                try:    # figures are optional — a render/DPF/pyvista failure must not
                        # block the report, mirroring workflow.run_report
                    from . import figures as fig_mod
                    figures = fig_mod.generate(results, gci, self.out_dir)
                except Exception as e:
                    self.progress.emit(f"figures skipped: {e}")
            review_html = workflow.render_html_review(results, manifest, checks, figures, self.out_dir)

            self.finished_ok.emit({"results": results, "manifest": manifest,
                                   "checks": checks, "figures": figures,
                                   "review_html": review_html})
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}")


def _set_prop(w: QWidget, name: str, value) -> None:
    """Set a dynamic property and re-apply QSS so selectors that key off it take."""
    w.setProperty(name, value)
    w.style().unpolish(w)
    w.style().polish(w)


class DropZone(QLabel):
    """A clickable, drag-and-drop file attach zone. Emits dropped(list[str])."""
    dropped = Signal(list)
    clicked = Signal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("drop")
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        self.clicked.emit()

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class FemrepWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(locale_ru.GUI["window_title"])
        self.resize(1040, 720)
        self.worker: PipelineWorker | None = None
        self.last_payload: dict | None = None
        self.report_mode = "SIGNOFF"
        self.project: Path | None = None
        self.attachments: dict[str, Path] = {}
        self._step = 0
        self._build_ui()
        self._set_step(0)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget(); root.setObjectName("canvas")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        outer.addWidget(self._build_rail())

        self.stack = QStackedWidget()
        wrap = QWidget(); wl = QVBoxLayout(wrap); wl.setContentsMargins(28, 28, 28, 28)
        wl.addWidget(self.stack)
        outer.addWidget(wrap, 1)

        self.stack.addWidget(self._build_step1())
        self.stack.addWidget(self._build_step2())
        self.stack.addWidget(self._build_step3())
        self.stack.addWidget(self._build_step4())

    def _build_rail(self) -> QWidget:
        rail = QWidget(); rail.setObjectName("rail"); rail.setFixedWidth(240)
        lay = QVBoxLayout(rail); lay.setContentsMargins(24, 28, 18, 28); lay.setSpacing(6)

        brand = QLabel("femrep"); brand.setObjectName("brand")
        sub = QLabel(locale_ru.GUI["brand_sub"]); sub.setObjectName("brandsub")
        lay.addWidget(brand); lay.addWidget(sub)
        lay.addSpacing(22)

        self._rail_rows: list[tuple[QLabel, QLabel]] = []
        for i, key in enumerate(STEPS):
            row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            num = QLabel(str(i + 1)); num.setObjectName("num"); num.setAlignment(Qt.AlignCenter)
            step = QLabel(locale_ru.GUI[key]); step.setProperty("role", "step")
            rl.addWidget(num); rl.addWidget(step, 1)
            lay.addWidget(row)
            self._rail_rows.append((num, step))
        lay.addStretch()

        hint = QLabel(locale_ru.GUI["rail_hint"])
        hint.setObjectName("brandsub"); hint.setWordWrap(True)
        lay.addWidget(hint)
        return rail

    def _card(self, title_key: str, subtitle: str):
        """Build a card QFrame, return (card, body_layout) with header pre-filled."""
        card = QFrame(); card.setObjectName("card")
        v = QVBoxLayout(card); v.setContentsMargins(36, 32, 36, 32); v.setSpacing(14)
        h = QLabel(locale_ru.GUI[title_key]); h.setObjectName("h2")
        v.addWidget(h)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("sub"); s.setWordWrap(True)
            v.addWidget(s)
        return card, v

    def _footer(self, back_cb, next_widget: QWidget, back_visible=True):
        bar = QHBoxLayout()
        back = QPushButton(locale_ru.GUI["btn_back"]); back.setObjectName("ghost")
        back.clicked.connect(back_cb)
        back.setVisible(back_visible)
        bar.addWidget(back); bar.addStretch(); bar.addWidget(next_widget)
        return bar

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper()); lbl.setObjectName("section")
        return lbl

    # --- step 1: Result -------------------------------------------------
    def _build_step1(self) -> QWidget:
        card, v = self._card("step_result", locale_ru.GUI["card1_sub"])
        v.addSpacing(6)
        v.addWidget(self._section(locale_ru.GUI["sec_attachments"]))
        self.drop = DropZone(locale_ru.GUI["drop_text"])
        self.drop.setMinimumHeight(108)
        self.drop.clicked.connect(self._pick_attach)
        self.drop.dropped.connect(self._attach_paths)
        v.addWidget(self.drop)

        # host for the removable attachment rows
        self.attach_host = QWidget(); self.attach_host.setStyleSheet("background: transparent;")
        self.attach_lay = QVBoxLayout(self.attach_host)
        self.attach_lay.setContentsMargins(0, 2, 14, 2); self.attach_lay.setSpacing(7)
        v.addWidget(self.attach_host)
        self.lbl_attach_hint = QLabel(locale_ru.GUI["attach_required"])
        self.lbl_attach_hint.setObjectName("sub")
        v.addWidget(self.lbl_attach_hint)

        self.chk_figs = QRadioButton(locale_ru.GUI["with_figures"]); self.chk_figs.setChecked(True)
        v.addWidget(self.chk_figs)

        v.addStretch()
        self.progress = QProgressBar(); self.progress.setVisible(False)
        v.addWidget(self.progress)
        self.lbl_status = QLabel(""); self.lbl_status.setObjectName("sub")
        v.addWidget(self.lbl_status)

        self.btn_run = QPushButton(locale_ru.GUI["btn_extract"]); self.btn_run.setObjectName("cta")
        self.btn_run.clicked.connect(self._run)
        v.addLayout(self._footer(lambda: None, self.btn_run, back_visible=False))
        self._refresh_attachments()
        return card

    # --- step 2: Check --------------------------------------------------
    def _build_step2(self) -> QWidget:
        card, v = self._card("step_check", locale_ru.GUI["card2_sub"])
        body = QHBoxLayout(); body.setSpacing(20)

        left = QVBoxLayout(); left.setSpacing(10)
        left.addWidget(self._section(locale_ru.GUI["sec_contour"]))
        self.preview = QLabel(locale_ru.GUI["preview_placeholder"])
        self.preview.setObjectName("drop"); self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(360, 280)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left.addWidget(self.preview, 1)
        body.addLayout(left, 1)

        right = QVBoxLayout(); right.setSpacing(8)
        right.addWidget(self._section(locale_ru.GUI["sec_qoi"]))
        self.lbl_qoi = QLabel("—"); self.lbl_qoi.setWordWrap(True)
        right.addWidget(self.lbl_qoi)
        right.addSpacing(6)
        right.addWidget(self._section(locale_ru.GUI["sec_gates"]))
        # gates fit directly in the column (6–9 of them) — no scroll area needed
        self.gates_host = QWidget()
        self.gates_host.setStyleSheet("background: transparent;")
        self.gates_lay = QVBoxLayout(self.gates_host)
        self.gates_lay.setContentsMargins(0, 2, 14, 2); self.gates_lay.setSpacing(7)
        right.addWidget(self.gates_host, 1)
        right.addWidget(self._section(locale_ru.GUI["sec_claim"]))
        self.lbl_claim = QLabel("—"); self.lbl_claim.setWordWrap(True); self.lbl_claim.setObjectName("sub")
        right.addWidget(self.lbl_claim)
        body.addLayout(right, 1)

        v.addLayout(body, 1)

        self.btn_review = QPushButton(locale_ru.GUI["btn_open_review"]); self.btn_review.setObjectName("opt")
        self.btn_review.clicked.connect(self._open_review); self.btn_review.setEnabled(False)
        nxt = QPushButton(locale_ru.GUI["btn_next"]); nxt.setObjectName("cta")
        nxt.clicked.connect(lambda: self._set_step(2))
        foot = self._footer(lambda: self._set_step(0), nxt)
        foot.insertWidget(1, self.btn_review)
        v.addLayout(foot)
        return card

    # --- step 3: Template ----------------------------------------------
    def _build_step3(self) -> QWidget:
        card, v = self._card("step_template", locale_ru.GUI["card3_sub"])
        v.addSpacing(4)
        v.addWidget(self._section(locale_ru.GUI["sec_project"]))
        pr = QHBoxLayout(); pr.setSpacing(10)
        self.btn_project = QPushButton(locale_ru.GUI["btn_open_project"]); self.btn_project.setObjectName("opt")
        self.btn_project.setToolTip(locale_ru.GUI["btn_open_project_tip"])
        self.btn_project.clicked.connect(self._pick_project)
        pr.addWidget(self.btn_project)
        self.lbl_project = QLabel(locale_ru.GUI["project_none"]); self.lbl_project.setObjectName("sub")
        pr.addWidget(self.lbl_project, 1)
        v.addLayout(pr)

        v.addSpacing(8)
        v.addWidget(self._section(locale_ru.GUI["sec_template"]))
        self.cmb_template = QComboBox()
        self.cmb_template.addItem(locale_ru.BUILTIN_DEFAULT_LABEL, ("builtin", "default"))
        self.cmb_template.addItem(locale_ru.BUILTIN_GOST_LABEL, ("builtin", "gost_ru"))
        self.cmb_template.currentIndexChanged.connect(lambda _i: self._refresh_content_panel())
        v.addWidget(self.cmb_template)

        self.btn_manage = QPushButton(locale_ru.GUI["btn_manage_templates"]); self.btn_manage.setObjectName("opt")
        self.btn_manage.clicked.connect(self._manage_templates); self.btn_manage.setEnabled(False)
        mr = QHBoxLayout(); mr.addWidget(self.btn_manage); mr.addStretch()
        v.addLayout(mr)

        v.addSpacing(4)
        v.addWidget(self._section(locale_ru.GUI["sec_content"]))
        self.content_host = QWidget(); self.content_host.setStyleSheet("background: transparent;")
        self.content_lay = QVBoxLayout(self.content_host)
        self.content_lay.setContentsMargins(0, 2, 14, 2); self.content_lay.setSpacing(3)
        cscroll = QScrollArea(); cscroll.setWidgetResizable(True); cscroll.setWidget(self.content_host)
        cscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cscroll.setFrameShape(QFrame.NoFrame)
        cscroll.viewport().setStyleSheet("background: transparent;")
        v.addWidget(cscroll, 1)

        nxt = QPushButton(locale_ru.GUI["btn_next"]); nxt.setObjectName("cta")
        nxt.clicked.connect(self._goto_export)
        v.addLayout(self._footer(lambda: self._set_step(1), nxt))
        return card

    # --- step 4: Export -------------------------------------------------
    def _build_step4(self) -> QWidget:
        card, v = self._card("step_export", locale_ru.GUI["card4_sub"])
        v.addSpacing(6)
        v.addWidget(self._section(locale_ru.GUI["sec_summary"]))
        self.lbl_export = QLabel("—"); self.lbl_export.setWordWrap(True)
        v.addWidget(self.lbl_export)

        v.addSpacing(8)
        v.addWidget(self._section(locale_ru.GUI["sec_sections"]))
        self.lbl_export_sections = QLabel("—"); self.lbl_export_sections.setObjectName("sub")
        self.lbl_export_sections.setWordWrap(True)
        v.addWidget(self.lbl_export_sections)

        v.addSpacing(8)
        v.addWidget(self._section(locale_ru.GUI["sec_format"]))
        fr = QHBoxLayout()
        self.rb_pdf = QRadioButton("PDF"); self.rb_pdf.setChecked(True)
        self.rb_docx = QRadioButton("DOCX")
        fr.addWidget(self.rb_pdf); fr.addWidget(self.rb_docx); fr.addStretch()
        v.addLayout(fr)
        self.lbl_gost = QLabel(""); self.lbl_gost.setObjectName("sub"); self.lbl_gost.setWordWrap(True)
        v.addWidget(self.lbl_gost)

        v.addStretch()
        self.btn_render = QPushButton(locale_ru.GUI["btn_generate"]); self.btn_render.setObjectName("cta")
        self.btn_render.clicked.connect(self._render)
        v.addLayout(self._footer(lambda: self._set_step(2), self.btn_render))
        return card

    # ------------------------------------------------------------- navigation
    def _set_step(self, idx: int):
        self._step = idx
        self.stack.setCurrentIndex(idx)
        for i, (num, step) in enumerate(self._rail_rows):
            active = (i == idx)
            done = (i < idx)
            _set_prop(num, "active", active)
            _set_prop(num, "done", done and not active)
            _set_prop(step, "active", active)
        if idx == 2:
            self._refresh_content_panel()
        if idx == 3:
            self._refresh_export_summary()
            self._refresh_export_sections()

    # ------------------------------------------------------------- attachments
    def _pick_attach(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, locale_ru.GUI["dlg_attach_files"], "", locale_ru.GUI["filter_all"])
        if paths:
            self._attach_paths(paths)

    def _attach_paths(self, paths: list[str]):
        """Classify each path and store it under its role (latest wins per role)."""
        for p in paths:
            role = workflow.classify_input(p)
            self.attachments[role] = Path(p)
        self._refresh_attachments()

    def _remove_role(self, role: str):
        self.attachments.pop(role, None)
        self._refresh_attachments()

    def _refresh_attachments(self):
        """Rebuild the removable attachment rows and gate the CTA on a result."""
        while self.attach_lay.count():
            item = self.attach_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for role, path in self.attachments.items():
            row = QWidget(); rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            rm = QPushButton("×"); rm.setObjectName("iconbtn"); rm.setFixedSize(24, 24)
            rm.setToolTip(locale_ru.GUI["attach_remove_tip"])
            rm.clicked.connect(lambda _=False, r=role: self._remove_role(r))
            name = QLabel(path.name); name.setWordWrap(True)
            badge = QLabel(_ROLE_RU.get(role, role)); badge.setAlignment(Qt.AlignCenter)
            _set_prop(badge, "badge", _ROLE_BADGE.get(role, "warn"))
            rl.addWidget(rm, 0, Qt.AlignTop)
            rl.addWidget(name, 1)
            rl.addWidget(badge, 0, Qt.AlignTop)
            self.attach_lay.addWidget(row)

        has_result = "result" in self.attachments
        self.btn_run.setEnabled(has_result)
        self.lbl_attach_hint.setText(
            locale_ru.GUI["attach_ready"] if has_result
            else locale_ru.GUI["attach_required"])

    # ------------------------------------------------------------- project / templates
    def _pick_project(self):
        d = QFileDialog.getExistingDirectory(self, locale_ru.GUI["dlg_open_project"])
        if not d:
            return
        self.project = Path(d)
        templates_mod.templates_dir(self.project).mkdir(parents=True, exist_ok=True)
        self.lbl_project.setText(str(self.project))
        self.btn_manage.setEnabled(True)
        self._refresh_templates()

    def _refresh_templates(self, select: str | None = None):
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        self.cmb_template.addItem(locale_ru.BUILTIN_DEFAULT_LABEL, ("builtin", "default"))
        self.cmb_template.addItem(locale_ru.BUILTIN_GOST_LABEL, ("builtin", "gost_ru"))
        if self.project:
            for name in templates_mod.list_templates(self.project):
                self.cmb_template.addItem(name, ("project", name))
        if select:
            i = self.cmb_template.findText(select)
            if i >= 0:
                self.cmb_template.setCurrentIndex(i)
        self.cmb_template.blockSignals(False)

    def _current_template_ref(self) -> tuple[str, str]:
        """(kind, ref) for the selected dropdown item: ('builtin','default'),
        ('builtin','gost_ru'), or ('project', <name>). Defaults to builtin default."""
        data = self.cmb_template.currentData()
        return data if isinstance(data, tuple) else ("builtin", "default")

    def _manage_templates(self):
        if not self.project:
            QMessageBox.information(self, "femrep", locale_ru.GUI["msg_open_project_first"])
            return
        dlg = TemplateDialog(self.project, self.last_payload, self)
        dlg.exec()
        self._refresh_templates(select=dlg.saved_name)

    def _selected_cfg(self):
        """Base config.yaml, then apply the selected dropdown entry: a built-in
        profile (default / gost_ru) or a project template overlay."""
        cfg = cli_mod._load_config(HERE / "config.yaml")
        kind, ref = self._current_template_ref()
        if kind == "builtin":
            if ref == "gost_ru":
                cfg["profile"] = "gost_ru"
        elif kind == "project" and self.project:
            try:
                tpl = templates_mod.load_template(self.project, ref)
                cfg.update(templates_mod.to_config(tpl))
            except (FileNotFoundError, ValueError) as e:
                QMessageBox.warning(self, "femrep",
                                    locale_ru.GUI["msg_load_template_failed"].format(
                                        name=repr(ref), err=e))
        return cfg

    # ------------------------------------------------------------- content panel
    def _enabled_sections(self) -> list[str]:
        """Ordered section keys for the selection. Both built-ins use the full
        default section list; a project template uses its enabled sections."""
        kind, ref = self._current_template_ref()
        if kind == "project" and self.project:
            try:
                tpl = templates_mod.load_template(self.project, ref)
                return [s["key"] for s in templates_mod.to_config(tpl).get("sections", [])]
            except (FileNotFoundError, ValueError):
                pass
        return [k for k, _ in templates_mod.SECTIONS]

    def _section_availability(self, key: str) -> tuple[str, str]:
        """(badge, label) describing whether a section's data is available, from
        the last pipeline payload. Read-only — editing lives in TemplateDialog."""
        if key == "composites":
            return "warn", locale_ru.GUI["avail_example"]
        if key == "gci":
            checks = (self.last_payload or {}).get("checks") or {}
            if checks.get("gci"):
                return "ok", locale_ru.GUI["avail_yes"]
            return "warn", locale_ru.GUI["avail_no_gci"]
        return "ok", locale_ru.GUI["avail_yes"]

    def _refresh_content_panel(self):
        if not hasattr(self, "content_lay"):
            return
        while self.content_lay.count():
            item = self.content_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for key in self._enabled_sections():
            badge_prop, badge_text = self._section_availability(key)
            row = QWidget(); rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            title = QLabel(locale_ru.SECTION_TITLES_RU.get(key, key)); title.setWordWrap(True)
            badge = QLabel(badge_text); badge.setAlignment(Qt.AlignCenter)
            _set_prop(badge, "badge", badge_prop)
            rl.addWidget(title, 1)
            rl.addWidget(badge, 0, Qt.AlignTop)
            self.content_lay.addWidget(row)
        self.content_lay.addStretch()

    # ------------------------------------------------------------- run pipeline
    def _run(self):
        result_file = self.attachments.get("result")
        if result_file is None:
            QMessageBox.warning(self, "femrep", locale_ru.GUI["msg_attach_first"])
            return
        # mirror the CLI: an .op2 with a sibling .f06 resolves to the .f06 backend
        result_file, deck = workflow.resolve_inputs(result_file, self.attachments.get("deck"))
        self.out_dir = Path.cwd() / "femrep_out" / result_file.stem
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.btn_run.setEnabled(False); self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.lbl_status.setText(locale_ru.GUI["status_running"])
        self.worker = PipelineWorker(
            result_file, self.report_mode,
            self.attachments.get("log"), deck,
            self.attachments.get("gci"), self.out_dir, self.chk_figs.isChecked())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_progress(self, msg):
        self.lbl_status.setText(msg)

    def _on_done(self, payload):
        self.last_payload = payload
        self.progress.setVisible(False); self.btn_run.setEnabled(True)
        self.lbl_status.setText(locale_ru.GUI["status_done"])
        self._populate_check(payload)
        self._set_step(1)

    def _on_fail(self, msg):
        self.progress.setVisible(False); self.btn_run.setEnabled(True)
        self.lbl_status.setText(locale_ru.GUI["status_error"])
        QMessageBox.critical(self, "femrep", msg)

    def _open_review(self):
        if self.last_payload and self.last_payload.get("review_html"):
            webbrowser.open(Path(self.last_payload["review_html"]).resolve().as_uri())

    # ------------------------------------------------------------- check view
    def _populate_check(self, payload):
        checks = payload["checks"]; results = payload["results"]; manifest = payload["manifest"]
        figs = payload.get("figures") or {}

        cp = figs.get("contour_views") or figs.get("contour")
        if cp and Path(cp).exists():
            pix = QPixmap(str(cp))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaledToWidth(440, Qt.SmoothTransformation))
            else:
                self.preview.setText(locale_ru.GUI["contour_unavailable"])
        else:
            self.preview.setText(locale_ru.GUI["contour_unavailable_hint"])

        q = results["primary_qoi"]
        readiness = checks.get("readiness") or {}
        solver = (manifest.get("solver", "").split() or ["—"])[0].capitalize()
        analysis = locale_ru.analysis_ru(manifest.get("analysis_type", ""))
        self.lbl_qoi.setText(
            f"<b>{solver}</b> · {analysis} анализ<br>"
            f"{locale_ru.qoi_ru(q['name'])} = {q['min']} … {q['max']} {locale_ru.units_ru(q['units'])}<br>"
            f"<span style='color:{gui_style.MUTED}'>"
            f"{locale_ru.readiness_status_ru(readiness.get('status', ''), 'инженерный отчёт')}</span>")

        # clear & rebuild gate badges
        while self.gates_lay.count():
            item = self.gates_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for g in checks["gates"]:
            row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            name = QLabel(locale_ru.GATE_NAMES.get(g["gate"], g["gate"]))
            name.setWordWrap(True)
            badge = QLabel(_VERDICT_RU.get(g["verdict"], g["verdict"]))
            badge.setAlignment(Qt.AlignCenter)
            _set_prop(badge, "badge", _BADGE.get(g["verdict"], "warn"))
            # name takes the full width; the compact pill is right-aligned to the first line
            rl.addWidget(name, 1)
            rl.addWidget(badge, 0, Qt.AlignTop)
            note = g.get("note")
            if note:
                row.setToolTip(note)
            self.gates_lay.addWidget(row)
        self.gates_lay.addStretch()

        self.lbl_claim.setText(locale_ru.review_summary_ru(results, checks))
        self.btn_review.setEnabled(bool(payload.get("review_html")))

    # ------------------------------------------------------------- export view
    def _goto_export(self):
        self._set_step(3)

    def _refresh_export_summary(self):
        cfg = self._selected_cfg()
        gost = cfg.get("profile") == "gost_ru"
        name = self.cmb_template.currentText()
        proj = str(self.project) if self.project else locale_ru.GUI["project_none"]
        prof = "ГОСТ 7.32-2017" if gost else locale_ru.GUI["profile_default_name"]
        self.lbl_export.setText(
            f"<b>{locale_ru.GUI['export_project']}:</b> {proj}<br>"
            f"<b>{locale_ru.GUI['export_template']}:</b> {name}<br>"
            f"<b>{locale_ru.GUI['export_profile']}:</b> {prof}")
        if gost:
            self.lbl_gost.setText(locale_ru.GUI["gost_note"])
            self.rb_docx.setChecked(True)
            self.rb_pdf.setEnabled(False); self.rb_docx.setEnabled(False)
        else:
            self.lbl_gost.setText("")
            self.rb_pdf.setEnabled(True); self.rb_docx.setEnabled(True)

    def _refresh_export_sections(self):
        titles = [locale_ru.SECTION_TITLES_RU.get(k, k) for k in self._enabled_sections()]
        self.lbl_export_sections.setText("  ·  ".join(titles) if titles
                                         else locale_ru.GUI["sections_none"])

    # ------------------------------------------------------------- render
    def _render_to(self, path: Path, cfg: dict) -> Path:
        """Render the last payload to `path`, routing by the cfg's profile. The
        gost_ru profile always emits a Russian .docx. Dialog-free so it is testable."""
        from datetime import datetime
        meta = {"generated": datetime.now().isoformat(timespec="seconds")}
        pl = self.last_payload
        if cfg.get("profile") == "gost_ru":
            from . import report_gost_docx
            if path.suffix.lower() != ".docx":
                path = path.with_suffix(".docx")
            report_gost_docx.render(pl["results"], pl["manifest"], pl["checks"], cfg,
                                    pl["figures"], meta, path)
        elif path.suffix.lower() == ".docx":
            report_docx.render(pl["results"], pl["manifest"], pl["checks"], cfg,
                               pl["figures"], meta, path)
        else:
            report_pdf.render(pl["results"], pl["manifest"], pl["checks"], cfg,
                              pl["figures"], meta, path)
        return path

    def _render(self):
        if not self.last_payload:
            QMessageBox.warning(self, "femrep", locale_ru.GUI["msg_extract_first"])
            return
        cfg = self._selected_cfg()
        gost = cfg.get("profile") == "gost_ru"
        ext = ".docx" if (gost or self.rb_docx.isChecked()) else ".pdf"
        base = getattr(self, "out_dir", Path.cwd())
        p, _ = QFileDialog.getSaveFileName(self, locale_ru.GUI["dlg_save_report"],
                                           str(base / ("report" + ext)),
                                           locale_ru.GUI["filter_report"].format(ext=ext))
        if not p:
            return
        try:
            out = self._render_to(Path(p), cfg)
            QMessageBox.information(self, "femrep",
                                    locale_ru.GUI["msg_report_saved"].format(path=out))
        except Exception as e:
            QMessageBox.critical(self, "femrep",
                                 locale_ru.GUI["msg_render_failed"].format(
                                     err=f"{e}\n{traceback.format_exc()[-600:]}"))


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
        self.setWindowTitle(locale_ru.GUI["td_title"])
        self.resize(820, 620)
        self._build()
        self._reload_list()

    def _build(self):
        outer = QHBoxLayout(self)

        # left: template list + actions
        left = QVBoxLayout()
        self.lst = QListWidget()
        self.lst.currentTextChanged.connect(self._on_pick)
        left.addWidget(QLabel(locale_ru.GUI["td_list_header"]))
        left.addWidget(self.lst, 1)
        for label_key, slot in [("td_new_blank", self._new_blank),
                                ("td_new_from_result", self._new_from_result),
                                ("td_duplicate", self._duplicate),
                                ("td_delete", self._delete)]:
            b = QPushButton(locale_ru.GUI[label_key]); b.clicked.connect(slot); left.addWidget(b)
        outer.addLayout(left, 1)

        # right: edit form
        right = QVBoxLayout()
        form_host = QWidget(); form = QFormLayout(form_host)
        self.f_name = QLineEdit()
        form.addRow(locale_ru.GUI["td_name"], self.f_name)
        self.f_profile = QComboBox()
        self._profiles = [(locale_ru.GUI["profile_default_label"], "default"),
                          (locale_ru.GUI["profile_gost_label"], "gost_ru")]
        for label, _ in self._profiles:
            self.f_profile.addItem(label)
        form.addRow(locale_ru.GUI["td_profile"], self.f_profile)
        self.brand_fields: dict[str, QLineEdit] = {}
        for key in templates_mod.DEFAULT_BRANDING:
            le = QLineEdit()
            self.brand_fields[key] = le
            if key == "logo":
                row = QHBoxLayout(); row.addWidget(le, 1)
                browse = QPushButton("…"); browse.setFixedWidth(28)
                browse.clicked.connect(self._pick_logo); row.addWidget(browse)
                host = QWidget(); host.setLayout(row); form.addRow(locale_ru.branding_label(key), host)
            else:
                form.addRow(locale_ru.branding_label(key), le)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(form_host)
        right.addWidget(QLabel(locale_ru.GUI["td_branding_header"])); right.addWidget(scroll, 2)

        right.addWidget(QLabel(locale_ru.GUI["td_sections_header"]))
        self.lst_sec = QListWidget()
        self.lst_sec.currentRowChanged.connect(self._on_section_pick)
        right.addWidget(self.lst_sec, 2)
        secbtns = QHBoxLayout()
        for label, slot in [("↑", lambda: self._move_section(-1)),
                            ("↓", lambda: self._move_section(1))]:
            b = QPushButton(label); b.setFixedWidth(36); b.clicked.connect(slot); secbtns.addWidget(b)
        secbtns.addWidget(QLabel(locale_ru.GUI["td_intro"]))
        self.f_intro = QLineEdit(); self.f_intro.setPlaceholderText(locale_ru.GUI["td_intro_placeholder"])
        self.f_intro.textEdited.connect(self._on_intro_edit)
        secbtns.addWidget(self.f_intro, 1)
        right.addLayout(secbtns)

        save = QPushButton(locale_ru.GUI["td_save"]); save.clicked.connect(self._save)
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
        prof_keys = [k for _, k in self._profiles]
        self.f_profile.setCurrentIndex(prof_keys.index(tpl["profile"])
                                       if tpl["profile"] in prof_keys else 0)
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
                "profile": self._profiles[self.f_profile.currentIndex()][1],
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
        p, _ = QFileDialog.getOpenFileName(self, locale_ru.GUI["td_logo_title"], "",
                                           locale_ru.GUI["filter_images"])
        if p:
            self.brand_fields["logo"].setText(p)

    def _new_blank(self):
        name, ok = QInputDialog.getText(self, locale_ru.GUI["td_new_template_title"],
                                        locale_ru.GUI["td_new_template_prompt"],
                                        text=locale_ru.GUI["td_new_template_default"])
        if ok and name.strip():
            self._load_into_form(templates_mod.default_template(name.strip()))

    def _new_from_result(self):
        results = (self.last_payload or {}).get("results")
        if results is None:
            p, _ = QFileDialog.getOpenFileName(self, locale_ru.GUI["td_seed_result_title"], "",
                                               locale_ru.GUI["filter_results"])
            if not p:
                return
            try:
                results = extract_mod.extract(Path(p))
            except Exception as e:
                QMessageBox.critical(self, "femrep",
                                     locale_ru.GUI["td_seed_failed"].format(err=e))
                return
        self._load_into_form(templates_mod.seed_from_results(results, locale_ru.GUI["td_from_result_name"]))

    def _duplicate(self):
        tpl = self._collect()
        tpl["name"] = f"{tpl['name']} {locale_ru.GUI['td_copy_suffix']}"
        self._load_into_form(tpl)

    def _delete(self):
        item = self.lst.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "femrep",
                                locale_ru.GUI["td_delete_confirm"].format(name=repr(item.text()))) == QMessageBox.Yes:
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
        QMessageBox.information(self, "femrep", locale_ru.GUI["td_saved"].format(path=path))


def _crash_log_path() -> Path:
    base = Path.home() / "AppData" / "Local" / "femrep" if sys.platform == "win32" else Path.home()
    base.mkdir(parents=True, exist_ok=True)
    return base / "femrep-crash.log"


def main() -> int:
    # The desktop icon runs the windowed (no-console) launcher, so an uncaught
    # startup exception would close the window with no message. Log it to a file
    # and show it in a dialog instead.
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("femrep")
        app.setStyleSheet(gui_style.QSS)
        win = FemrepWindow()
        win.show()
        return app.exec()
    except Exception:
        tb = traceback.format_exc()
        try:
            _crash_log_path().write_text(tb, encoding="utf-8")
        except Exception:
            pass
        try:
            QMessageBox.critical(None, locale_ru.GUI["startup_error_title"],
                                 locale_ru.GUI["startup_error_body"].format(
                                     tb=tb[-1500:], path=_crash_log_path()))
        except Exception:
            sys.stderr.write(tb)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
