"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..store import Store
from . import theme
from .window import MainWindow


def _files_from(argv: Optional[Sequence[str]]) -> List[Path]:
    """Hand histories passed in by a file association or a drop on the icon.

    Anything that is not a readable file is ignored rather than reported: with
    no terminal attached there is nowhere to report it, and the window is about
    to open regardless.
    """
    given = list(argv) if argv is not None else sys.argv[1:]
    return [Path(name) for name in given if Path(name).is_file()]


def _close_splash() -> None:
    """Dismiss the packaged build's startup panel once there is a window."""
    try:
        import pyi_splash  # injected only into a packaged build
    except ImportError:
        return
    try:
        pyi_splash.close()
    except Exception:  # the panel is cosmetic, never a reason to fail startup
        pass


def run(argv: Optional[Sequence[str]] = None) -> int:
    app = QApplication(sys.argv[:1])
    app.setApplicationName("PokerNow Tracker")
    app.setStyleSheet(theme.STYLESHEET)
    app.setFont(QFont("Segoe UI", 9))

    window = MainWindow(Store())
    window.show()
    _close_splash()

    files = _files_from(argv)
    if files:
        window.open_files(files)

    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
