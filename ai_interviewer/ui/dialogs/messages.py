from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from ai_interviewer.i18n import tr


def _resolve_parent(parent: QWidget | None) -> QWidget | None:
    return parent if parent is not None else QApplication.activeWindow()


def _box(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
) -> QMessageBox:
    box = QMessageBox(_resolve_parent(parent))
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    return box


def info(parent: QWidget | None, title: str, text: str) -> None:
    box = _box(parent, QMessageBox.Icon.Information, title, text)
    box.addButton(tr("common.ok"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def warning(parent: QWidget | None, title: str, text: str) -> None:
    box = _box(parent, QMessageBox.Icon.Warning, title, text)
    box.addButton(tr("common.ok"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def error(parent: QWidget | None, title: str, text: str) -> None:
    box = _box(parent, QMessageBox.Icon.Critical, title, text)
    box.addButton(tr("common.ok"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def ask_yes_no(parent: QWidget | None, title: str, text: str) -> bool:
    box = _box(parent, QMessageBox.Icon.Question, title, text)
    yes = box.addButton(tr("common.yes"), QMessageBox.ButtonRole.YesRole)
    box.addButton(tr("common.no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(yes)
    box.exec()
    return box.clickedButton() is yes
