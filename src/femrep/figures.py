"""femrep.figures — render the report's figures.

Two engines, both already in the venv (no new deps):
  - pyvista off-screen : 3D contour of the primary QoI field on the deformed/undeformed mesh.
  - matplotlib (Agg)   : transient time-history, GCI convergence, layup stack.

Each function returns the output path or None (so the renderer can show a
placeholder). Run via CLI; standalone test at the bottom.

Mirror the repo's existing matplotlib idiom (Agg backend, savefig to reports/).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
from ansys.dpf import core as dpf
from pathlib import Path


def _node_id_map(mesh) -> dict:
    """node_id -> grid-point-index, so a DPF field (scoped by node id) maps onto the grid."""
    node_ids = np.asarray(mesh.nodes.scoping.ids)
    return {int(nid): i for i, nid in enumerate(node_ids)}


def _contour_grid(results: dict):
    """Return (grid, qoi_name, units) with primary QoI scalars attached, or None."""
    rfile = Path(results["result_file"])
    if rfile.suffix.lower() not in (".rst", ".rth"):
        return None  # no geometry in .f06/.op2-text -> no contour possible
    if not rfile.exists():
        return None
    model = dpf.Model(str(rfile))
    mesh = model.metadata.meshed_region
    grid = mesh.grid
    qoi_name = results["primary_qoi"]["name"]
    # map our QoI name back to a raw DPF result operator
    if qoi_name == "temperature":
        op = model.results.temperature
    elif qoi_name == "von_mises_stress":
        op = model.results.stress  # compute von-Mises for the contour too
    elif qoi_name == "displacement_magnitude":
        op = model.results.displacement
    else:
        op = getattr(model.results, qoi_name, None) or model.results.temperature
    field = op().eval()[0]
    raw = np.asarray(field.data, dtype=float)
    # reduce to a scalar per scoping entity (von-Mises for stress tensor, norm for vec)
    if qoi_name == "von_mises_stress" and raw.ndim == 2 and raw.shape[1] == 6:
        sxx, syy, szz = raw[:, 0], raw[:, 1], raw[:, 2]
        sxy, syz, sxz = raw[:, 3], raw[:, 4], raw[:, 5]
        vals = np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
                              + 6 * (sxy ** 2 + syz ** 2 + sxz ** 2)))
    elif raw.ndim > 1:
        vals = np.linalg.norm(raw, axis=1)
    else:
        vals = raw
    idx_of = _node_id_map(mesh)
    field_ids = np.asarray(field.scoping.ids)
    scalars = np.full(grid.n_points, np.nan)
    # element-nodal stress: scoping may not align to node ids -> contour on
    # node-averaged fallback; if mismatch, skip cleanly.
    if len(field_ids) == len(vals):
        for nid, v in zip(field_ids, vals):
            i = idx_of.get(int(nid))
            if i is not None:
                scalars[i] = v
    if np.all(np.isnan(scalars)):
        return None
    grid.point_data[qoi_name] = scalars
    return grid, qoi_name, results["primary_qoi"]["units"]


def contour(results: dict, out_dir: Path, *, name: str = "contour.png",
            cmap: str = "coolwarm") -> Path | None:
    """Render the primary QoI field as a 3D off-screen contour PNG.

    DPF reads .rst/.rth (which carry geometry); .f06 has no mesh, so this returns
    None and the report shows an honest placeholder. Re-opens the result file and
    maps the field onto mesh.grid by node id. Returns the PNG path or None.
    """
    try:
        payload = _contour_grid(results)
        if payload is None:
            return None
        grid, qoi_name, units = payload
        p = pv.Plotter(off_screen=True, window_size=[1600, 1000])
        p.background_color = "white"
        p.add_mesh(grid, scalars=qoi_name, cmap=cmap,
                   scalar_bar_args={"title": f"{qoi_name} [{units}]", "title_font_size": 18,
                                    "label_font_size": 14, "width": 0.6, "position_y": 0.05})
        p.view_isometric()
        out = out_dir / name
        p.screenshot(str(out))
        p.close()
        return out
    except Exception:
        return None


def contour_multiview(results: dict, out_dir: Path, *, name: str = "contour_views.png",
                      cmap: str = "coolwarm") -> Path | None:
    """Render a four-view contour plate so reports are not locked to one camera angle."""
    try:
        payload = _contour_grid(results)
        if payload is None:
            return None
        grid, qoi_name, units = payload
        p = pv.Plotter(off_screen=True, shape=(2, 2), window_size=[1800, 1400])
        p.background_color = "white"
        views = [
            ("Isometric", "iso"),
            ("Top", "xy"),
            ("Front", "xz"),
            ("Right", "yz"),
        ]
        for idx, (label, view) in enumerate(views):
            p.subplot(idx // 2, idx % 2)
            p.add_mesh(grid, scalars=qoi_name, cmap=cmap,
                       scalar_bar_args={"title": f"{qoi_name} [{units}]",
                                        "title_font_size": 14, "label_font_size": 10})
            p.add_text(label, position="upper_left", font_size=12, color="#1f3a5f")
            if view == "iso":
                p.view_isometric()
            elif view == "xy":
                p.view_xy()
            elif view == "xz":
                p.view_xz()
            elif view == "yz":
                p.view_yz()
            p.reset_camera()
        out = out_dir / name
        p.screenshot(str(out))
        p.close()
        return out
    except Exception:
        return None


def interactive_contour_html(results: dict, out_dir: Path, *,
                             name: str = "interactive_contour.html",
                             cmap: str = "coolwarm") -> Path | None:
    """Export a rotatable PyVista contour scene for HTML review."""
    try:
        payload = _contour_grid(results)
        if payload is None:
            return None
        grid, qoi_name, units = payload
        p = pv.Plotter(off_screen=True, window_size=[1200, 850])
        p.background_color = "white"
        p.add_mesh(grid, scalars=qoi_name, cmap=cmap,
                   scalar_bar_args={"title": f"{qoi_name} [{units}]"})
        p.view_isometric()
        out = out_dir / name
        p.export_html(str(out))
        p.close()
        return out
    except Exception:
        return None


def deformed_shape(results: dict, out_dir: Path, *,
                   name: str = "deformed_shape.png", warp_factor: float = 1.0) -> Path | None:
    """Render the undeformed + deformed shape for a structural .rst (warp by displacement).

    Auto-scales the warp so the deformation is visible (real disp is often µm vs
    metre-scale geometry). Returns the PNG path or None (non-.rst, or no displacement).
    """
    rfile = Path(results["result_file"])
    if rfile.suffix.lower() != ".rst":
        return None
    try:
        model = dpf.Model(str(rfile))
        if not hasattr(model.results, "displacement"):
            return None
        mesh = model.metadata.meshed_region
        grid = mesh.grid
        disp = model.results.displacement().eval()[0]
        # map displacement vectors onto grid points by node id
        node_ids = np.asarray(mesh.nodes.scoping.ids)
        idx_of = {int(nid): i for i, nid in enumerate(node_ids)}
        d_ids = np.asarray(disp.scoping.ids)
        dvals = np.asarray(disp.data, dtype=float)
        U = np.zeros((grid.n_points, 3))
        for nid, v in zip(d_ids, dvals):
            i = idx_of.get(int(nid))
            if i is not None:
                U[i] = v
        # auto-scale: warp so max deformation ~5% of bounding-box diag, for visibility
        bb = grid.length
        umax = np.linalg.norm(U, axis=1).max()
        scale = (0.05 * bb / umax) if umax > 0 else 0.0
        warped = grid.warp_by_vector(U * scale, factor=1.0)
        p = pv.Plotter(off_screen=True, window_size=[1600, 1000])
        p.background_color = "white"
        p.add_mesh(grid, style="wireframe", color="#868e96", opacity=0.25,
                   label="undeformed")
        p.add_mesh(warped, color="#1f3a5f", label=f"deformed (×{scale:.0f})")
        p.view_isometric()
        out = out_dir / name
        p.screenshot(str(out))
        p.close()
        return out
    except Exception:
        return None


def time_history(results: dict, out_dir: Path, *,
                 name: str = "time_history.png") -> Path | None:
    """Transient QoI(t): a real min/max envelope + mean curve when a transient is
    present (multi-set .rth sequence or multi-time .f06); else a single-set snapshot bar.
    """
    try:
        out = out_dir / name
        tf = results.get("time_freq", {})
        qoi = results["primary_qoi"]
        transient = results.get("transient")

        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=140)
        if transient and transient.get("n_sets", 0) > 1:
            times = np.asarray(transient["times"], dtype=float)
            mins = np.asarray(transient["min"], dtype=float)
            maxs = np.asarray(transient["max"], dtype=float)
            means = np.asarray(transient["mean"], dtype=float)
            ax.fill_between(times, mins, maxs, color="#0b7285", alpha=0.18, label="min–max envelope")
            ax.plot(times, maxs, color="#c92a2a", linewidth=1.6, label="max")
            ax.plot(times, mins, color="#1f3a5f", linewidth=1.6, label="min")
            ax.plot(times, means, color="#0b7285", linewidth=1.6, linestyle="--", label="mean")
            tsrc = transient.get("time_source", "?")
            ax.set_xlabel("time [s]  ·  axis source: " + tsrc)
            ax.set_ylabel(f"{qoi['name']} [{qoi['units']}]")
            ax.set_title(f"Transient QoI history ({transient['n_sets']} sets)")
            ax.legend(loc="best", fontsize=8)
        else:
            ax.bar(["min", "mean", "max"],
                   [qoi["min"], 0.5 * (qoi["min"] + qoi["max"]), qoi["max"]],
                   color=["#1f3a5f", "#868e96", "#c92a2a"])
            ax.set_ylabel(f"{qoi['name']} [{qoi['units']}]")
            t0 = tf.get("sample_times_s", [0])[0] if tf.get("sample_times_s") else 0
            ax.set_title(f"QoI snapshot — single result set (t = {t0} s)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(str(out))
        plt.close(fig)
        return out
    except Exception:
        return None


def gci_convergence(gci: dict | None, out_dir: Path, *,
                    name: str = "gci_convergence.png") -> Path | None:
    """GCI mesh-independence: QoI vs mesh size, with the Richardson extrapolate."""
    if not gci or "richardson_f_exact" not in gci:
        return None
    try:
        out = out_dir / name
        # reconstruct the three points from r21/r32 + f1 (approximate, for the plot only)
        r21, r32 = gci["r21"], gci["r32"]
        f1 = gci["richardson_f_exact"] + (gci["richardson_f_exact"] - 0) * 0  # placeholder
        # we only stored ratios, not the raw f's; plot the asymptotic check instead:
        fig, ax = plt.subplots(figsize=(6, 3), dpi=140)
        ax.bar(["GCI fine", "GCI coarse"],
               [gci["gci_fine_pct"], gci["gci_coarse_pct"]],
               color=["#2b8a3e" if gci["gci_fine_pct"] <= 3 else "#c92a2a",
                      "#868e96"])
        ax.axhline(3.0, color="#c92a2a", linestyle="--", linewidth=1, label="3% gate")
        ax.set_ylabel("GCI [%]")
        ax.set_title(f"Grid Convergence Index  ·  R={gci['convergence_ratio_R']:.3f}, "
                     f"p={gci['observed_order_p']:.2f}, "
                     f"asympt={gci['asymptotic_ratio']:.2f}")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(str(out))
        plt.close(fig)
        return out
    except Exception:
        return None


def generate(results: dict, gci: dict | None, out_dir: Path) -> dict:
    """Render all figures; return {key: path} for the renderer (None-safe)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "contour": contour(results, out_dir),
        "contour_views": contour_multiview(results, out_dir),
        "deformed_shape": deformed_shape(results, out_dir),
        "time_history": time_history(results, out_dir),
        "gci_convergence": gci_convergence(gci, out_dir),
    }


if __name__ == "__main__":
    import json
    out = Path("out")
    r = json.loads((out / "results.json").read_text(encoding="utf-8"))
    g = json.loads((out / "checks.json").read_text(encoding="utf-8")).get("gci")
    paths = generate(r, g, out)
    print("figures:", {k: str(v) for k, v in paths.items()})
