"""Draw the application icon at every size the platforms ask for.

Qt is already a dependency, so the icon is drawn rather than checked in as a
binary blob, and the palette comes straight from the interface theme.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath,
)

# Windows reads every size out of one .ico; macOS wants its own set.
ICO_SIZES = (256, 128, 64, 48, 32, 16)
ICNS_SIZES = (16, 32, 64, 128, 256, 512, 1024)

PLATE_TOP = QColor("#242c3a")
PLATE_BOTTOM = QColor("#141821")
SPADE = QColor("#5d8fd4")
SPADE_SHADE = QColor("#3f6cab")


def _spade(size: float) -> QPainterPath:
    """A spade drawn in a unit square, then scaled to ``size``."""
    path = QPainterPath()
    s = size

    # Two lobes and a point, mirrored about the vertical centre.
    path.moveTo(0.500 * s, 0.145 * s)
    path.cubicTo(0.500 * s, 0.145 * s, 0.205 * s, 0.395 * s, 0.205 * s, 0.560 * s)
    path.cubicTo(0.205 * s, 0.675 * s, 0.290 * s, 0.740 * s, 0.375 * s, 0.740 * s)
    path.cubicTo(0.430 * s, 0.740 * s, 0.470 * s, 0.715 * s, 0.492 * s, 0.685 * s)
    path.cubicTo(0.492 * s, 0.760 * s, 0.455 * s, 0.830 * s, 0.395 * s, 0.870 * s)
    path.lineTo(0.605 * s, 0.870 * s)
    path.cubicTo(0.545 * s, 0.830 * s, 0.508 * s, 0.760 * s, 0.508 * s, 0.685 * s)
    path.cubicTo(0.530 * s, 0.715 * s, 0.570 * s, 0.740 * s, 0.625 * s, 0.740 * s)
    path.cubicTo(0.710 * s, 0.740 * s, 0.795 * s, 0.675 * s, 0.795 * s, 0.560 * s)
    path.cubicTo(0.795 * s, 0.395 * s, 0.500 * s, 0.145 * s, 0.500 * s, 0.145 * s)
    path.closeSubpath()
    return path


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    plate = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    plate.setColorAt(0.0, PLATE_TOP)
    plate.setColorAt(1.0, PLATE_BOTTOM)

    # A rounded plate, inset slightly so the corners are not clipped.
    inset = size * 0.045
    radius = size * 0.22
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(plate))
    painter.drawRoundedRect(
        QRectF(inset, inset, size - inset * 2, size - inset * 2), radius, radius
    )

    # A hairline rim keeps the plate from dissolving into a dark dock.
    if size >= 32:
        rim = QColor("#39435a")
        rim.setAlpha(190)
        pen = painter.pen()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(rim)
        painter.drawRoundedRect(
            QRectF(inset, inset, size - inset * 2, size - inset * 2), radius, radius
        )
        painter.setPen(pen)
        painter.setPen(Qt.NoPen)

    spade = QLinearGradient(QPointF(0, size * 0.15), QPointF(0, size * 0.87))
    spade.setColorAt(0.0, SPADE)
    spade.setColorAt(1.0, SPADE_SHADE)
    painter.setBrush(QBrush(spade))
    painter.drawPath(_spade(size))

    painter.end()
    return image


def render_splash(width: int = 420, height: int = 160) -> QImage:
    """The panel shown while a one-file build unpacks itself.

    Unpacking takes a few seconds on a slow disk, and without something on
    screen a double-click looks like it did nothing at all.
    """
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("#141821"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#242c3a"))
    painter.drawRect(0, 0, width, 4)

    mark = height * 0.52
    painter.translate(34, (height - mark) / 2)
    spade = QLinearGradient(QPointF(0, 0), QPointF(0, mark))
    spade.setColorAt(0.0, SPADE)
    spade.setColorAt(1.0, SPADE_SHADE)
    painter.setBrush(QBrush(spade))
    painter.drawPath(_spade(mark))
    painter.resetTransform()

    font = painter.font()
    font.setPointSizeF(height * 0.135)
    font.setWeight(font.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#dfe3ea"))
    painter.drawText(
        QRectF(34 + mark + 18, 0, width, height * 0.58),
        Qt.AlignLeft | Qt.AlignBottom, "PokerNow Tracker",
    )

    font.setPointSizeF(height * 0.085)
    font.setWeight(font.Weight.Normal)
    painter.setFont(font)
    painter.setPen(QColor("#8b93a2"))
    painter.drawText(
        QRectF(34 + mark + 18, height * 0.58, width, height * 0.3),
        Qt.AlignLeft | Qt.AlignTop, "Starting up",
    )

    painter.end()
    return image


def write(directory: Path) -> Path:
    """Write the .ico and the .iconset macOS needs, returning the .ico."""
    directory.mkdir(parents=True, exist_ok=True)

    ico = directory / "pokernow.ico"
    frames = [render(size) for size in ICO_SIZES]
    writer_ok = frames[0].save(str(ico), "ICO")
    if not writer_ok:  # pragma: no cover - only if Qt lacks the ICO plugin
        raise RuntimeError("Qt could not write an .ico file")

    iconset = directory / "pokernow.iconset"
    iconset.mkdir(exist_ok=True)
    for size in ICNS_SIZES:
        render(size).save(str(iconset / f"icon_{size}x{size}.png"), "PNG")
        if size <= 512:
            render(size * 2).save(str(iconset / f"icon_{size}x{size}@2x.png"), "PNG")

    render(512).save(str(directory / "pokernow.png"), "PNG")
    render_splash().save(str(directory / "splash.png"), "PNG")
    return ico


def main() -> int:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    target = write(Path(__file__).resolve().parent / "build")
    print(f"wrote {target} and the macOS iconset beside it")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
