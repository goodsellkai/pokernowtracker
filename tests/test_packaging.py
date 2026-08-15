"""The packaged build is what most people download, so its inputs are checked.

The build itself is too slow for the test suite, but everything it depends on
being correct is verified here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"


def test_the_spec_is_valid_python():
    ast.parse((PACKAGING / "pokernow.spec").read_text(encoding="utf-8"))


def test_the_spec_keeps_the_modules_the_interface_uses():
    text = (PACKAGING / "pokernow.spec").read_text(encoding="utf-8")
    namespace: dict = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and node.targets[0].id in {"QT_KEEP", "QT_DROP"}:
            namespace[node.targets[0].id] = ast.literal_eval(node.value)

    # Excluding a module the interface imports produces a build that starts and
    # then dies, which is the worst failure to discover after publishing.
    assert namespace["QT_KEEP"] == {"QtCore", "QtGui", "QtWidgets"}
    assert not namespace["QT_KEEP"] & set(namespace["QT_DROP"])

    # shiboken6 is the binding layer itself, never a candidate for exclusion.
    assert "shiboken6" not in text.split("icon_windows")[0]


def test_the_packaged_entry_point_starts_the_interface(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("packaged_main", PACKAGING / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import pokernow_tracker.ui as ui

    called = {}

    def fake_run(argv=None):
        called["ran"] = True
        return 0

    monkeypatch.setattr(ui, "run", fake_run)
    assert module.main() == 0
    assert called["ran"]


def test_the_icon_renders_at_every_size_the_platforms_ask_for(app, tmp_path):
    import sys

    sys.path.insert(0, str(PACKAGING))
    import icon as icon_module

    written = icon_module.write(tmp_path)
    assert written.exists() and written.stat().st_size > 0

    # macOS refuses a .iconset that is missing any expected size.
    iconset = tmp_path / "pokernow.iconset"
    for size in icon_module.ICNS_SIZES:
        assert (iconset / f"icon_{size}x{size}.png").exists()
        if size <= 512:
            assert (iconset / f"icon_{size}x{size}@2x.png").exists()

    image = icon_module.render(64)
    assert image.width() == 64 and image.height() == 64
    # The centre of the plate must be painted, not transparent.
    assert image.pixelColor(32, 40).alpha() == 255

    # The spec feeds this straight to PyInstaller's splash, which fails the
    # build outright if the file is not there.
    assert (tmp_path / "splash.png").exists()


def test_the_splash_is_dismissed_when_there_is_no_packaged_build():
    from pokernow_tracker.ui.app import _close_splash

    # Outside a packaged build there is no pyi_splash to import, and startup
    # must carry on rather than fail.
    _close_splash()


def test_the_release_workflow_builds_every_system_people_use():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "macos-latest" in workflow  # Apple silicon
    assert "macos-15-intel" in workflow  # Intel, which arm64 builds cannot serve
    assert "if-no-files-found: error" in workflow  # a silent empty release is worse
