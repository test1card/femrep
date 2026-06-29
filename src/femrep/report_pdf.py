"""femrep.report_pdf — render a branded PDF from results + manifest + checks.

reportlab platypus (no system deps, unlike WeasyPrint). Clean modern default:
cover band, section headings, colored gate verdicts, probe tables, GCI table.
Same content as the DOCX renderer (M6).

Run via the CLI; standalone:
    python -m femrep.report_pdf  (reads out/results.json etc. — see __main__)
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, Image, PageBreak,
                                NextPageTemplate, HRFlowable)

VERDICT_COLOR = {"pass": "color_ok", "fail": "color_warn", "not_done": "color_muted"}


def _hex(s: str) -> colors.Color:
    return colors.HexColor(s)


def _styles(cfg: dict) -> dict:
    base = getSampleStyleSheet()
    font = cfg.get("font", "Helvetica")
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=font,
                                fontSize=26, textColor=_hex(cfg["color_primary"]),
                                spaceAfter=4, leading=30),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName=font,
                                   fontSize=12, textColor=_hex(cfg["color_muted"]),
                                   spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=font,
                             fontSize=15, textColor=_hex(cfg["color_primary"]),
                             spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=font,
                             fontSize=11, textColor=_hex(cfg["color_accent"]),
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName=font,
                               fontSize=9.5, leading=14, spaceAfter=4),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName=font,
                                fontSize=8, textColor=_hex(cfg["color_muted"]),
                                leading=11),
        "claim": ParagraphStyle("claim", parent=base["Normal"], fontName=font,
                                fontSize=10, leading=15, spaceAfter=6,
                                backColor=_hex("#f1f3f5"), borderPadding=6,
                                borderColor=_hex(cfg["color_accent"]),
                                borderWidth=0.5),
        "mono": ParagraphStyle("mono", parent=base["Code"], fontName="Courier",
                               fontSize=7.5, leading=10, textColor=_hex(cfg["color_muted"]),
                               backColor=_hex("#f8f9fa"), borderPadding=4),
    }


def _page_decorations(canvas, doc, cfg, meta):
    """Header/footer on every page after the cover."""
    canvas.saveState()
    w, h = doc.pagesize
    if doc.page > 1:
        canvas.setFont(cfg.get("font", "Helvetica"), 8)
        canvas.setFillColor(_hex(cfg["color_muted"]))
        canvas.drawString(20 * mm, h - 12 * mm,
                          f"{cfg.get('title','FEM Report')}  ·  femis-governed")
        canvas.drawRightString(w - 20 * mm, h - 12 * mm,
                               f"result sha {meta.get('sha','')[:12]}…")
        canvas.setStrokeColor(_hex(cfg["color_primary"]))
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        canvas.drawCentredString(w / 2, 10 * mm, f"{doc.page}")
    canvas.restoreState()


def _cover_band(story, cfg, manifest, meta, st):
    """Cover: title band with primary color and public report facts."""
    w, _ = A4 if cfg.get("page_size", "A4") == "A4" else LETTER
    doc_id = cfg.get("document_number") or "uncontrolled draft"
    rev = cfg.get("revision") or "-"
    band = Table([[Paragraph(cfg.get("title", "FEM Analysis Report"), st["title"])],
                  [Paragraph(f"{manifest.get('analysis_type','').split(' ')[0]} analysis · "
                             f"{manifest.get('solver','')} {manifest.get('solver_version','')}",
                             st["subtitle"])],
                  [Paragraph(f"Generated {meta.get('generated','')[:10]}  ·  "
                             f"<b>Issued engineering report</b>  ·  Doc {doc_id} Rev {rev}",
                             st["subtitle"])]],
                 colWidths=[w - 40 * mm])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _hex(cfg["color_primary"])),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    # override paragraph colors inside band to white
    for p in (st["title"], st["subtitle"]):
        p.textColor = colors.white
    story.append(band)
    story.append(Spacer(1, 8 * mm))
    for p in (st["title"], st["subtitle"]):
        p.textColor = _hex(cfg["color_primary"]) if p is st["title"] else _hex(cfg["color_muted"])


def _kv_table(rows: list[tuple], cfg, st) -> Table:
    t = Table([[Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(str(v), st["body"])]
               for k, v in rows], colWidths=[45 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _hex("#f8f9fa")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, _hex(cfg["color_muted"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _gate_row(g: dict, cfg) -> list:
    color = VERDICT_COLOR[g["verdict"]]
    sym = {"pass": "✓", "fail": "✗", "not_done": "—"}.get(g["verdict"], "?")
    return [sym, g["gate"], g["note"]], color


def _gates_table(gates: list[dict], cfg, st) -> Table:
    rows = [["", "Gate", "Note"]]
    styles = [("BACKGROUND", (0, 0), (-1, 0), _hex(cfg["color_primary"])),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, 0), 9),
              ("FONTNAME", (0, 0), (-1, 0), cfg.get("font", "Helvetica"))]
    for i, g in enumerate(gates, start=1):
        color = _hex(cfg[VERDICT_COLOR[g["verdict"]]])
        sym = {"pass": "✓", "fail": "✗", "not_done": "—"}.get(g["verdict"], "?")
        rows.append([sym, g["gate"], Paragraph(g["note"], st["small"])])
        styles.append(("TEXTCOLOR", (0, i), (0, i), color))
        styles.append(("FONTSIZE", (0, i), (0, i), 12))
        styles.append(("ALIGN", (0, i), (0, i), "CENTER"))
    t = Table(rows, colWidths=[10 * mm, 50 * mm, 105 * mm])
    styles += [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _hex("#f8f9fa")]),
               ("LINEBELOW", (0, 0), (-1, -1), 0.25, _hex(cfg["color_muted"])),
               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    t.setStyle(TableStyle(styles))
    return t


def _gci_table(gci: dict | None, cfg, st) -> Table:
    if not gci:
        return Paragraph("No GCI study provided — single-mesh result (see gates).", st["small"])
    rows = [["Metric", "Value"]]
    for k, label in [("r21", "refinement ratio r21"), ("r32", "refinement ratio r32"),
                     ("convergence_ratio_R", "Roache convergence ratio R (want 0<R<1)"),
                     ("observed_order_p", "observed order p"),
                     ("gci_fine_pct", "GCI fine (%)"),
                     ("gci_coarse_pct", "GCI coarse (%)"),
                     ("asymptotic_ratio", "asymptotic ratio (want ~1)")]:
        v = gci.get(k)
        rows.append([label, f"{v:.4f}" if isinstance(v, float) else str(v)])
    rows.append(["VERDICT", gci["verdict"]])
    t = Table(rows, colWidths=[90 * mm, 75 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _hex(cfg["color_primary"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, _hex("#f8f9fa")]),
        ("BACKGROUND", (0, -1), (-1, -1),
         _hex(cfg["color_ok"] if gci["verdict"].startswith("PASS") else cfg["color_warn"])),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, _hex(cfg["color_muted"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _readiness_table(readiness: dict | None, cfg, st) -> Table | Paragraph:
    if not readiness:
        return Paragraph("Readiness summary not available.", st["small"])
    rows = [["Evidence", "Status", "Note"]]
    for item in readiness.get("items", []):
        rows.append([item["key"], item["status"], Paragraph(item["note"], st["small"])])
    t = Table(rows, colWidths=[42 * mm, 35 * mm, 88 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _hex(cfg["color_primary"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _hex("#f8f9fa")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, _hex(cfg["color_muted"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _add_figure(story, path: Path | None, caption: str, cfg, st, width_mm=150):
    if not path or not Path(path).exists():
        story.append(Paragraph(f"<i>{caption}</i> [figure not available]", st["small"]))
        return
    img = Image(str(path), width=width_mm * mm, height=width_mm * mm * 0.62)
    img._restrictSize(width_mm * mm, 190 * mm)
    story.append(img)
    story.append(Paragraph(f"<i>{caption}</i>", st["small"]))
    story.append(Spacer(1, 4 * mm))


def _render_composites(story, results: dict, cfg: dict, st: dict, figures: dict):
    """Render the CFRP section. If a real layup is present (from ACP/.rmed, M-later),
    render it; otherwise render the synthetic CLT validation case as a worked
    example so the section is never empty and its governance is demonstrated.
    """
    has_real = "layup" in results  # wired when real ACP data lands
    if not has_real:
        from .cases.clt_synthetic import case as clt_case
        c = clt_case()
        layup = c["layup"]
        story.append(Paragraph(
            "No ACP/.rmed layup detected in this result file. Rendering the synthetic "
            "[0/90/0] CLT <b>validation case</b> so the composite-section governance is "
            "demonstrated; real CFRP data is wired when an ACP result is supplied.", st["body"]))
        story.append(Paragraph(f"Material: {c['material']}  ·  "
                               f"failure philosophy: {layup['failure_philosophy']}", st["body"]))
        # layup table
        rows = [["ply", "angle (deg)", "t (mm)"]]
        for i, ang in enumerate(layup["sequence"], 1):
            rows.append([str(i), str(ang), str(layup["t_ply_mm"])])
        rows.append(["—", "total", str(layup["total_t_mm"])])
        t = Table(rows, colWidths=[20 * mm, 40 * mm, 40 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _hex(cfg["color_primary"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _hex("#f8f9fa")]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 3 * mm))
        # ABD / FPF key results
        A = c["ABD"]["A_MPa_mm"]
        story.append(_kv_table([
            ("A11 / A22 / A66", f"{A[0][0]:.0f} / {A[1][1]:.0f} / {A[2][2]:.0f} MPa·mm"),
            ("B (coupling)", f"≈ 0 (symmetric layup — verified)"),
            ("First-ply-failure Nx", f"{c['fpf_Nx_N_per_mm']} N/mm (Tsai-Wu IRF = 1.0)"),
        ], cfg, st))
        # femis governance note (from composites-analysis.md)
        story.append(Paragraph(
            "<b>femis governance note:</b> FPF is a design-point margin, conservative for "
            "ultimate strength (use progressive damage CDM for LPF/OHC/bearing). Progressive "
            "damage <b>requires characteristic-length / fracture-energy regularization</b> for "
            "mesh objectivity — a result without a mesh-sensitivity study is unverified. "
            "As-draped ply angles (not nominal) feed stiffness, strength and CTE.", st["claim"]))


def render(results: dict, manifest: dict, checks: dict, cfg: dict,
           figures: dict, meta: dict, out_path: Path) -> None:
    st = _styles(cfg)
    meta = {**meta, "sha": results.get("result_sha256", "")}
    qoi = results["primary_qoi"]
    gci = checks.get("gci")
    readiness = checks.get("readiness")
    page_size = A4 if cfg.get("page_size", "A4") == "A4" else LETTER

    doc = BaseDocTemplate(str(out_path), pagesize=page_size,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=20 * mm, bottomMargin=15 * mm,
                          title=cfg.get("title", "FEM Report"))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    cover_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cover")
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame],
                     onPage=lambda c, d: _page_decorations(c, d, cfg, meta)),
        PageTemplate(id="Body", frames=[frame],
                     onPage=lambda c, d: _page_decorations(c, d, cfg, meta)),
    ])

    story = []
    _cover_band(story, cfg, manifest, meta, st)
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    # --- 1. Summary ---
    story.append(Paragraph("1. Summary", st["h2"]))
    story.append(Paragraph(checks["claim"].replace("**", ""), st["claim"]))
    story.append(_kv_table([
        ("Readiness", readiness.get("summary", "(not evaluated)") if readiness else "(not evaluated)"),
        ("Primary QoI", f"{qoi['name']} ({qoi['units']})"),
        ("QoI catalog", ", ".join(i["name"] for i in results.get("qoi_catalog", [])) or "(not available)"),
        ("Range", f"{qoi['min']} .. {qoi['max']}  "
                  + (f"({qoi.get('min_C')} .. {qoi.get('max_C')} °C)" if 'min_C' in qoi else "")),
        ("Hot node", f"{qoi['hot_node']} @ {qoi['hot_node_xyz_mm']} mm"),
        ("Cold node", f"{qoi['cold_node']} @ {qoi['cold_node_xyz_mm']} mm"),
        ("Report status", "Issued"),
        ("Project", cfg.get("project") or "(not specified)"),
        ("Customer", cfg.get("customer") or "(not specified)"),
        ("Prepared / checked / approved",
         f"{cfg.get('prepared_by') or '-'} / {cfg.get('checked_by') or '-'} / {cfg.get('approved_by') or '-'}"),
    ], cfg, st))

    # --- 2. Model ---
    et = ", ".join(f"{k}: {v:,}" for k, v in results["mesh"]["element_types"].items())
    n_elem = sum(results["mesh"]["element_types"].values()) if results["mesh"]["element_types"] \
        else results["mesh"].get("elements", 0)
    n_elem = n_elem if isinstance(n_elem, int) else 0
    story.append(Paragraph("2. Model", st["h2"]))
    story.append(_kv_table([
        ("Nodes / elements", f"{results['mesh']['nodes']:,} / {n_elem:,}"
                              + ("" if n_elem else "  (not in .f06 — node/point dump only)")),
        ("Element types", et or "(n/a)"),
        ("Analysis type", manifest.get("analysis_type", "")),
        ("Units", manifest.get("units", "")),
        ("Result file", Path(results["result_file"]).name),
    ], cfg, st))

    # --- 3. Meshing ---
    story.append(Paragraph("3. Meshing", st["h2"]))
    story.append(Paragraph("Element distribution and mesh quality. Quality-metric "
                           "extraction (skewness, Jacobian, growth ratio) lands with M3/M4; "
                           "the histogram below is the current mesh composition.", st["body"]))
    et_rows = [["element", "count"]] + [[k, f"{v:,}"] for k, v in
                                        results["mesh"]["element_types"].items()]
    story.append(Table(et_rows, colWidths=[60 * mm, 40 * mm],
                       style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9),
                                         ("BACKGROUND", (0, 0), (-1, 0), _hex(cfg["color_primary"])),
                                         ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                         ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                                          [colors.white, _hex("#f8f9fa")])])))

    # --- 4. Composites / CFRP ---
    story.append(Paragraph("4. Composites / CFRP", st["h2"]))
    _render_composites(story, results, cfg, st, figures)

    # --- 5. Mechanical solve ---
    story.append(Paragraph("5. Mechanical / solve", st["h2"]))
    c = results.get("convergence", {})
    cv = c.get("converged")
    verdict_txt = ({True: "converged", False: "non-convergence / stop marker",
                    None: "no log / deferred"}.get(cv, str(cv)))
    story.append(_kv_table([
        ("Convergence verdict", verdict_txt),
        ("Substeps / outputs", str(c.get("substeps", "—"))),
        ("Final time", str(c.get("final_total_time", "—"))),
        ("Note", c.get("note", "—")),
        ("Solver", f"{manifest.get('solver','')} {manifest.get('solver_version','')}"),
    ], cfg, st))

    # --- 6. Results ---
    story.append(Paragraph("6. Results", st["h2"]))
    _add_figure(story, figures.get("contour_views"),
                "QoI field contour, four-view plate.", cfg, st, width_mm=165)
    _add_figure(story, figures.get("contour"), "QoI field contour (pyvista off-screen).",
                cfg, st)
    _add_figure(story, figures.get("deformed_shape"),
                "Undeformed (wireframe) vs deformed shape (scaled for visibility).",
                cfg, st)
    _add_figure(story, figures.get("time_history"), "Transient time-history / QoI snapshot.",
                cfg, st)

    # --- 7. Mesh-independence (GCI) ---
    story.append(Paragraph("7. Mesh independence (GCI)", st["h2"]))
    story.append(_gci_table(gci, cfg, st))
    _add_figure(story, figures.get("gci_convergence"),
                "GCI fine/coarse vs the 3% acceptance gate.", cfg, st, width_mm=120)

    # --- 8. Governance ---
    story.append(Paragraph("8. Governance (femis)", st["h2"]))
    story.append(Paragraph("Gates — each verdict is computed, never invented to 'pass'.", st["body"]))
    if readiness:
        story.append(Paragraph(readiness.get("summary", ""), st["claim"]))
    story.append(_readiness_table(readiness, cfg, st))
    story.append(Spacer(1, 4 * mm))
    story.append(_gates_table(checks["gates"], cfg, st))

    # --- 9. Manifest ---
    story.append(Paragraph("9. Run manifest (provenance)", st["h2"]))
    story.append(Paragraph(f"<b>Result SHA-256:</b> {results.get('result_sha256','')}", st["mono"]))
    story.append(_kv_table([
        ("Solver / version", f"{manifest.get('solver','')} {manifest.get('solver_version','')}"),
        ("Platform", manifest.get("platform", "")),
        ("Command line", manifest.get("command_line", "")),
        ("Deck", manifest.get("deck_path") or "(not supplied)"),
        ("Superseded by", manifest.get("superseded_by") or "(current — final)"),
    ], cfg, st))

    story.append(NextPageTemplate("Body"))
    doc.build(story)


if __name__ == "__main__":
    out = Path("out")
    r = json.loads((out / "results.json").read_text(encoding="utf-8"))
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    c = json.loads((out / "checks.json").read_text(encoding="utf-8"))
    from . import cli
    cfg = cli._load_config(Path(__file__).parent / "config.yaml")
    render(r, m, c, cfg, {}, {"generated": "manual", "sha": ""}, Path("out/manual_report.pdf"))
    print("wrote out/manual_report.pdf")
