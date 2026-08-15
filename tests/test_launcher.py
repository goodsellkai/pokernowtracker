"""The double-click launcher must work without a terminal or a shell."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("launch", ROOT / "launch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_exists_for_both_platforms():
    assert (ROOT / "launch.py").exists()
    assert (ROOT / "PokerNow Tracker.pyw").exists()      # Windows, no console
    assert (ROOT / "PokerNow Tracker.command").exists()  # macOS and Linux


def test_launcher_puts_the_package_on_the_path():
    module = _load()
    assert str(module.ROOT) in sys.path
    assert module.ROOT == ROOT


def test_launcher_detects_a_present_toolkit():
    pytest.importorskip("PySide6")
    assert _load()._has_toolkit() is True


def test_launcher_starts_the_application_when_ready(monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "_has_toolkit", lambda: True)

    started = {}
    import pokernow_tracker.ui as ui

    monkeypatch.setattr(ui, "run", lambda argv=None: started.setdefault("argv", argv) or 0)
    assert module.main([]) == 0
    assert "argv" in started


def test_launcher_gives_up_cleanly_when_install_is_declined(monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "_has_toolkit", lambda: False)
    monkeypatch.setattr(module, "_install_with_window", lambda: False)
    assert module.main([]) == 1
