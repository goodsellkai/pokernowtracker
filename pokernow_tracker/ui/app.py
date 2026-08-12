"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..store import Store
from . import theme
from .window import MainWindow


def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pokernow",
        description="Track PokerNow opponents and estimate their preflop ranges.",
    )
    parser.add_argument("files", nargs="*", help="hand history exports to open at startup")
    parser.add_argument("--data-dir", help="where to keep tracked data")
    args = parser.parse_args(list(argv) if argv is not None else None)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("PokerNow Tracker")
    app.setStyleSheet(theme.STYLESHEET)
    app.setFont(QFont("Segoe UI", 9))

    store = Store(Path(args.data_dir) if args.data_dir else None)
    window = MainWindow(store)
    window.show()

    if args.files:
        window.open_files([Path(name) for name in args.files])

    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
