"""Start PokerNow Tracker, installing what it needs on first run.

This exists so the application can be opened by double-clicking, with no
terminal involved. On Windows use ``PokerNow Tracker.pyw``, which runs this
without opening a console window.

The interface toolkit is a large download, so the first launch offers to fetch
it and reports progress in a small window built from the standard library.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

REQUIREMENT = "PySide6>=6.5"
PACKAGE = "PySide6"

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _has_toolkit() -> bool:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return False
    return True


def _plain_install() -> bool:
    """Fallback when even tkinter is unavailable."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", REQUIREMENT],
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return _has_toolkit()


def _install_with_window() -> bool:
    """Ask permission, then install while showing progress."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        return _plain_install()

    root = tk.Tk()
    root.withdraw()
    approved = messagebox.askyesno(
        "PokerNow Tracker",
        "PokerNow Tracker needs its interface toolkit (PySide6) before it can "
        "start.\n\nDownload and install it now? This takes a minute or two and "
        "only happens once.",
    )
    if not approved:
        root.destroy()
        return False

    root.deiconify()
    root.title("PokerNow Tracker")
    root.geometry("380x120")
    root.resizable(False, False)
    root.configure(bg="#101319")

    label = tk.Label(
        root,
        text="Installing the interface toolkit...\nThis only happens once.",
        bg="#101319",
        fg="#dfe3ea",
        font=("Segoe UI", 10),
        justify="left",
    )
    label.pack(expand=True, padx=20, pady=20)

    outcome: dict[str, object] = {}

    def work() -> None:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pip", "install", REQUIREMENT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            outcome["code"] = completed.returncode
            outcome["output"] = completed.stdout or ""
        except (subprocess.SubprocessError, OSError) as error:  # pragma: no cover
            outcome["code"] = 1
            outcome["output"] = str(error)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    while thread.is_alive():
        root.update()
        thread.join(0.1)
    root.destroy()

    if outcome.get("code") == 0 and _has_toolkit():
        return True

    tail = str(outcome.get("output", "")).strip().splitlines()[-6:]
    failure = tk.Tk()
    failure.withdraw()
    messagebox.showerror(
        "PokerNow Tracker",
        "The interface toolkit could not be installed.\n\n"
        + "\n".join(tail)
        + f"\n\nYou can install it yourself with:\n"
        f"{Path(sys.executable).name} -m pip install {PACKAGE}",
    )
    failure.destroy()
    return False


def main(argv: list[str] | None = None) -> int:
    if not _has_toolkit() and not _install_with_window():
        return 1

    from pokernow_tracker.ui import run

    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
