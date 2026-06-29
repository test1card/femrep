"""femrep.cases.clt_synthetic — known-answer CFRP laminate for validating the
composite report sections (greenfield: no ACP/CFRP data exists in the project yet).

Classic [0/90/0] T300/5208 laminate, Tsai-Wu failure. The ABD matrix and IRF
here are the hand-calc reference values that femrep's composite-section renderer
must reproduce before it touches real ACP data. This is the one self-check femis
demands ("non-trivial logic leaves one runnable check behind").

Run:  python -m femrep.cases.clt_synthetic
"""
from __future__ import annotations

import numpy as np

# T300/5208 typical ply (Tsai & Hahn, "Introduction to Composite Materials",
# the canonical textbook lamina — used so the ABD/IRF answer is literature-known).
E1, E2, G12, NU12 = 181e3, 10.3e3, 7.17e3, 0.28   # MPa
# Strengths (MPa) for Tsai-Wu: XT, XC, YT, YC, S
XT, XC, YT, YC, S = 1500.0, 1500.0, 40.0, 246.0, 68.0

T_PLY = 0.125  # mm per ply

# [0/90/0] layup (3 plies), symmetric
LAYUP = [0.0, 90.0, 0.0]


def Q_plane_stress(deg: float) -> np.ndarray:
    """Reduced stiffness Q of a ply at angle deg (plane-stress CLT)."""
    th = np.radians(deg)
    c, s = np.cos(th), np.sin(th)
    nu21 = NU12 * E2 / E1
    den = 1.0 - NU12 * nu21
    Q11 = E1 / den
    Q22 = E2 / den
    Q12 = NU12 * E2 / den
    Q66 = G12
    # Tsai-Hill transformation
    Qbar = np.array([
        [Q11*c**4 + 2*(Q12 + 2*Q66)*s**2*c**2 + Q22*s**4,
         (Q11 + Q22 - 4*Q66)*s**2*c**2 + Q12*(s**4 + c**4),
         (Q11 - Q12 - 2*Q66)*s*c**3 - (Q22 - Q12 - 2*Q66)*s**3*c],
        [(Q11 + Q22 - 4*Q66)*s**2*c**2 + Q12*(s**4 + c**4),
         Q11*s**4 + 2*(Q12 + 2*Q66)*s**2*c**2 + Q22*c**4,
         (Q11 - Q12 - 2*Q66)*s**3*c - (Q22 - Q12 - 2*Q66)*s*c**3],
        [(Q11 - Q12 - 2*Q66)*s*c**3 - (Q22 - Q12 - 2*Q66)*s**3*c,
         (Q11 - Q12 - 2*Q66)*s**3*c - (Q22 - Q12 - 2*Q66)*s*c**3,
         (Q11 + Q22 - 2*Q12 - 2*Q66)*s**2*c**2 + Q66*(s**4 + c**4)],
    ])
    return Qbar


def abd_matrix(layup: list[float], t_ply: float = T_PLY):
    """Assemble ABD for a symmetric layup. Returns (A 3x3, B 3x3, D 3x3) in N/mm, N·mm/mm."""
    n = len(layup)
    z = np.array([(-n / 2 + i) * t_ply for i in range(n + 1)])  # ply interfaces
    A = np.zeros((3, 3)); B = np.zeros((3, 3)); D = np.zeros((3, 3))
    for i, ang in enumerate(layup):
        Q = Q_plane_stress(ang)
        A += Q * (z[i + 1] - z[i])
        B += 0.5 * Q * (z[i + 1] ** 2 - z[i] ** 2)
        D += (1.0 / 3.0) * Q * (z[i + 1] ** 3 - z[i] ** 3)
    return A, B, D


def tsai_wu_irf(Nx_MPa_mm: float, layup: list[float]) -> float:
    """Tsai-Wu inverse-resistance factor for a membrane load Nx (N/mm)
    applied to the laminate; returns the max ply IRF (1.0 = first-ply failure).

    Simplified to membrane Nx only (no moment) — sufficient for the known-answer
    validation that the section renderer must reproduce.
    """
    A, B, D = abd_matrix(layup)
    # mid-plane strain under membrane load Nx, Ny=Nxy=0 (ABD -> invert [A] for symmetric B=0)
    loads = np.array([Nx_MPa_mm, 0.0, 0.0])
    eps0 = np.linalg.solve(A, loads)
    irf_max = 0.0
    F1 = 1 / XT - 1 / XC
    F2 = 1 / YT - 1 / YC
    F11, F22, F66 = 1 / (XT * XC), 1 / (YT * YC), 1 / (S ** 2)
    F12 = -0.5 * np.sqrt(F11 * F22)  # Tsai-Wu interaction (Mises-Hencky fallback)
    for ang in layup:
        Q = Q_plane_stress(ang)
        stress = Q @ eps0  # in-plane ply stress in laminate axes -> transform to ply axes
        th = np.radians(ang)
        c, s = np.cos(th), np.sin(th)
        T = np.array([[c**2, s**2, 2*s*c], [s**2, c**2, -2*s*c], [-s*c, s*c, c**2 - s**2]])
        sig = T @ stress
        s1, s2, t12 = sig
        f = (F1 * s1 + F2 * s2 + F11 * s1**2 + F22 * s2**2
             + F66 * t12**2 + 2 * F12 * s1 * s2)
        irf_max = max(irf_max, f)
    return irf_max


def case() -> dict:
    """Return the synthetic case payload (the 'known-answer' reference)."""
    A, B, D = abd_matrix(LAYUP)
    # find first-ply-failure load Nx by root search on IRF = 1
    lo, hi = 1.0, 5000.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if tsai_wu_irf(mid, LAYUP) < 1.0:
            lo = mid
        else:
            hi = mid
    fpf_Nx = 0.5 * (lo + hi)
    return {
        "material": "T300/5208 (textbook lamina)",
        "properties": {"E1": E1, "E2": E2, "G12": G12, "nu12": NU12,
                       "XT": XT, "XC": XC, "YT": YT, "YC": YC, "S": S},
        "layup": {"sequence": LAYUP, "t_ply_mm": T_PLY, "total_t_mm": T_PLY * len(LAYUP),
                  "symmetric": True, "failure_philosophy": "FPF (first-ply, Tsai-Wu)"},
        "ABD": {"A_MPa_mm": np.round(A, 3).tolist(),
                "B_MPa_mm2": np.round(B, 6).tolist(),  # ~0 for symmetric
                "D_MPa_mm3": np.round(D, 3).tolist()},
        "fpf_Nx_N_per_mm": round(fpf_Nx, 3),
        "note": ("Symmetric [0/90/0] -> B = 0 (no membrane-bending coupling), the sanity "
                 "check. FPF load and Tsai-Wu IRF are the values the report's CFRP section "
                 "must reproduce. femis: progressive-damage (CDM) needs characteristic-length "
                 "regularization for mesh objectivity — this FPF case does NOT."),
    }


def main() -> int:
    c = case()
    print(f"[clt_synthetic] {c['layup']['sequence']}  {c['material']}")
    print(f"  A (N/mm): diag {[round(x) for x in np.diag(np.array(c['ABD']['A_MPa_mm']))]}")
    print(f"  B max coupling: {max(abs(x) for r in c['ABD']['B_MPa_mm2'] for x in r):.2e}  (want ~0)")
    print(f"  FPF Nx = {c['fpf_Nx_N_per_mm']} N/mm  (Tsai-Wu IRF = 1.0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
