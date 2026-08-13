from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 18)
        self.layout.setSpacing(12)
        if title:
            label = QLabel(title)
            label.setObjectName("SectionTitle")
            self.layout.addWidget(label)
        if subtitle:
            label = QLabel(subtitle)
            label.setObjectName("Muted")
            label.setWordWrap(True)
            self.layout.addWidget(label)


class HexLogo(QWidget):
    """Small vector logo; no external image asset is required."""

    def __init__(self, size: int = 42, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.44
        points = []
        for i in range(6):
            angle = math.radians(30 + i * 60)
            points.append(QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle)))
        polygon = QPolygonF(points)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#7C3AED"))
        painter.drawPolygon(polygon)
        painter.setPen(QPen(QColor("white")))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(self._size * 0.43))
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, "H")
