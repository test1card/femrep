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

STEPS = [("Результат", "Result"), ("Проверка", "Check"),
         ("Шаблон", "Template"), ("Экспорт", "Export")]


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


def _set_prop(w: QWidget, name: str, value) -> None:
    """Set a dynamic property and re-apply QSS so selectors that key off it take."""
    w.setProperty(name, value)
    w.style().unpolish(w)
    w.style().polish(w)


class FemrepWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("femrep — femis-governed FEM report generator")
        self.resize(1040, 720)
        self.worker: PipelineWorker | None = None
        self.last_payload: dict | None = None
        self.report_mode = "SIGNOFF"
        self.project: Path | None = None
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
        sub = QLabel("FEM-отчёты под femis"); sub.setObjectName("brandsub")
        lay.addWidget(brand); lay.addWidget(sub)
        lay.addSpacing(22)

        self._rail_rows: list[tuple[QLabel, QLabel]] = []
        for i, (ru, en) in enumerate(STEPS):
            row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
            num = QLabel(str(i + 1)); num.setObjectName("num"); num.setAlignment(Qt.AlignCenter)
            step = QLabel(f"{ru}"); step.setProperty("role", "step")
            step.setToolTip(en)
            rl.addWidget(num); rl.addWidget(step, 1)
            lay.addWidget(row)
            self._rail_rows.append((num, step))
        lay.addStretch()

        hint = QLabel("femis: ни один вывод не сильнее\nсвоей проверки.")
        hint.setObjectName("brandsub"); hint.setWordWrap(True)
        lay.addWidget(hint)
        return rail

    def _card(self, title_ru: str, title_en: str, subtitle: str):
        """Build a card QFrame, return (card, body_layout) with header pre-filled."""
        card = QFrame(); card.setObjectName("card")
        v = QVBoxLayout(card); v.setContentsMargins(36, 32, 36, 32); v.setSpacing(14)
        h = QLabel(f"{title_ru}"); h.setObjectName("h2"); h.setToolTip(title_en)
        v.addWidget(h)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("sub"); s.setWordWrap(True)
            v.addWidget(s)
        return card, v

    def _footer(self, back_cb, next_widget: QWidget, back_visible=True):
        bar = QHBoxLayout()
        back = QPushButton("Назад"); back.setObjectName("ghost")
        back.clicked.connect(back_cb)
        back.setVisible(back_visible)
        bar.addWidget(back); bar.addStretch(); bar.addWidget(next_widget)
        return bar

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper()); lbl.setObjectName("section")
        return lbl

    # --- step 1: Result -------------------------------------------------
    def _build_step1(self) -> QWidget:
        card, v = self._card("Результат", "Result",
                             "Выберите файл результатов решателя. Лог, GCI и расчётную "
                             "колоду можно добавить по желанию.")
        v.addSpacing(6)
        v.addWidget(self._section("Файл результатов (Result)"))
        self.drop = QLabel("Перетащите или нажмите, чтобы выбрать  ·  .rst / .rth / .f06 / .op2")
        self.drop.setObjectName("drop"); self.drop.setAlignment(Qt.AlignCenter)
        self.drop.setMinimumHeight(92)
        self.drop.setCursor(Qt.PointingHandCursor)
        self.drop.mousePressEvent = lambda e: self._pick_result()
        v.addWidget(self.drop)
        self.lbl_result = QLabel("файл не выбран"); self.lbl_result.setObjectName("sub")
        v.addWidget(self.lbl_result)

        v.addSpacing(8)
        v.addWidget(self._section("Опционально (Optional)"))
        opts = QHBoxLayout(); opts.setSpacing(10)
        self.btn_log = QPushButton("Лог (.mntr/.out)…"); self.btn_log.setObjectName("opt")
        self.btn_log.clicked.connect(self._pick_log)
        self.btn_gci = QPushButton("GCI (.json)…"); self.btn_gci.setObjectName("opt")
        self.btn_gci.clicked.connect(self._pick_gci)
        self.btn_deck = QPushButton("Колода / Deck…"); self.btn_deck.setObjectName("opt")
        self.btn_deck.clicked.connect(self._pick_deck)
        opts.addWidget(self.btn_log); opts.addWidget(self.btn_gci); opts.addWidget(self.btn_deck)
        opts.addStretch()
        v.addLayout(opts)
        self.lbl_opts = QLabel("лог — ·  GCI — ·  колода —"); self.lbl_opts.setObjectName("sub")
        v.addWidget(self.lbl_opts)

        self.chk_figs = QRadioButton("С иллюстрациями (with figures)"); self.chk_figs.setChecked(True)
        v.addWidget(self.chk_figs)

        v.addStretch()
        self.progress = QProgressBar(); self.progress.setVisible(False)
        v.addWidget(self.progress)
        self.lbl_status = QLabel(""); self.lbl_status.setObjectName("sub")
        v.addWidget(self.lbl_status)

        self.btn_run = QPushButton("Извлечь и проверить →"); self.btn_run.setObjectName("cta")
        self.btn_run.clicked.connect(self._run)
        v.addLayout(self._footer(lambda: None, self.btn_run, back_visible=False))
        return card

    # --- step 2: Check --------------------------------------------------
    def _build_step2(self) -> QWidget:
        card, v = self._card("Проверка", "Check",
                             "Результаты извлечены. Проверьте величину интереса и вердикты "
                             "проверок femis перед выпуском отчёта.")
        body = QHBoxLayout(); body.setSpacing(20)

        left = QVBoxLayout(); left.setSpacing(10)
        left.addWidget(self._section("Контур (Contour)"))
        self.preview = QLabel("предпросмотр контура появится после извлечения")
        self.preview.setObjectName("drop"); self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(360, 280)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left.addWidget(self.preview, 1)
        body.addLayout(left, 1)

        right = QVBoxLayout(); right.setSpacing(8)
        right.addWidget(self._section("Сводка QoI (Summary)"))
        self.lbl_qoi = QLabel("—"); self.lbl_qoi.setWordWrap(True)
        right.addWidget(self.lbl_qoi)
        right.addSpacing(6)
        right.addWidget(self._section("Проверки femis (Gates)"))
        self.gates_host = QWidget()
        self.gates_lay = QVBoxLayout(self.gates_host)
        self.gates_lay.setContentsMargins(0, 0, 0, 0); self.gates_lay.setSpacing(6)
        gscroll = QScrollArea(); gscroll.setWidgetResizable(True); gscroll.setWidget(self.gates_host)
        gscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right.addWidget(gscroll, 1)
        right.addWidget(self._section("Утверждение femis (Claim)"))
        self.lbl_claim = QLabel("—"); self.lbl_claim.setWordWrap(True); self.lbl_claim.setObjectName("sub")
        right.addWidget(self.lbl_claim)
        body.addLayout(right, 1)

        v.addLayout(body, 1)

        self.btn_review = QPushButton("Открыть HTML-обзор"); self.btn_review.setObjectName("opt")
        self.btn_review.clicked.connect(self._open_review); self.btn_review.setEnabled(False)
        nxt = QPushButton("Далее →"); nxt.setObjectName("cta")
        nxt.clicked.connect(lambda: self._set_step(2))
        foot = self._footer(lambda: self._set_step(0), nxt)
        foot.insertWidget(1, self.btn_review)
        v.addLayout(foot)
        return card

    # --- step 3: Template ----------------------------------------------
    def _build_step3(self) -> QWidget:
        card, v = self._card("Шаблон", "Template",
                             "Выберите проект и шаблон оформления. Шаблоны хранят брендинг, "
                             "набор разделов и профиль (например, ГОСТ).")
        v.addSpacing(6)
        v.addWidget(self._section("Проект (Project)"))
        pr = QHBoxLayout(); pr.setSpacing(10)
        self.btn_project = QPushButton("Открыть / создать проект…"); self.btn_project.setObjectName("opt")
        self.btn_project.setToolTip("Open or create a femrep project folder that holds your templates")
        self.btn_project.clicked.connect(self._pick_project)
        pr.addWidget(self.btn_project)
        self.lbl_project = QLabel("проект не выбран — встроенная разметка"); self.lbl_project.setObjectName("sub")
        pr.addWidget(self.lbl_project, 1)
        v.addLayout(pr)

        v.addSpacing(8)
        v.addWidget(self._section("Шаблон оформления (Template)"))
        self.cmb_template = QComboBox()
        self.cmb_template.addItem("Built-in default")
        v.addWidget(self.cmb_template)

        self.btn_manage = QPushButton("Управление шаблонами…"); self.btn_manage.setObjectName("opt")
        self.btn_manage.clicked.connect(self._manage_templates); self.btn_manage.setEnabled(False)
        mr = QHBoxLayout(); mr.addWidget(self.btn_manage); mr.addStretch()
        v.addLayout(mr)

        v.addStretch()
        nxt = QPushButton("Далее →"); nxt.setObjectName("cta")
        nxt.clicked.connect(self._goto_export)
        v.addLayout(self._footer(lambda: self._set_step(1), nxt))
        return card

    # --- step 4: Export -------------------------------------------------
    def _build_step4(self) -> QWidget:
        card, v = self._card("Экспорт", "Export",
                             "Сводка форматирования. Нажмите, чтобы сгенерировать итоговый отчёт.")
        v.addSpacing(6)
        v.addWidget(self._section("Сводка (Summary)"))
        self.lbl_export = QLabel("—"); self.lbl_export.setWordWrap(True)
        v.addWidget(self.lbl_export)

        v.addSpacing(8)
        v.addWidget(self._section("Формат (Format)"))
        fr = QHBoxLayout()
        self.rb_pdf = QRadioButton("PDF"); self.rb_pdf.setChecked(True)
        self.rb_docx = QRadioButton("DOCX")
        fr.addWidget(self.rb_pdf); fr.addWidget(self.rb_docx); fr.addStretch()
        v.addLayout(fr)
        self.lbl_gost = QLabel(""); self.lbl_gost.setObjectName("sub"); self.lbl_gost.setWordWrap(True)
        v.addWidget(self.lbl_gost)

        v.addStretch()
        self.btn_render = QPushButton("Сгенерировать отчёт"); self.btn_render.setObjectName("cta")
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
        if idx == 3:
            self._refresh_export_summary()

    # ------------------------------------------------------------- pickers
    def _pick_result(self):
        p, _ = QFileDialog.getOpenFileName(self, "Файл результатов / Result file", "",
                                           "Results (*.rst *.rth *.f06 *.op2);;All (*.*)")
        if p:
            self.result_file = Path(p)
            self.drop.setText(Path(p).name)
            self.lbl_result.setText(p)

    def _pick_log(self):
        p, _ = QFileDialog.getOpenFileName(self, "Лог решателя / Solve log", "",
                                           "Logs (*.mntr *.out *.log *.f06);;All (*.*)")
        if p:
            self.log_file = Path(p); self._refresh_opts()

    def _pick_gci(self):
        p, _ = QFileDialog.getOpenFileName(self, "GCI runs", "", "JSON (*.json)")
        if p:
            self.gci_file = Path(p); self._refresh_opts()

    def _pick_deck(self):
        p, _ = QFileDialog.getOpenFileName(self, "Расчётная колода / Deck", "", "All (*.*)")
        if p:
            self.deck_file = Path(p); self._refresh_opts()

    def _refresh_opts(self):
        log = getattr(self, "log_file", None)
        gci = getattr(self, "gci_file", None)
        deck = getattr(self, "deck_file", None)
        self.lbl_opts.setText(
            f"лог {log.name if log else '—'} ·  "
            f"GCI {gci.name if gci else '—'} ·  "
            f"колода {deck.name if deck else '—'}")

    # ------------------------------------------------------------- project / templates
    def _pick_project(self):
        d = QFileDialog.getExistingDirectory(self, "Open or create a femrep project folder")
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

    # ------------------------------------------------------------- run pipeline
    def _run(self):
        if not hasattr(self, "result_file"):
            QMessageBox.warning(self, "femrep", "Сначала выберите файл результатов.")
            return
        self.out_dir = Path.cwd() / "femrep_out" / self.result_file.stem
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.btn_run.setEnabled(False); self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.lbl_status.setText("выполняется…")
        self.worker = PipelineWorker(
            self.result_file, self.report_mode,
            getattr(self, "log_file", None), getattr(self, "deck_file", None),
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
        self.lbl_status.setText("готово")
        self._populate_check(payload)
        self._set_step(1)

    def _on_fail(self, msg):
        self.progress.setVisible(False); self.btn_run.setEnabled(True)
        self.lbl_status.setText("ОШИБКА")
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
                self.preview.setText("контур недоступен")
        else:
            self.preview.setText("контур недоступен — см. историю по времени в отчёте")

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
            row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(8)
            badge = QLabel(_VERDICT_RU.get(g["verdict"], g["verdict"]))
            badge.setAlignment(Qt.AlignCenter)
            _set_prop(badge, "badge", _BADGE.get(g["verdict"], "warn"))
            # fixed-width cell aligns the name column; the pill sizes to its text
            cell = QWidget(); cell.setFixedWidth(150)
            cl = QHBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
            cl.addWidget(badge); cl.addStretch()
            name = QLabel(locale_ru.GATE_NAMES.get(g["gate"], g["gate"]))
            name.setWordWrap(True)
            rl.addWidget(cell); rl.addWidget(name, 1)
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
        proj = str(self.project) if self.project else "встроенная разметка"
        self.lbl_export.setText(
            f"<b>Проект:</b> {proj}<br>"
            f"<b>Шаблон:</b> {name}<br>"
            f"<b>Профиль:</b> {cfg.get('profile', 'default')}")
        if gost:
            self.lbl_gost.setText("Профиль ГОСТ — отчёт будет сохранён как русский .docx "
                                  "(формат выбран автоматически).")
            self.rb_docx.setChecked(True)
            self.rb_pdf.setEnabled(False); self.rb_docx.setEnabled(False)
        else:
            self.lbl_gost.setText("")
            self.rb_pdf.setEnabled(True); self.rb_docx.setEnabled(True)

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
            QMessageBox.warning(self, "femrep", "Сначала извлеките результаты (шаг 1).")
            return
        cfg = self._selected_cfg()
        gost = cfg.get("profile") == "gost_ru"
        ext = ".docx" if (gost or self.rb_docx.isChecked()) else ".pdf"
        base = getattr(self, "out_dir", Path.cwd())
        p, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт" if gost else "Save report",
                                           str(base / ("report" + ext)),
                                           f"Report (*{ext})")
        if not p:
            return
        try:
            out = self._render_to(Path(p), cfg)
            QMessageBox.information(self, "femrep", f"Отчёт сохранён:\n{out}")
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
        form.addRow("Название / Name", self.f_name)
        self.f_profile = QComboBox()
        self._profiles = [("Стандартный (PDF/DOCX)", "default"),
                          ("ГОСТ 7.32-2017 (DOCX, рус.)", "gost_ru")]
        for label, _ in self._profiles:
            self.f_profile.addItem(label)
        form.addRow("Профиль / Profile", self.f_profile)
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
    app.setStyleSheet(gui_style.QSS)
    win = FemrepWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
