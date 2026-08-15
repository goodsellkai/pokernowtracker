"""Double-click this file to start PokerNow Tracker.

The .pyw extension tells Windows to run it with pythonw, so no console window
appears. Everything happens in launch.py next to this file.
"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "launch.py"), run_name="__main__")
