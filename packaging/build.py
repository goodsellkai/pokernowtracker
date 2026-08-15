"""Build a self-contained PokerNow Tracker for whichever system runs this.

    python packaging/build.py

Windows produces ``dist/PokerNow Tracker.exe``. macOS produces
``dist/PokerNow Tracker.app``, and a .zip of it, since an unzipped .app
downloaded through a browser loses its executable bits. Linux produces a
single executable file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
DIST = ROOT / "dist"


def _icons() -> None:
    subprocess.run([sys.executable, str(HERE / "icon.py")], check=True, cwd=ROOT)

    if sys.platform != "darwin":
        return

    # iconutil ships with macOS and is the only supported way to make an .icns.
    iconset = BUILD / "pokernow.iconset"
    icns = BUILD / "pokernow.icns"
    try:
        subprocess.run(
            ["iconutil", "--convert", "icns", str(iconset), "--output", str(icns)],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("iconutil unavailable, building without an icon")


def _zip_app(app: Path) -> Path:
    """Zip a .app, preserving the permission bits macOS needs to launch it."""
    archive = DIST / f"{app.stem}-macOS.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(app.rglob("*")):
            info = zipfile.ZipInfo.from_file(path, path.relative_to(app.parent))
            if path.is_symlink():
                info.create_system = 3
                info.external_attr = (0xA1FF << 16)
                bundle.writestr(info, str(path.readlink()))
                continue
            if path.is_dir():
                continue
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes())
    return archive


def main() -> int:
    _icons()

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(BUILD / "pyinstaller", ignore_errors=True)

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean",
            "--distpath", str(DIST),
            "--workpath", str(BUILD / "pyinstaller"),
            str(HERE / "pokernow.spec"),
        ],
        check=True,
        cwd=ROOT,
    )

    produced = []
    app = DIST / "PokerNow Tracker.app"
    if app.exists():
        produced.append(_zip_app(app))
        shutil.rmtree(DIST / "PokerNow Tracker", ignore_errors=True)
    else:
        produced.extend(
            path for path in DIST.iterdir()
            if path.is_file() and path.name.startswith("PokerNow Tracker")
        )

    for path in produced:
        print(f"{path.name}  {path.stat().st_size / 1_000_000:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
