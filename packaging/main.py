"""Entry point for the packaged application.

The packaged build already contains everything it needs, so this skips the
dependency check in ``launch.py`` and starts the interface directly.
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    multiprocessing.freeze_support()  # a frozen child process must not re-run main

    from pokernow_tracker.ui import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
