"""Developer-only widget gallery: every themed control in one window.

Run with:  python -m ai_interviewer.ui.dev_gallery
Use the System/Light/Dark segment to eyeball both palettes live. Not shipped
behavior — nothing here touches the user's config file.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QTabWidget,
    QWidget,
)

from ai_interviewer.config import AppConfig
from ai_interviewer.i18n import set_language
from ai_interviewer.ui.state import Prop


def main() -> int:
    from ai_interviewer.ui.app import create_app
    from ai_interviewer.ui.theme.manager import ThemeManager

    app = create_app([])
    set_language("ko")
    config = AppConfig(config_path=os.devnull)  # never persisted
    config.ui_theme_mode = "dark"
    manager = ThemeManager(config)
    # Keep the gallery's theme switch off the real config file.
    config.save = lambda *args, **kwargs: None  # type: ignore[method-assign]
    manager.apply(app)

    window = _build_window()
    window.resize(1280, 860)
    window.show()
    return app.exec()


def _build_window() -> QWidget:
    from ai_interviewer.ui.screens.wizard import build_theme_selector
    from ai_interviewer.ui.widgets import cards
    from ai_interviewer.ui.widgets.buttons import IconButton
    from ai_interviewer.ui.widgets.choice_card import ChoiceCard
    from ai_interviewer.ui.widgets.signal_widget import SignalWidget
    from ai_interviewer.ui.widgets.step_rail import StepRail
    from ai_interviewer.ui.widgets.text_edit import make_text_edit

    root = QWidget()
    root.setWindowTitle("AI Interviewer - Theme Gallery (dev)")
    outer = QHBoxLayout(root)
    outer.setContentsMargins(18, 18, 18, 18)
    outer.setSpacing(16)

    rail = cards.frame("rail")
    rail_layout = cards.vbox(rail, 16, 8)
    rail_layout.addWidget(cards.label("AI Interviewer", "display"))
    rail_layout.addWidget(cards.label("theme gallery", "railAccent"))
    rail_layout.addWidget(SignalWidget(height=120, animated=True))
    rail_layout.addWidget(StepRail(("언어", "모델", "화자", "질문", "검토"), 2), 1)
    rail.setFixedWidth(280)
    outer.addWidget(rail)

    main_card = cards.frame("card")
    layout = cards.vbox(main_card, 20, 12)
    layout.addWidget(cards.section_header("위젯 갤러리", "모든 컨트롤 상태를 두 테마에서 확인"))
    layout.addWidget(build_theme_selector(main_card))

    buttons = QHBoxLayout()
    buttons.setSpacing(8)
    buttons.addWidget(IconButton("면접 시작", icon_name="play", kind="primary"))
    buttons.addWidget(IconButton("녹음", icon_name="mic", kind="secondary"))
    buttons.addWidget(IconButton("다시 듣기", icon_name="rotate-ccw", kind="tool"))
    buttons.addWidget(IconButton("삭제", icon_name="x", kind="danger"))
    disabled = IconButton("비활성", icon_name="mic-off")
    disabled.setEnabled(False)
    buttons.addWidget(disabled)
    buttons.addStretch(1)
    layout.addLayout(buttons)

    inputs = QHBoxLayout()
    inputs.setSpacing(8)
    combo = QComboBox()
    combo.addItems(["Sohee", "Ryan", "Aiden"])
    inputs.addWidget(combo)
    inputs.addWidget(QLineEdit("http://127.0.0.1:11434"))
    check = QCheckBox("사운드 테스트 필수")
    check.setChecked(True)
    inputs.addWidget(check)
    radio = QRadioButton("한국어")
    radio.setChecked(True)
    inputs.addWidget(radio)
    inputs.addStretch(1)
    layout.addLayout(inputs)

    progress = QProgressBar()
    progress.setRange(0, 1000)
    progress.setValue(640)
    progress.setTextVisible(False)
    layout.addWidget(progress)

    choices = QHBoxLayout()
    choices.setSpacing(10)
    selected = ChoiceCard("1.7B CustomVoice (권장)", "설치됨\n톤 제어 지원", selected=True)
    other = ChoiceCard("0.6B CustomVoice", "다운로드 필요 (약 1.4 GB)\n빠른 응답", selected=False)
    selected.clicked.connect(lambda: (selected.set_selected(True), other.set_selected(False)))
    other.clicked.connect(lambda: (other.set_selected(True), selected.set_selected(False)))
    choices.addWidget(selected)
    choices.addWidget(other)
    layout.addLayout(choices)

    metrics = QHBoxLayout()
    metrics.setSpacing(8)
    for name, value in (("진행", "3 / 20"), ("답변", "01:24"), ("전체", "12:07")):
        metrics.addWidget(cards.metric_tile(name, Prop(value)))
    layout.addLayout(metrics)

    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    memo = make_text_edit()
    memo.setPlainText("메모...")
    tabs.addTab(memo, "메모")
    tabs.addTab(make_text_edit(read_only=True), "전사(STT)")
    layout.addWidget(tabs, 1)

    panel = cards.frame("questionPanel")
    panel_layout = cards.vbox(panel, 16, 6)
    panel_layout.addWidget(cards.label("현재 질문", "questionKicker"))
    panel_layout.addWidget(cards.label("자기소개를 1분 이내로 해 주세요.", "question", wrap=True))
    layout.addWidget(panel)

    outer.addWidget(main_card, 1)
    return root


if __name__ == "__main__":
    sys.exit(main())
