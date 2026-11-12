"""Offline procedural camera preview; intentionally labeled synthetic."""
import math
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from .receivers import VideoFrame


def demo_frame(timestamp):
    image = QImage(1280, 720, QImage.Format.Format_RGB888)
    image.fill(QColor('#176075'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Aerial shoreline with gentle camera drift and moving wave fronts.
    drift = 14 * math.sin(timestamp / 5)
    beach = QPainterPath()
    beach.moveTo(0, 0)
    beach.lineTo(410 + drift, 0)
    beach.cubicTo(310 + drift, 260, 490 + drift, 460, 330 + drift, 720)
    beach.lineTo(0, 720)
    beach.closeSubpath()
    painter.fillPath(beach, QColor('#d5bd87'))
    for wave in range(12):
        x = 390 + wave * 90 - (timestamp * 18 % 90) + drift
        path = QPainterPath()
        path.moveTo(x, 0)
        for y in range(0, 741, 20):
            path.lineTo(x + 24 * math.sin(y / 100 + timestamp * .4), y)
        painter.setPen(QPen(QColor(160, 222, 221, 95 if wave < 3 else 35), 3))
        painter.drawPath(path)
    # Moving rescue boat: a visible motion cue, not an inferred detection.
    painter.save()
    painter.translate(840 + 100 * math.sin(timestamp / 7), 360 + 95 * math.cos(timestamp / 9))
    painter.rotate(15 * math.sin(timestamp / 7))
    painter.setPen(QPen(QColor('#c5e9e7'), 2))
    painter.drawLine(QPointF(-10, 25), QPointF(-24, 80))
    painter.drawLine(QPointF(10, 25), QPointF(24, 80))
    boat = QPainterPath()
    boat.moveTo(0, -32)
    boat.lineTo(15, 12)
    boat.lineTo(10, 30)
    boat.lineTo(-10, 30)
    boat.lineTo(-15, 12)
    boat.closeSubpath()
    painter.fillPath(boat, QColor('#f5f3e9'))
    painter.fillRect(-6, -5, 12, 22, QColor('#e98e46'))
    painter.restore()
    painter.setPen(QPen(QColor(220, 240, 240, 140), 1))
    painter.drawLine(620, 360, 660, 360)
    painter.drawLine(640, 340, 640, 380)
    painter.fillRect(20, 20, 570, 48, QColor(4, 15, 23, 210))
    painter.setPen(QColor('#f1cf75'))
    painter.setFont(QFont('sans-serif', 17))
    painter.drawText(36, 52, 'DEMO / SYNTHETIC VIDEO — NO LIVE CAMERA')
    painter.setPen(QColor('#ffffff'))
    painter.setFont(QFont('monospace', 14))
    painter.drawText(28, 690, f'SIM CAMERA 01   /   FRAME TIME {timestamp:012.2f}')
    painter.end()
    return VideoFrame(image, timestamp)
