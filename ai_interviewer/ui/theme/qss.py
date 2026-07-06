from __future__ import annotations

from typing import Callable

from ai_interviewer.ui.theme.tokens import Tokens


IconUrl = Callable[[str, str], str]


def _default_icon_url(name: str, color: str) -> str:
    from ai_interviewer.ui import icons

    return icons.tinted_svg_url(name, color)


def build_qss(t: Tokens, icon_url: IconUrl | None = None) -> str:
    """Generate the application stylesheet for one theme. Pure except for
    the tinted indicator SVGs written by `icon_url`."""
    url = icon_url or _default_icon_url
    chevron = url("chevron-down", t.muted)
    check = url("check", t.primary_contrast)

    return f"""
/* ---- base ---------------------------------------------------------- */
QWidget {{
    font-family: {t.font_stack};
    font-size: {t.size_body}pt;
    color: {t.ink};
}}
QMainWindow, QDialog {{
    background-color: {t.app_bg};
}}
QLabel {{
    background: transparent;
}}

/* ---- surfaces ------------------------------------------------------ */
QFrame[variant="card"] {{
    background-color: {t.surface};
    border: 1px solid {t.border};
    border-radius: {t.radius_lg}px;
}}
QFrame[variant="subtle"] {{
    background-color: {t.surface_alt};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
}}
QFrame[variant="hero"], QFrame[variant="stage"], QFrame[variant="rail"] {{
    background-color: {t.surface_deep};
    border: 1px solid {t.border};
    border-radius: {t.radius_lg}px;
}}
QFrame[variant="stage"] {{
    border-radius: {t.radius_md}px;
}}
QFrame[variant="plain"] {{
    background: transparent;
    border: none;
}}
QFrame[variant="questionPanel"] {{
    background-color: {t.selection};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
}}

/* ---- label roles ---------------------------------------------------- */
QLabel[role="display"] {{
    font-size: {t.size_display}pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="heroSubtitle"] {{
    font-size: {t.size_body}pt;
    color: {t.muted};
}}
QLabel[role="title"] {{
    font-size: {t.size_title}pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="section"] {{
    font-size: {t.size_section}pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="muted"], QLabel[role="subtitle"] {{
    font-size: {t.size_caption}pt;
    color: {t.muted};
}}
QLabel[role="kicker"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.primary};
}}
QLabel[role="railTitle"] {{
    font-size: 12pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="railMuted"] {{
    font-size: {t.size_caption}pt;
    color: {t.muted};
}}
QLabel[role="railAccent"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.accent};
}}
QLabel[role="metricLabel"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.muted};
}}
QLabel[role="metricValue"] {{
    font-family: {t.mono_stack};
    font-size: {t.size_metric}pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="status"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="success"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.success};
}}
QLabel[role="warning"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.warning};
}}
QLabel[role="danger"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.danger};
}}
QLabel[role="question"] {{
    font-size: {t.size_question}pt;
    color: {t.ink};
}}
QLabel[role="questionKicker"] {{
    font-size: {t.size_caption}pt;
    font-weight: 700;
    color: {t.accent};
}}
QLabel[role="choiceTitle"] {{
    font-size: 12pt;
    font-weight: 700;
    color: {t.ink};
}}
QLabel[role="choiceBody"] {{
    font-size: {t.size_caption}pt;
    color: {t.muted};
}}

/* ---- buttons -------------------------------------------------------- */
QPushButton {{
    background-color: {t.surface_alt};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
    padding: {t.sp[2]}px {t.sp[4]}px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {t.selection};
    border-color: {t.primary};
}}
QPushButton:pressed {{
    background-color: {t.selection};
    border-color: {t.primary_dark};
}}
QPushButton:focus {{
    border: 1px solid {t.focus_ring};
}}
QPushButton:disabled {{
    color: {t.muted};
    background-color: {t.surface_alt};
    border-color: {t.border};
}}
QPushButton[kind="primary"] {{
    background-color: {t.primary};
    color: {t.primary_contrast};
    border: 1px solid {t.primary};
    font-weight: 700;
    padding: {t.sp[2]}px {t.sp[4]}px;
}}
QPushButton[kind="primary"]:hover {{
    background-color: {t.primary_dark};
    border-color: {t.primary_dark};
}}
QPushButton[kind="primary"]:pressed {{
    background-color: {t.primary_dark};
}}
QPushButton[kind="primary"]:focus {{
    border: 1px solid {t.glow};
}}
QPushButton[kind="primary"]:disabled {{
    background-color: {t.surface_alt};
    color: {t.muted};
    border-color: {t.border};
}}
QPushButton[kind="tool"], QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid {t.border};
    font-weight: 500;
    padding: {t.sp[1] + 2}px {t.sp[3]}px;
}}
QPushButton[kind="ghost"] {{
    border-color: transparent;
    color: {t.muted};
}}
QPushButton[kind="tool"]:hover, QPushButton[kind="ghost"]:hover {{
    background-color: {t.surface_alt};
    border-color: {t.primary};
    color: {t.ink};
}}
QPushButton[kind="tool"]:disabled, QPushButton[kind="ghost"]:disabled {{
    color: {t.muted};
    background: transparent;
    border-color: {t.border};
}}
QPushButton[kind="danger"] {{
    background: transparent;
    color: {t.danger};
    border: 1px solid {t.danger};
}}
QPushButton[kind="danger"]:hover {{
    background-color: {t.danger};
    color: {t.primary_contrast};
}}
/* Dense grids (session controls): keep labels un-truncated. */
QPushButton[dense="true"] {{
    padding: {t.sp[1] + 2}px {t.sp[1]}px;
    font-size: {t.size_caption}pt;
}}

QToolButton[seg="true"] {{
    background: transparent;
    color: {t.muted};
    border: 1px solid {t.border};
    border-radius: {t.radius_sm}px;
    padding: {t.sp[1]}px {t.sp[3]}px;
    font-weight: 600;
}}
QToolButton[seg="true"]:hover {{
    color: {t.ink};
    border-color: {t.primary};
}}
QToolButton[seg="true"]:checked {{
    background-color: {t.selection};
    color: {t.ink};
    border-color: {t.primary};
}}

/* ---- inputs ---------------------------------------------------------- */
QLineEdit {{
    background-color: {t.surface_alt};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_sm}px;
    padding: {t.sp[1] + 1}px {t.sp[2]}px;
    selection-background-color: {t.selection};
    selection-color: {t.ink};
}}
QLineEdit:focus {{
    border: 1px solid {t.focus_ring};
}}
QLineEdit:disabled {{
    color: {t.muted};
}}

QPlainTextEdit, QTextEdit {{
    background-color: {t.surface_deep};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
    padding: {t.sp[2]}px;
    selection-background-color: {t.selection};
    selection-color: {t.ink};
}}
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {t.focus_ring};
}}
QPlainTextEdit[readOnly="true"] {{
    color: {t.muted};
}}

QComboBox {{
    background-color: {t.surface_alt};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_sm}px;
    padding: {t.sp[1] + 1}px {t.sp[2]}px;
    min-height: 1.4em;
}}
QComboBox:hover {{
    border-color: {t.primary};
}}
QComboBox:focus {{
    border: 1px solid {t.focus_ring};
}}
QComboBox:disabled {{
    color: {t.muted};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: url("{chevron}");
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.surface};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_sm}px;
    selection-background-color: {t.selection};
    selection-color: {t.ink};
    outline: none;
    padding: {t.sp[1]}px;
}}

QCheckBox, QRadioButton {{
    background: transparent;
    color: {t.ink};
    spacing: {t.sp[2]}px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {t.muted};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {t.border};
    background-color: {t.surface_alt};
    border-radius: {t.radius_sm}px;
}}
QCheckBox::indicator:hover {{
    border-color: {t.primary};
}}
QCheckBox::indicator:checked {{
    background-color: {t.primary};
    border-color: {t.primary};
    image: url("{check}");
}}
/* QRadioButton::indicator is intentionally NOT styled: a QSS box turns the
   round Fusion indicator into a squircle at fractional DPI. Fusion draws
   radios from the palette, which the ThemeManager keeps token-consistent. */

/* ---- tabs ------------------------------------------------------------ */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {t.border};
    background: transparent;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {t.muted};
    border: none;
    border-bottom: 2px solid transparent;
    padding: {t.sp[1] + 2}px {t.sp[3]}px;
    margin-right: {t.sp[1]}px;
    font-weight: 600;
    font-size: {t.size_caption}pt;
}}
QTabBar::tab:hover {{
    color: {t.ink};
}}
QTabBar::tab:selected {{
    color: {t.ink};
    border-bottom: 2px solid {t.primary};
}}

/* ---- progress / lists ------------------------------------------------ */
QProgressBar {{
    background-color: {t.surface_alt};
    border: 1px solid {t.border};
    border-radius: {t.radius_sm}px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {t.primary};
    border-radius: {t.radius_sm - 1}px;
}}

QTableView {{
    background-color: {t.surface};
    alternate-background-color: {t.surface_alt};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
    gridline-color: transparent;
    selection-background-color: {t.selection};
    selection-color: {t.ink};
    outline: none;
}}
QTableView::item {{
    padding: {t.sp[1]}px {t.sp[2]}px;
    border: none;
}}
QHeaderView::section {{
    background-color: {t.surface};
    color: {t.muted};
    border: none;
    border-bottom: 1px solid {t.border};
    padding: {t.sp[1] + 2}px {t.sp[2]}px;
    font-weight: 700;
    font-size: {t.size_caption}pt;
}}
QTableCornerButton::section {{
    background-color: {t.surface};
    border: none;
    border-bottom: 1px solid {t.border};
}}

/* ---- scrollbars ------------------------------------------------------ */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background-color: {t.border};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t.muted};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background-color: {t.border};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {t.muted};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ---- menus / tooltips ------------------------------------------------ */
QMenu {{
    background-color: {t.surface};
    color: {t.ink};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
    padding: {t.sp[1]}px;
}}
QMenu::item {{
    padding: {t.sp[1] + 2}px {t.sp[4]}px;
    border-radius: {t.radius_sm}px;
}}
QMenu::item:selected {{
    background-color: {t.selection};
}}
QToolTip {{
    background-color: {t.surface_deep};
    color: {t.ink};
    border: 1px solid {t.border};
    padding: {t.sp[1]}px {t.sp[2]}px;
}}

/* ---- message boxes --------------------------------------------------- */
QMessageBox {{
    background-color: {t.surface};
}}
QMessageBox QLabel {{
    color: {t.ink};
}}

/* ---- video stage ------------------------------------------------------ */
QLabel[role="videoStage"] {{
    background-color: {t.video_bg};
    color: {t.muted};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
    font-size: {t.size_caption}pt;
    font-weight: 600;
}}

/* ---- custom widgets --------------------------------------------------- */
ChoiceCard {{
    background-color: {t.surface_alt};
    border: 1px solid {t.border};
    border-radius: {t.radius_md}px;
}}
ChoiceCard:hover {{
    border-color: {t.primary};
}}
ChoiceCard[selected="true"] {{
    background-color: {t.selection};
    border-color: {t.primary};
}}
ChoiceCard:focus {{
    border: 1px solid {t.focus_ring};
}}
ChoiceCard QFrame[accentBar="true"] {{
    background-color: {t.border};
    border: none;
    border-radius: 2px;
}}
ChoiceCard[selected="true"] QFrame[accentBar="true"] {{
    background-color: {t.accent};
}}
ChoiceCard[selected="true"] QLabel[role="choiceBody"] {{
    color: {t.glow};
}}
"""
