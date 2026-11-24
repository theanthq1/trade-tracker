"""Read-only candlestick chart for actual historical Massive data."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

EASTERN = ZoneInfo("America/New_York")


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=EASTERN)
    return parsed.timestamp()


class CandlestickChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.candles = []
        self.trade = {}
        self.setMinimumHeight(360)

    def set_data(self, candles: list[dict], trade: dict) -> None:
        self.candles = candles
        self.trade = trade
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#10151d"))
        if not self.candles:
            painter.setPen(QColor("#9da3ad"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No chart data loaded")
            return

        margin = 42
        volume_height = 46
        plot = QRectF(margin, 18, self.width() - margin - 70, self.height() - 36 - volume_height)
        volume_plot = QRectF(plot.left(), plot.bottom() + 10, plot.width(), volume_height)
        lows = [c["low"] for c in self.candles]
        highs = [c["high"] for c in self.candles]
        low, high = min(lows), max(highs)
        padding = max((high - low) * 0.08, 0.01)
        low -= padding
        high += padding
        start = self.candles[0]["time"].timestamp()
        end = self.candles[-1]["time"].timestamp() + 60
        span = max(end - start, 60)
        max_volume = max((c["volume"] for c in self.candles), default=1) or 1

        def x(ts):
            return plot.left() + (ts - start) / span * plot.width()

        def y(price):
            return plot.top() + (high - price) / max(high - low, 0.01) * plot.height()

        painter.setPen(QPen(QColor("#2f3a49"), 1))
        for index in range(5):
            gy = plot.top() + index * plot.height() / 4
            painter.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
            price = high - index * (high - low) / 4
            painter.setPen(QColor("#8b98a9"))
            painter.drawText(2, int(gy + 4), f"${price:.2f}")
            painter.setPen(QPen(QColor("#2f3a49"), 1))

        candle_width = max(1.5, min(9.0, plot.width() / max(len(self.candles), 1) * 0.7))
        for candle in self.candles:
            cx = x(candle["time"].timestamp())
            color = QColor("#39d09b" if candle["close"] >= candle["open"] else "#ff6b78")
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPointF(cx, y(candle["high"])), QPointF(cx, y(candle["low"])))
            body_top = y(max(candle["open"], candle["close"]))
            body_height = max(1.0, y(min(candle["open"], candle["close"])) - body_top)
            painter.fillRect(QRectF(cx - candle_width / 2, body_top, candle_width, body_height), color)
            volume_top = volume_plot.bottom() - candle["volume"] / max_volume * volume_plot.height()
            painter.fillRect(QRectF(cx - candle_width / 2, volume_top, candle_width, volume_plot.bottom() - volume_top), color)

        self._draw_marker(painter, "option_entry_typed_at", "stock_entry", "Actual entry", "#61a8ff", x, y, start, end)
        self._draw_marker(painter, "option_exit_typed_at", "stock_exit", "Actual exit", "#61a8ff", x, y, start, end)
        painter.setPen(QColor("#9da3ad"))
        painter.drawText(int(plot.left()), self.height() - 8, "Premarket 4:00 AM")
        painter.drawText(int(plot.right() - 118), self.height() - 8, "10:30 AM ET")

    def _draw_marker(self, painter, time_key, price_key, label, color, x, y, start, end):
        timestamp = parse_timestamp(self.trade.get(time_key))
        price = self.trade.get(price_key)
        if timestamp is None or price in (None, "") or not start <= timestamp <= end:
            return
        cx, cy = x(timestamp), y(float(price))
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor(color), 1))
        painter.drawEllipse(QPointF(cx, cy), 4, 4)
        painter.drawText(int(cx + 8), int(cy - 6), label)


class MassiveChartPanel(QWidget):
    refresh_requested = Signal()
    details_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.chart = CandlestickChart()
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(360)
        self.image.setStyleSheet("background: #10151d;")
        self._image_pixmap = QPixmap()
        self.views = QStackedWidget()
        self.views.addWidget(self.chart)
        self.views.addWidget(self.image)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        details_button = QPushButton("View Data Details")
        details_button.setEnabled(False)
        details_button.clicked.connect(self.details_requested.emit)
        self._details_button = details_button
        status_row.addWidget(self.refresh_button)
        status_row.addWidget(details_button)
        layout.addLayout(status_row)
        layout.addWidget(self.views, 1)

    def show_loading(self, trade: dict) -> None:
        self.status.setText(f"Loading saved data for {trade.get('ticker_symbol', '—')}…")
        self.refresh_button.setEnabled(False)
        self._details_button.setEnabled(False)

    def show_data(self, trade: dict, candles: list[dict], metadata: dict) -> None:
        cache_status = metadata.get("status", "Saved locally")
        self.status.setText(
            f"Data source: {metadata.get('provider', '—')} · "
            f"Cache status: {cache_status} · "
            f"Fetched: {metadata.get('fetched_at', '—')} · "
            f"Resolution: {metadata.get('request').resolution if metadata.get('request') else '—'} · "
            f"Bars: {len(candles)}"
        )
        self.refresh_button.setEnabled(True)
        self._details_button.setEnabled(True)
        self.views.setCurrentWidget(self.chart)
        self.chart.set_data(candles, trade)

    def show_screenshot(self, trade: dict) -> None:
        pixmap = QPixmap()
        screenshot = trade.get("screenshot")
        if screenshot:
            pixmap.loadFromData(bytes(screenshot))
        if pixmap.isNull():
            self.show_error("Screenshot unavailable or invalid.")
            return
        self._image_pixmap = pixmap
        self.status.setText(
            f"{trade.get('ticker_symbol', '—')} · Uploaded screenshot · "
            "Click View Chart to return to the chart."
        )
        self.refresh_button.setEnabled(True)
        self._details_button.setEnabled(False)
        self.views.setCurrentWidget(self.image)
        self._scale_image()

    def show_error(self, message: str) -> None:
        self.status.setText(message)
        self.refresh_button.setEnabled(True)
        self._details_button.setEnabled(False)
        self.views.setCurrentWidget(self.chart)
        self.chart.set_data([], {})

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._scale_image()

    def _scale_image(self):
        if self._image_pixmap.isNull():
            return
        available = self.image.size()
        self.image.setPixmap(self._image_pixmap.scaled(
            available, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
