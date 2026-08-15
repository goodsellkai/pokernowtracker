# PyInstaller build for a self-contained PokerNow Tracker.
#
# Windows produces a single .exe. macOS produces a .app bundle. Neither needs
# Python, Qt, or anything else present on the machine that runs it.

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
BUILD = Path(SPECPATH) / "build"

# Set POKERNOW_BUILD_CONSOLE=1 to keep a console attached, which is the only
# way to see a startup traceback from a build that fails on another machine.
CONSOLE = os.environ.get("POKERNOW_BUILD_CONSOLE") == "1"

# The interface uses QtCore, QtGui, and QtWidgets. Everything else Qt ships is
# dead weight in the download, and some of it (WebEngine especially) is very
# large, so each unused module is named rather than shipped by default.
QT_KEEP = {"QtCore", "QtGui", "QtWidgets"}
QT_DROP = [
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic",
    "Qt3DRender", "QtBluetooth", "QtCharts", "QtConcurrent", "QtDataVisualization",
    "QtDBus", "QtDesigner", "QtGraphs", "QtGraphsWidgets", "QtHelp", "QtHttpServer",
    "QtLocation", "QtMultimedia", "QtMultimediaWidgets", "QtNetwork",
    "QtNetworkAuth", "QtNfc", "QtOpenGL", "QtOpenGLWidgets", "QtPdf",
    "QtPdfWidgets", "QtPositioning", "QtPrintSupport", "QtQml", "QtQuick",
    "QtQuick3D", "QtQuickControls2", "QtQuickTest", "QtQuickWidgets",
    "QtRemoteObjects", "QtScxml", "QtSensors", "QtSerialBus", "QtSerialPort",
    "QtSpatialAudio", "QtSql", "QtStateMachine", "QtSvg", "QtSvgWidgets",
    "QtTest", "QtTextToSpeech", "QtUiTools", "QtWebChannel", "QtWebEngineCore",
    "QtWebEngineQuick", "QtWebEngineWidgets", "QtWebSockets", "QtXml",
]

excludes = [f"PySide6.{name}" for name in QT_DROP if name not in QT_KEEP]
excludes += [
    # Standard-library corners nothing here touches. Each one is startup time
    # and download size a first-time user would otherwise be waiting on.
    "tkinter", "unittest", "pydoc", "doctest", "sqlite3", "xmlrpc",
    "ftplib", "lib2to3", "distutils", "setuptools", "pip", "numpy", "PIL",
    "pytest", "PyQt5", "PyQt6",
]

icon_windows = str(BUILD / "pokernow.ico")
icon_macos = str(BUILD / "pokernow.icns")

analysis = Analysis(
    [str(Path(SPECPATH) / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(analysis.pure)

if sys.platform == "darwin":
    # A .app bundle is a folder internally but reads as a single item in
    # Finder, so one-file's slower startup buys nothing here.
    exe = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name="PokerNow Tracker",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=True,  # a file dropped on the icon arrives as an argument
    )
    collected = COLLECT(
        exe,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        name="PokerNow Tracker",
    )
    app = BUNDLE(
        collected,
        name="PokerNow Tracker.app",
        icon=icon_macos,
        bundle_identifier="club.pokernow.tracker",
        info_plist={
            "CFBundleName": "PokerNow Tracker",
            "CFBundleDisplayName": "PokerNow Tracker",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Hand history export",
                "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["public.comma-separated-values-text"],
                "LSHandlerRank": "Alternate",
            }],
        },
    )
else:
    # A one-file build unpacks itself before Python starts, which takes a
    # noticeable moment on a slow disk. The splash goes up immediately, so a
    # double-click never looks like it did nothing.
    splash = Splash(
        str(BUILD / "splash.png"),
        binaries=analysis.binaries,
        datas=analysis.datas,
        always_on_top=False,
    )

    # One file, so what the user downloads is exactly what they double-click.
    exe = EXE(
        pyz,
        analysis.scripts,
        splash,
        splash.binaries,
        analysis.binaries,
        analysis.datas,
        [],
        name="PokerNow Tracker",
        debug=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=CONSOLE,
        disable_windowed_traceback=False,
        icon=icon_windows,
    )
