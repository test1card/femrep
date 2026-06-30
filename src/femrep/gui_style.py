"""femrep.gui_style — design tokens + QSS for the GUI.

Derived from the minimalist-ui design system: warm monochrome canvas, off-black
text, ultra-light borders, crisp small radii, near-zero shadows, dark solid CTA,
muted pastel status badges. No gradients, no heavy shadows, no pill containers.
"""
from __future__ import annotations

# palette
CANVAS = "#F7F6F3"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#FBFBFA"
BORDER = "#EAEAEA"
INK = "#2F3437"
MUTED = "#787774"
INK_SOLID = "#111111"
# pastel status pairs (bg, fg)
OK = ("#EDF3EC", "#346538")
WARN = ("#FBF3DB", "#956400")
BAD = ("#FDEBEC", "#9F2F2D")

FONT_STACK = '"SF Pro Text", "Helvetica Neue", "Segoe UI", system-ui, sans-serif'

QSS = f"""
* {{ font-family: {FONT_STACK}; color: {INK}; font-size: 13px; }}
#canvas {{ background: {CANVAS}; }}

/* left step rail */
#rail {{ background: {SURFACE_ALT}; border-right: 1px solid {BORDER}; }}
#brand {{ font-size: 17px; font-weight: 700; letter-spacing: -0.02em; }}
#brandsub {{ color: {MUTED}; font-size: 11px; }}
QLabel[role="step"] {{ color: {MUTED}; font-size: 13px; padding: 9px 10px; border-radius: 8px; }}
QLabel[role="step"][active="true"] {{ color: {INK}; background: #EFEEE9; font-weight: 600; }}
#num {{ background: {BORDER}; color: {MUTED}; border-radius: 11px;
        min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; font-size: 12px; }}
#num[active="true"] {{ background: {INK_SOLID}; color: #FFFFFF; }}
#num[done="true"] {{ background: {OK[0]}; color: {OK[1]}; }}

/* content card */
#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
#h2 {{ font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }}
#sub {{ color: {MUTED}; font-size: 13px; }}
#section {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; }}
#drop {{ border: 1.5px dashed #D9D8D3; border-radius: 10px; background: {SURFACE_ALT};
         color: {MUTED}; font-size: 13px; }}

/* inputs */
QLineEdit, QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
                        padding: 7px 10px; selection-background-color: #E1F3FE; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid #C9C8C2; }}
QComboBox::drop-down {{ border: none; width: 22px; }}

/* buttons */
QPushButton#cta {{ background: {INK_SOLID}; color: #FFFFFF; border: none; border-radius: 7px;
                   padding: 10px 20px; font-size: 13px; font-weight: 600; }}
QPushButton#cta:hover {{ background: #333333; }}
QPushButton#cta:disabled {{ background: #C9C8C2; color: #FFFFFF; }}
QPushButton#ghost {{ background: transparent; color: {INK}; border: 1px solid {BORDER};
                     border-radius: 7px; padding: 10px 18px; font-size: 13px; }}
QPushButton#ghost:hover {{ background: {SURFACE_ALT}; }}
QPushButton#opt {{ background: {SURFACE}; color: {INK}; border: 1px solid {BORDER};
                   border-radius: 7px; padding: 8px 14px; font-size: 12px; }}
QPushButton#opt:hover {{ border: 1px solid #C9C8C2; }}

/* status badges (set property badge = ok|warn|bad) */
QLabel[badge="ok"] {{ background: {OK[0]}; color: {OK[1]}; border-radius: 9px; padding: 4px 10px;
                      font-size: 11px; font-weight: 600; }}
QLabel[badge="warn"] {{ background: {WARN[0]}; color: {WARN[1]}; border-radius: 9px; padding: 4px 10px;
                        font-size: 11px; font-weight: 600; }}
QLabel[badge="bad"] {{ background: {BAD[0]}; color: {BAD[1]}; border-radius: 9px; padding: 4px 10px;
                       font-size: 11px; font-weight: 600; }}

QScrollArea {{ border: none; background: transparent; }}
QListWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: #EFEEE9; color: {INK}; }}
"""
