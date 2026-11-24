"""Qt host for the local TradingView Charting Library page."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView

from app.market_data.udf_server import UDFDataService

LOGGER = logging.getLogger("trade_tracker.tradingview")


class TradingViewPanel(QWidget):
    def __init__(self, database_path, parent=None):
        super().__init__(parent)
        self.server = UDFDataService(database_path, Path(__file__).resolve().parents[2])
        self.server.start()
        self.status = QLabel("Select a trade and click Chart.")
        self.status.setWordWrap(True)
        self.web_view = QWebEngineView()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.status)
        layout.addWidget(self.web_view, 1)
        self.web_view.setVisible(False)

    def load_trade(self, trade: dict) -> None:
        self.server.set_trade(trade)
        missing = []
        if not trade.get("option_entry_typed_at") or trade.get("stock_entry") in (None, 0, 0.0):
            missing.append("stock entry timestamp/price")
        if not trade.get("option_exit_typed_at") or trade.get("stock_exit") in (None, 0, 0.0):
            missing.append("stock exit timestamp/price")
        self.status.setText(
            "Missing data: " + ", ".join(missing) if missing else ""
        )
        self.status.setVisible(bool(missing))
        self.web_view.setVisible(True)
        url = QUrl(f"{self.server.base_url}/tradingview/index.html?trade_id={trade['id']}")
        self.web_view.setUrl(url)

    def close(self) -> None:
        self.server.stop()
