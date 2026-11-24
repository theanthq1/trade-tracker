#!/usr/bin/env python3
import sqlite3
import sys
import threading
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QSettings, QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor, QDoubleValidator, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QGridLayout, QHeaderView,
    QLineEdit, QFrame, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QStackedWidget, QFileDialog,
    QToolButton, QVBoxLayout, QWidget
)

from app.ui.analyze_tab import AnalyzeTableColumns as AnalyzeColumns
from app.ui.data_config_dialog import DataConfigDialog
from app.ui.massive_chart import MassiveChartPanel
from app.market_data.providers import get_active_market_data_provider, provider_settings
from app.database.market_data_repository import MarketDataRepository, MarketDataRequest
from app.database.connection import configure, connect
from app.database.backup import create_backup, export_database_copy, restore_backup
from app.migrations import run_migrations
from app.settings import diagnostic_summary, prepare_database_path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = prepare_database_path()
LOGGER = logging.getLogger("trade_tracker")


THEME_PALETTES = {
    "dark": {
        "window": "#181a1f", "panel": "#22252b", "input": "#2b2f36",
        "text": "#e6e8eb", "muted": "#9da3ad", "border": "#3a3f47",
        "accent": "#3b82f6", "accent_hover": "#5795f7", "accent_pressed": "#2563c7",
        "table_alt": "#272a31", "selection": "#315fa8", "positive": "#22c55e",
        "negative": "#ef4444",
    },
    "light": {
        "window": "#eef0f3", "panel": "#ffffff", "input": "#f7f8fa",
        "text": "#20242a", "muted": "#626a75", "border": "#c7ccd3",
        "accent": "#3b82f6", "accent_hover": "#5795f7", "accent_pressed": "#2563c7",
        "table_alt": "#f0f2f5", "selection": "#bcd2f5", "positive": "#16803c",
        "negative": "#c93636",
    },
}


def theme_stylesheet(mode):
    palette = THEME_PALETTES[mode]
    return f"""
        QWidget {{ background: {palette['window']}; color: {palette['text']}; font-family: "Tahoma", "Arial", sans-serif; font-size: 13px; }}
        #root, #menuPage {{ background: {palette['window']}; }}
        #menuTitle {{ color: {palette['text']}; font-size: 28px; font-weight: bold; }}
        #menuSubtitle {{ color: {palette['muted']}; font-size: 12px; }}
        #dashboardHeader, #dashboardCard {{ background: {palette['panel']}; border: 1px solid {palette['border']}; border-radius: 10px; }}
        #sectionTitle {{ background: transparent; color: {palette['text']}; font-size: 15px; font-weight: bold; }}
        #sectionHint {{ background: transparent; color: {palette['muted']}; font-size: 11px; }}
        #statusText {{ background: transparent; color: {palette['muted']}; font-size: 12px; }}
        #dashboardFooter {{ background: transparent; color: {palette['muted']}; font-size: 11px; }}
        #developerToggle {{ background: transparent; color: {palette['muted']}; border: none; padding: 4px 0; font-weight: bold; text-align: left; }}
        #developerToggle:hover {{ color: {palette['text']}; }}
        #primaryAction {{ background: {palette['accent']}; color: #ffffff; border-color: {palette['accent']}; font-size: 14px; font-weight: bold; min-height: 52px; border-radius: 7px; }}
        #primaryAction:hover {{ background: {palette['accent_hover']}; border-color: {palette['accent_hover']}; }}
        #primaryAction:pressed {{ background: {palette['accent_pressed']}; }}
        #secondaryAction {{ min-height: 42px; border-radius: 7px; }}
        #dataIndicator {{ background: {palette['input']}; border-color: {palette['border']}; border-radius: 7px; min-height: 34px; padding: 0 14px; }}
        #dataIndicator:hover {{ border-color: {palette['accent']}; }}
        #title {{ color: {palette['text']}; font-size: 20px; font-weight: bold; }}
        #topBar {{ background: {palette['panel']}; border: 1px solid {palette['border']}; border-radius: 5px; padding: 4px; }}
        #card {{ background: {palette['panel']}; color: {palette['text']}; border: 1px solid {palette['border']}; border-radius: 5px; }}
        #statLabel, #fieldLabel {{ background: transparent; color: {palette['muted']}; font-weight: bold; }}
        #statValue, #tableTitle {{ color: {palette['text']}; font-size: 18px; font-weight: bold; }}
        #eyebrow {{ color: {palette['muted']}; font-size: 11px; font-weight: bold; letter-spacing: 1px; }}
        QPushButton {{ background: {palette['panel']}; color: {palette['text']}; border: 1px solid {palette['border']}; border-radius: 5px; padding: 0 12px; min-height: 34px; font-size: 12px; font-weight: 600; }}
        QPushButton:hover {{ background: {palette['input']}; border-color: {palette['accent']}; }}
        QPushButton:pressed {{ background: {palette['border']}; }}
        QPushButton:focus, QLineEdit:focus, QComboBox:focus {{ border: 2px solid {palette['accent']}; }}
        QPushButton:disabled {{ background: {palette['border']}; color: {palette['muted']}; }}
        #menuButton, #submitButton {{ background: {palette['accent']}; color: #ffffff; border-color: {palette['accent']}; font-weight: bold; }}
        #menuButton:hover, #submitButton:hover {{ background: {palette['accent_hover']}; }}
        #menuButton:pressed, #submitButton:pressed {{ background: {palette['accent_pressed']}; }}
        #timerButton:disabled {{ background: {palette['positive']}; color: #ffffff; border-color: {palette['positive']}; }}
        #dangerButton {{ background: {palette['negative']}; color: #ffffff; border-color: {palette['negative']}; font-weight: bold; }}
        #dangerButton:hover {{ background: {palette['negative']}; }}
        QLineEdit, QComboBox {{ background: {palette['input']}; color: {palette['text']}; border: 1px solid {palette['border']}; border-radius: 4px; padding: 2px 6px; selection-background-color: {palette['selection']}; }}
        QComboBox QAbstractItemView {{ background: {palette['panel']}; color: {palette['text']}; selection-background-color: {palette['selection']}; }}
        #imageDrop {{ background: {palette['input']}; color: {palette['muted']}; border: 1px solid {palette['border']}; border-radius: 4px; }}
        QTableWidget {{ background: {palette['panel']}; alternate-background-color: {palette['table_alt']}; color: {palette['text']}; border: 1px solid {palette['border']}; gridline-color: {palette['border']}; selection-background-color: {palette['selection']}; selection-color: {palette['text']}; }}
        QTableWidget::item {{ border-bottom: 1px solid {palette['border']}; padding: 5px; }}
        QHeaderView::section {{ background: {palette['input']}; color: {palette['muted']}; border: none; border-bottom: 1px solid {palette['border']}; padding: 6px; font-weight: bold; }}
        QScrollArea {{ background: {palette['window']}; border: none; }}
        QMessageBox {{ background: {palette['panel']}; color: {palette['text']}; }}
            QLabel {{ background: transparent; }}
    """


class TradeLoadWorker(QObject):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = str(db_path)

    @Slot()
    def load(self):
        try:
            with sqlite3.connect(self.db_path) as connection:
                rows = connection.execute(
                    "SELECT id, ticker_symbol, option_type, stock_entry, option_entry, stock_exit, option_exit, screenshot, created_at, option_entry_typed_at, option_exit_typed_at FROM trades ORDER BY id DESC"
                ).fetchall()
            trades = []
            wins = 0
            total_pnl = 0.0
            closed_count = 0
            for row in rows:
                trade_id, ticker_symbol, option_type, stock_entry, option_entry, stock_exit, option_exit, screenshot, created_at, entry_typed_at, exit_typed_at = row
                is_closed = bool(exit_typed_at and option_exit and option_exit > 0)
                pnl = option_exit - option_entry if is_closed else 0.0
                percentage = pnl / option_entry * 100 if is_closed and option_entry else 0.0
                if is_closed:
                    closed_count += 1
                    total_pnl += pnl
                    wins += pnl > 0
                trades.append((
                    trade_id,
                    datetime.fromisoformat(created_at).strftime("%b %d, %Y %I:%M %p"),
                    ticker_symbol or "—",
                    option_type or "—",
                    f"${stock_entry:.2f}" if stock_entry else "—",
                    f"${option_entry:.2f}" if option_entry else "—",
                    f"${stock_exit:.2f}" if is_closed else "—",
                    f"${option_exit:.2f}" if is_closed else "—",
                    f"{'+' if pnl >= 0 else '-'}${abs(pnl):.2f}" if is_closed else "—",
                    f"{'+' if percentage >= 0 else '-'}{abs(percentage):.2f}%" if is_closed else "—",
                    "Attached" if screenshot else "—",
                    is_closed and pnl >= 0,
                ))
            self.loaded.emit([
                trades,
                closed_count,
                total_pnl,
                round(wins / closed_count * 100) if closed_count else 0,
            ])
        except Exception as error:
            self.failed.emit(str(error))


class ImageEncodeWorker(QObject):
    encoded = Signal(bytes, object)
    failed = Signal(str)

    @Slot(object)
    def encode(self, image):
        try:
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, "PNG")
            preview = image.scaled(300, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.encoded.emit(bytes(data), preview)
        except Exception as error:
            self.failed.emit(str(error))


class WatchlistStatsWorker(QObject):
    loaded = Signal(list)
    failed = Signal(str)

    TICKERS = ("TSLA", "MU", "AMD", "META", "MSFT", "AAPL", "NVDA", "SPY", "QQQ")

    def __init__(self):
        super().__init__()
    @Slot()
    def load(self):
        provider = get_active_market_data_provider()
        try:
            rows, errors = provider.get_watchlist_statistics(self.TICKERS)
        except Exception as error:
            rows = []
            errors = [str(error)]
        if not rows:
            self.failed.emit("Unable to load watchlist statistics.\n" + "\n".join(errors))
            return
        self.loaded.emit([rows, errors])


class ChartDataWorker(QObject):
    loaded = Signal(object, object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.repository = MarketDataRepository(DB_PATH)

    @Slot(object, bool)
    def load(self, trade: dict, force_refresh: bool = False):
        try:
            entry_timestamp = trade.get("option_entry_typed_at") or trade.get("created_at")
            if not entry_timestamp:
                raise ValueError("The selected trade has no entry timestamp.")
            entry = datetime.fromisoformat(str(entry_timestamp))
            if entry.tzinfo is None:
                entry = entry.replace(tzinfo=ZoneInfo("America/New_York"))
            eastern = ZoneInfo("America/New_York")
            trade_day = entry.astimezone(eastern).date()
            trade_date = trade_day.isoformat()
            start = datetime.combine(trade_day, datetime.min.time(), tzinfo=eastern).replace(hour=4)
            end = start.replace(hour=10, minute=31)
            provider = get_active_market_data_provider()
            request = MarketDataRequest(
                trade_id=int(trade["id"]), symbol=str(trade["ticker_symbol"]).strip().upper(),
                trade_date=trade_date, provider=provider.name, data_type="candles",
                resolution="1m", start_time=start, end_time=end,
            )
            result = self.repository.load_or_fetch(
                request,
                lambda: provider.get_historical_bars(request.symbol, start, end, request.resolution),
                force_refresh=force_refresh,
            )
            self.loaded.emit(trade, result)
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            self.failed.emit(str(error))


class TradeTracker(QMainWindow):
    trade_load_requested = Signal()
    image_encode_requested = Signal(object)
    watchlist_stats_requested = Signal()
    chart_requested = Signal(object, bool)

    def __init__(self):
        super().__init__()
        self.image_bytes = None
        self.exit_timer_started_at = None
        self.exit_timer_active = False
        self.option_entry_typed_at = None
        self.option_exit_typed_at = None
        self.settings = QSettings("TradeTracker", "TradeTracker")
        self.theme_mode = self.settings.value("theme", "dark")
        if self.theme_mode not in THEME_PALETTES:
            self.theme_mode = "dark"
        self.theme_buttons = []
        self.provider_settings = provider_settings()
        self.db = configure(connect(DB_PATH))
        self.db_lock = threading.Lock()

        run_migrations(self.db)
        self.db.commit()
        self.setWindowTitle("Trade Tracker")
        self.resize(390, 285)
        self.setMinimumSize(430, 360)
        self.build_ui()
        self.setup_workers()
        self.load_trades()
        QShortcut(QKeySequence.Paste, self, activated=self.paste_image)

    def setup_workers(self):
        self.trade_load_thread = QThread(self)
        self.trade_load_worker = TradeLoadWorker(DB_PATH)
        self.trade_load_worker.moveToThread(self.trade_load_thread)
        self.trade_load_requested.connect(self.trade_load_worker.load)
        self.trade_load_worker.loaded.connect(self.apply_trade_rows)
        self.trade_load_worker.failed.connect(self.show_worker_error)
        self.trade_load_thread.start()

        self.image_encode_thread = QThread(self)
        self.image_encode_worker = ImageEncodeWorker()
        self.image_encode_worker.moveToThread(self.image_encode_thread)
        self.image_encode_requested.connect(self.image_encode_worker.encode)
        self.image_encode_worker.encoded.connect(self.apply_encoded_image)
        self.image_encode_worker.failed.connect(self.show_worker_error)
        self.image_encode_thread.start()

        self.watchlist_thread = QThread(self)
        self.watchlist_worker = WatchlistStatsWorker()
        self.watchlist_worker.moveToThread(self.watchlist_thread)
        self.watchlist_stats_requested.connect(self.watchlist_worker.load)
        self.watchlist_worker.loaded.connect(self.apply_watchlist_stats)
        self.watchlist_worker.failed.connect(self.show_worker_error)
        self.watchlist_thread.start()

        self.chart_thread = QThread(self)
        self.chart_worker = ChartDataWorker()
        self.chart_worker.moveToThread(self.chart_thread)
        self.chart_requested.connect(self.chart_worker.load)
        self.chart_worker.loaded.connect(self.apply_chart_data)
        self.chart_worker.failed.connect(self.show_chart_error)
        self.chart_thread.start()
        self.chart_result = None
        self.current_chart_trade = None

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        self.resize(980, 680)
        self.setMinimumSize(760, 560)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages)

        self.menu_page = QWidget()
        self.menu_page.setObjectName("menuPage")
        menu_layout = QVBoxLayout(self.menu_page)
        menu_layout.setContentsMargins(36, 28, 36, 24)
        menu_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("dashboardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 18, 20, 18)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        menu_title = QLabel("Trade Tracker")
        menu_title.setObjectName("menuTitle")
        title_stack.addWidget(menu_title)
        menu_subtitle = QLabel("Personal Options Journal")
        menu_subtitle.setObjectName("menuSubtitle")
        title_stack.addWidget(menu_subtitle)
        header_layout.addLayout(title_stack)
        header_layout.addStretch(1)
        add_entry = QPushButton("New Trade")
        add_entry.setObjectName("primaryAction")
        add_entry.clicked.connect(self.show_add_entry)
        self.data_indicator = QPushButton()
        self.data_indicator.setObjectName("dataIndicator")
        self.data_indicator.clicked.connect(self.open_data_config)
        self.update_data_indicator(self.provider_settings.value("market_data/provider", "Massive", type=str), "gray")
        header_layout.addWidget(self.data_indicator)
        menu_layout.addWidget(header)

        content = QGridLayout()
        content.setHorizontalSpacing(16)
        content.setVerticalSpacing(16)
        trading_card, trading_layout = self.dashboard_card("Trading", "Start or record your trading workflow.")
        add_entry.setObjectName("primaryAction")
        trading_layout.addWidget(add_entry)
        trading_layout.addWidget(self.dashboard_hint("Create a new options trade journal entry."))
        content.addWidget(trading_card, 0, 0)

        analysis_card, analysis_layout = self.dashboard_card("Analysis", "Review performance and market context.")
        analyze = QPushButton("Analyze Trades")
        analyze.setObjectName("primaryAction")
        analyze.clicked.connect(self.show_analysis)
        watchlist = QPushButton("Watchlist Stats")
        watchlist.setObjectName("secondaryAction")
        watchlist.clicked.connect(self.show_watchlist_stats)
        analysis_layout.addWidget(analyze)
        analysis_layout.addWidget(watchlist)
        content.addWidget(analysis_card, 0, 1)
        content.setColumnStretch(0, 1)
        content.setColumnStretch(1, 1)
        menu_layout.addLayout(content)

        data_card, data_layout = self.dashboard_card("Data & Connections", "The selected provider powers charts, ATR, and market analysis.")
        data_form = QFormLayout()
        self.home_provider_combo = QComboBox()
        self.home_provider_combo.addItems(["Schwab", "Massive", "IBKR PRO"])
        self.home_provider_combo.setCurrentText(self.provider_settings.value("market_data/provider", "Massive", type=str))
        self.home_provider_combo.currentTextChanged.connect(self.select_home_provider)
        data_form.addRow("Data Provider", self.home_provider_combo)
        self.home_data_status = QLabel("Not tested")
        self.home_data_status.setObjectName("statusText")
        self.update_data_indicator(self.provider_settings.value("market_data/provider", "Massive", type=str), "gray")
        data_form.addRow("Status", self.home_data_status)
        data_layout.addLayout(data_form)
        data_actions = QHBoxLayout()
        configure_data = QPushButton("Configure Provider")
        configure_data.setObjectName("secondaryAction")
        configure_data.clicked.connect(self.open_data_config)
        test_data = QPushButton("Test Connection")
        test_data.setObjectName("secondaryAction")
        test_data.clicked.connect(self.test_data_connection)
        data_actions.addWidget(configure_data)
        data_actions.addWidget(test_data)
        data_layout.addLayout(data_actions)
        menu_layout.addWidget(data_card)

        developer_toggle = QToolButton()
        developer_toggle.setObjectName("developerToggle")
        developer_toggle.setText("Developer Tools")
        developer_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        developer_toggle.setArrowType(Qt.RightArrow)
        developer_toggle.setCheckable(True)
        developer_toggle.setChecked(False)
        menu_layout.addWidget(developer_toggle)
        developer_panel = QFrame()
        developer_panel.setObjectName("dashboardCard")
        developer_layout = QHBoxLayout(developer_panel)
        developer_layout.setContentsMargins(18, 14, 18, 14)
        backup = QPushButton("Backup Database")
        backup.setObjectName("secondaryAction")
        backup.clicked.connect(self.create_database_backup)
        restore = QPushButton("Restore Database")
        restore.setObjectName("dangerButton")
        restore.clicked.connect(self.restore_database_backup)
        diagnostics = QPushButton("Database Diagnostics")
        diagnostics.setObjectName("secondaryAction")
        diagnostics.clicked.connect(self.show_database_diagnostics)
        for button in (backup, restore, diagnostics):
            developer_layout.addWidget(button)
        developer_panel.setVisible(False)
        developer_toggle.toggled.connect(lambda expanded: (developer_panel.setVisible(expanded), developer_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)))
        menu_layout.addWidget(developer_panel)

        footer = QHBoxLayout()
        footer_label = QLabel("Local-first trade journal")
        footer_label.setObjectName("dashboardFooter")
        footer.addWidget(footer_label)
        footer.addStretch(1)
        footer.addWidget(self.create_theme_button())
        menu_layout.addLayout(footer)
        self.pages.addWidget(self.menu_page)

        self.build_entry_page()
        self.build_analysis_page()
        self.build_watchlist_page()
        self.apply_theme()
        self.show_menu()

    def build_entry_page(self):
        self.entry_page = QWidget()
        page_layout = QVBoxLayout(self.entry_page)
        page_layout.setContentsMargins(16, 12, 16, 14)
        page_layout.setSpacing(8)
        page_layout.addWidget(self.page_header("New trade"))

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)
        form_scroll = QScrollArea()
        form_scroll.setObjectName("formScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        form_scroll.setMaximumWidth(452)
        form_scroll.setFrameShape(QFrame.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_card = QFrame()
        form_card.setObjectName("card")
        form_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(12, 10, 12, 10)
        form_layout.setSpacing(4)
        form_title = QLabel("NEW TRADE")
        form_title.setObjectName("eyebrow")
        form_layout.addWidget(form_title)

        self.inputs = {}
        identity_layout = QGridLayout()
        identity_layout.setContentsMargins(0, 2, 0, 0)
        identity_layout.setHorizontalSpacing(10)
        identity_layout.setVerticalSpacing(3)
        identity_layout.setColumnStretch(1, 1)

        ticker_label = QLabel("Ticker symbol")
        ticker_label.setObjectName("fieldLabel")
        ticker_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("AAPL")
        self.ticker_input.setMaxLength(10)
        self.ticker_input.setFixedHeight(28)
        self.ticker_input.setAlignment(Qt.AlignLeft)
        identity_layout.addWidget(ticker_label, 0, 0)
        identity_layout.addWidget(self.ticker_input, 0, 1)

        option_type_label = QLabel("Option type")
        option_type_label.setObjectName("fieldLabel")
        option_type_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.option_type_input = QComboBox()
        self.option_type_input.addItems(["Call", "Put"])
        self.option_type_input.setFixedHeight(28)
        identity_layout.addWidget(option_type_label, 1, 0)
        identity_layout.addWidget(self.option_type_input, 1, 1)
        form_layout.addLayout(identity_layout)

        fields = [
            ("stock_entry", "Stock price at entry"),
            ("option_entry", "Option price at entry"),
            ("stock_exit", "Stock exit price"),
            ("option_exit", "Option price at exit"),
        ]
        fields_layout = QGridLayout()
        fields_layout.setContentsMargins(0, 2, 0, 0)
        fields_layout.setHorizontalSpacing(10)
        fields_layout.setVerticalSpacing(3)
        fields_layout.setColumnStretch(1, 1)
        for row, (key, label_text) in enumerate(fields, start=2):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            field = QLineEdit()
            field.setPlaceholderText("$00.00")
            field.setValidator(QDoubleValidator(0.00, 1000000.00, 2, field))
            field.setAlignment(Qt.AlignRight)
            field.setFixedHeight(28)
            if key == "option_entry":
                field.textChanged.connect(self.track_option_entry_time)
            elif key in ("stock_exit", "option_exit"):
                if key == "option_exit":
                    self.option_exit_input = field
                field.editingFinished.connect(self.track_exit_fields)
            if key == "option_exit":
                self.option_exit_input = field
                field.setEnabled(False)
            self.inputs[key] = field
            fields_layout.addWidget(label, row, 0)
            fields_layout.addWidget(field, row, 1)
        form_layout.addLayout(fields_layout)

        self.image_preview = QLabel("Paste a PNG screenshot\nCtrl + V")
        self.image_preview.setObjectName("imageDrop")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setFixedHeight(68)
        self.image_preview.setScaledContents(False)
        form_layout.addWidget(self.image_preview)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        paste = QPushButton("Paste image")
        paste.setObjectName("secondaryButton")
        paste.setFixedHeight(32)
        paste.clicked.connect(self.paste_image)
        clear = QPushButton("Clear image")
        clear.setObjectName("secondaryButton")
        clear.setFixedHeight(32)
        clear.clicked.connect(self.clear_image)
        actions.addWidget(paste, 1)
        actions.addWidget(clear, 1)
        form_layout.addLayout(actions)

        form_scroll.setWidget(form_card)
        body.addWidget(form_scroll, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.enter_button = QPushButton("Enter")
        self.enter_button.setObjectName("timerButton")
        self.enter_button.setMinimumHeight(32)
        self.enter_button.clicked.connect(self.enter_trade)
        action_row.addWidget(self.enter_button, 1)
        submit = QPushButton("Submit")
        submit.setObjectName("submitButton")
        submit.setMinimumHeight(32)
        submit.clicked.connect(self.add_trade)
        action_row.addWidget(submit, 1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("dangerButton")
        cancel.setMinimumHeight(32)
        cancel.clicked.connect(self.cancel_trade)
        action_row.addWidget(cancel, 1)

        page_layout.addLayout(body, 0)
        page_layout.addLayout(action_row)
        page_layout.addStretch(1)
        self.pages.addWidget(self.entry_page)

    def build_analysis_page(self):
        self.analysis_page = QWidget()
        page_layout = QVBoxLayout(self.analysis_page)
        page_layout.setContentsMargins(24, 20, 24, 22)
        page_layout.setSpacing(14)
        page_layout.addWidget(self.page_header("Trade analysis"))

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.total_stat = self.stat_card("TOTAL TRADES", "0")
        self.pnl_stat = self.stat_card("OPTION P/L", "$0.00")
        self.win_stat = self.stat_card("WIN RATE", "0%")
        for card in (self.total_stat[0], self.pnl_stat[0], self.win_stat[0]):
            stats.addWidget(card)
        page_layout.addLayout(stats)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_heading = QHBoxLayout()
        table_heading.setContentsMargins(20, 14, 20, 8)
        table_title = QLabel("Trade history")
        table_title.setObjectName("tableTitle")
        table_heading.addWidget(table_title)
        table_heading.addStretch()
        export_button = QPushButton("Download full database")
        export_button.setObjectName("submitButton")
        export_button.setFixedHeight(32)
        export_button.setToolTip("Export every column from the trades database, including fields not shown here.")
        export_button.clicked.connect(self.export_full_database)
        table_heading.addWidget(export_button)
        table_layout.addLayout(table_heading)
        self.table = QTableWidget(0, 11)
        self.table.setShowGrid(True)
        self.table.setHorizontalHeaderLabels(AnalyzeColumns.HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setWordWrap(False)
        self.table.setMinimumSize(0, 0)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)
        header.setSectionResizeMode(AnalyzeColumns.CHART, QHeaderView.Fixed)
        self.table.setColumnWidth(AnalyzeColumns.CHART, 128)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)
        page_layout.addWidget(table_card, 1)
        self.massive_chart_panel = MassiveChartPanel()
        self.massive_chart_panel.setObjectName("card")
        self.massive_chart_panel.setVisible(False)
        self.massive_chart_panel.refresh_requested.connect(self.refresh_current_chart)
        self.massive_chart_panel.details_requested.connect(self.show_chart_details)
        page_layout.addWidget(self.massive_chart_panel, 1)
        self.pages.addWidget(self.analysis_page)

    def build_watchlist_page(self):
        self.watchlist_page = QWidget()
        page_layout = QVBoxLayout(self.watchlist_page)
        page_layout.setContentsMargins(24, 20, 24, 22)
        page_layout.setSpacing(14)
        page_layout.addWidget(self.page_header("Watchlist statistics"))

        intro = QFrame()
        intro.setObjectName("card")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("Daily volatility snapshot")
        title.setObjectName("tableTitle")
        intro_layout.addWidget(title)
        description = QLabel("One Massive batch request for the current session range of your core watchlist. This view is intentionally not labeled ATR(14): accurate ATR(14) requires historical bars for each symbol.")
        description.setObjectName("menuSubtitle")
        description.setWordWrap(True)
        intro_layout.addWidget(description)
        formula = QLabel("Daily range = session high − session low    ·    Range % = daily range ÷ last close")
        formula.setObjectName("eyebrow")
        formula.setWordWrap(True)
        intro_layout.addWidget(formula)
        page_layout.addWidget(intro)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.watchlist_avg_atr = self.stat_card("AVERAGE DAILY RANGE", "—")
        self.watchlist_avg_percent = self.stat_card("AVERAGE RANGE %", "—")
        self.watchlist_updated = self.stat_card("SYMBOLS LOADED", "—")
        for card in (self.watchlist_avg_atr[0], self.watchlist_avg_percent[0], self.watchlist_updated[0]):
            stats.addWidget(card)
        page_layout.addLayout(stats)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout()
        heading.setContentsMargins(20, 14, 20, 8)
        table_title = QLabel("Core watchlist")
        table_title.setObjectName("tableTitle")
        heading.addWidget(table_title)
        heading.addStretch()
        self.watchlist_status = QLabel("Ready to load")
        self.watchlist_status.setObjectName("menuSubtitle")
        heading.addWidget(self.watchlist_status)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("submitButton")
        refresh.setFixedHeight(32)
        refresh.clicked.connect(self.show_watchlist_stats)
        heading.addWidget(refresh)
        table_layout.addLayout(heading)
        self.watchlist_table = QTableWidget(0, 5)
        self.watchlist_table.setHorizontalHeaderLabels(["Ticker", "Daily range", "Range %", "Last close", "Status"])
        self.watchlist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.watchlist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.watchlist_table.verticalHeader().setVisible(False)
        self.watchlist_table.verticalHeader().setDefaultSectionSize(44)
        self.watchlist_table.setAlternatingRowColors(True)
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.watchlist_table)
        page_layout.addWidget(table_card, 1)
        self.pages.addWidget(self.watchlist_page)

    def page_header(self, title_text):
        header = QFrame()
        header.setObjectName("topBar")
        heading = QHBoxLayout(header)
        heading.setContentsMargins(14, 9, 14, 9)
        title = QLabel(title_text)
        title.setObjectName("title")
        heading.addWidget(title)
        heading.addStretch()
        back = QPushButton("Back to menu")
        back.setObjectName("backButton")
        back.setFixedHeight(36)
        back.clicked.connect(self.show_menu)
        heading.addWidget(back)
        heading.addWidget(self.create_theme_button())
        return header

    def create_theme_button(self):
        button = QPushButton()
        button.setObjectName("themeButton")
        button.setFixedSize(104, 36)
        button.clicked.connect(self.toggle_theme)
        self.theme_buttons.append(button)
        return button

    def apply_theme(self):
        QApplication.instance().setStyleSheet(theme_stylesheet(self.theme_mode))
        label = "Light Mode" if self.theme_mode == "dark" else "Dark Mode"
        for button in self.theme_buttons:
            button.setText(label)
        palette = THEME_PALETTES[self.theme_mode]
        self.positive_color = palette["positive"]
        self.negative_color = palette["negative"]
        self.refresh_trade_colors()

    def toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        self.settings.setValue("theme", self.theme_mode)
        self.apply_theme()

    def refresh_trade_colors(self):
        if not hasattr(self, "table"):
            return
        for row in range(self.table.rowCount()):
            pnl_item = self.table.item(row, 7)
            percentage_item = self.table.item(row, 8)
            if pnl_item is None or percentage_item is None:
                continue
            color = self.positive_color if not pnl_item.text().startswith("-") else self.negative_color
            pnl_item.setForeground(QColor(color))
            percentage_item.setForeground(QColor(color))

    def show_menu(self):
        self.show_page(self.menu_page)

    def show_add_entry(self):
        self.show_page(self.entry_page)

    def show_analysis(self):
        self.show_page(self.analysis_page)

    def show_watchlist_stats(self):
        self.show_page(self.watchlist_page)
        self.watchlist_status.setText("Loading market data…")
        self.watchlist_stats_requested.emit()

    @staticmethod
    def dashboard_hint(text):
        hint = QLabel(text)
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        return hint

    @staticmethod
    def dashboard_card(title, hint):
        card = QFrame()
        card.setObjectName("dashboardCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        hint_label = TradeTracker.dashboard_hint(hint)
        layout.addWidget(hint_label)
        return card, layout

    def select_home_provider(self, provider):
        self.provider_settings.setValue("market_data/provider", provider)
        self.update_data_indicator(provider, "gray")
        self.open_data_config()

    def test_data_connection(self):
        provider_name = self.provider_settings.value("market_data/provider", "Massive", type=str)
        self.update_data_indicator(provider_name, "yellow")
        self.home_data_status.setText("Testing connection…")
        try:
            ok, message = get_active_market_data_provider().test_connection()
        except Exception as error:
            ok, message = False, str(error)
        self.update_data_indicator(provider_name, "green" if ok else "red")
        self.home_data_status.setText(message)

    def show_database_diagnostics(self):
        QMessageBox.information(
            self,
            "Database Diagnostics",
            f"{diagnostic_summary()}\n\n"
            f"Active provider: {self.provider_settings.value('market_data/provider', 'Massive', type=str)}",
        )

    def open_data_config(self):
        dialog = DataConfigDialog(self)
        dialog.provider_changed.connect(self.update_data_indicator)
        dialog.exec()
        active = self.provider_settings.value("market_data/provider", "Massive", type=str)
        self.home_provider_combo.blockSignals(True)
        self.home_provider_combo.setCurrentText(active)
        self.home_provider_combo.blockSignals(False)
        self.test_data_connection()

    @Slot(str, str)
    def update_data_indicator(self, provider, status):
        if not hasattr(self, "data_indicator"):
            return
        colors = {"green": "#22c55e", "red": "#ef4444", "yellow": "#eab308", "gray": "#9da3ad"}
        self.data_indicator.setText(f"Data ● {provider}")
        self.data_indicator.setStyleSheet(f"color: {colors.get(status, colors['gray'])};")
        if hasattr(self, "home_data_status"):
            status_text = {"green": "● Connected", "red": "● Not connected", "yellow": "● Testing", "gray": "● Not configured"}
            self.home_data_status.setText(status_text.get(status, "● Not configured"))

    def _get_trade_for_chart(self, trade_id):
        row = self.db.execute(
            """
            SELECT id, ticker_symbol, created_at, option_entry_typed_at,
                   option_exit_typed_at, stock_entry, stock_exit, screenshot
            FROM trades WHERE id = ?
            """,
            (trade_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Trade {trade_id} was not found.")
        return {
            "id": row[0], "ticker_symbol": row[1], "created_at": row[2],
            "option_entry_typed_at": row[3], "option_exit_typed_at": row[4],
            "stock_entry": row[5], "stock_exit": row[6],
            "screenshot": row[7],
        }

    def load_chart_for_trade(self, trade_id):
        self.show_analysis()
        try:
            trade = self._get_trade_for_chart(trade_id)
            self.current_chart_trade = trade
            self.massive_chart_panel.setVisible(True)
            self.massive_chart_panel.show_loading(trade)
            self.chart_requested.emit(trade, False)
        except Exception as error:
            self.show_chart_error(str(error))

    def view_screenshot_for_trade(self, trade_id):
        self.show_analysis()
        try:
            trade = self._get_trade_for_chart(trade_id)
            self.massive_chart_panel.setVisible(True)
            self.massive_chart_panel.show_screenshot(trade)
        except Exception as error:
            self.show_chart_error(str(error))

    def refresh_current_chart(self):
        if not self.current_chart_trade:
            return
        answer = QMessageBox.question(
            self,
            "Refresh Market Data",
            "Fetch new market data and save it as a separate snapshot? The existing snapshot will be preserved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.massive_chart_panel.show_loading(self.current_chart_trade)
        self.chart_requested.emit(self.current_chart_trade, True)

    def show_chart_details(self):
        if not self.chart_result:
            return
        result = self.chart_result
        request = result.get("request")
        details = [
            f"Data source: {result.get('provider', '—')}",
            f"Cache status: {result.get('status', '—')}",
            f"Snapshot ID: {result.get('snapshot_id', '—')}",
            f"Fetched: {result.get('fetched_at', '—')}",
            f"Bars: {len(result.get('candles') or [])}",
        ]
        if request:
            details.extend([
                f"Trade ID: {request.trade_id}",
                f"Range: {request.start_key} → {request.end_key}",
                f"Resolution: {request.resolution}",
            ])
        if result.get("coverage_note"):
            details.append(f"Coverage: {result['coverage_note']}")
        if result.get("error_message"):
            details.append(f"Error: {result['error_message']}")
        QMessageBox.information(self, "Market Data Details", "\n".join(details))

    @Slot(object, object)
    def apply_chart_data(self, trade, result):
        self.chart_result = result
        self.massive_chart_panel.setVisible(True)
        if result.get("candles"):
            self.massive_chart_panel.show_data(trade, result["candles"], result)
        else:
            self.massive_chart_panel.show_error(
                f"Data source: {result.get('provider', '—')} · "
                f"Cache status: {result.get('status', 'No data available')}"
                + (f" · {result['error_message']}" if result.get("error_message") else "")
            )

    @Slot(str)
    def show_chart_error(self, message):
        self.massive_chart_panel.setVisible(True)
        self.massive_chart_panel.show_error(f"Chart unavailable: {message}")

    def create_database_backup(self):
        try:
            backup_path = create_backup(DB_PATH)
            QMessageBox.information(self, "Database Backup", f"Backup created at:\n{backup_path}")
        except Exception as error:
            QMessageBox.warning(self, "Backup Failed", str(error))

    def export_full_database(self):
        suggested_name = DB_PATH.parent / f"trades-full-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download Full Trade Database",
            str(suggested_name),
            "SQLite database (*.db);;All files (*)",
        )
        if not target_path:
            return
        try:
            self.db.commit()
            exported = export_database_copy(DB_PATH, target_path)
            QMessageBox.information(
                self,
                "Database Downloaded",
                "A complete copy of the trade database was saved to:\n"
                f"{exported}\n\n"
                "The export includes every trades-table column, including timestamps, "
                "trade duration, market context, and screenshots.",
            )
        except Exception as error:
            QMessageBox.warning(self, "Download Failed", str(error))

    def restore_database_backup(self):
        backup_path, _ = QFileDialog.getOpenFileName(
            self, "Select Trade Tracker Backup", str(DB_PATH.parent), "SQLite databases (*.db *.sqlite)"
        )
        if not backup_path:
            return
        answer = QMessageBox.question(
            self,
            "Confirm Database Restore",
            "This will replace the active database. A safety backup will be created first. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.db.commit()
            self.db.close()
            safety_backup = restore_backup(DB_PATH, backup_path, confirmed=True)
            self.db = configure(connect(DB_PATH))
            run_migrations(self.db)
            self.load_trades()
            QMessageBox.information(self, "Database Restored", f"Safety backup:\n{safety_backup}")
        except Exception as error:
            QMessageBox.warning(self, "Restore Failed", str(error))

    def show_page(self, page):
        self.pages.setCurrentWidget(page)

    def stat_card(self, label_text, value_text):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        value = QLabel(value_text)
        value.setObjectName("statValue")
        layout.addWidget(label)
        layout.addWidget(value)
        return frame, value

    def paste_image(self):
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(self, "No image", "Copy a PNG or screenshot first, then press Ctrl+V.")
            return
        self.image_encode_requested.emit(image)

    @Slot(bytes, object)
    def apply_encoded_image(self, image_bytes, preview):
        self.image_bytes = image_bytes
        self.image_preview.setPixmap(QPixmap.fromImage(preview))

    @Slot(str)
    def show_worker_error(self, message):
        if hasattr(self, "watchlist_status") and self.pages.currentWidget() is self.watchlist_page:
            self.watchlist_status.setText("Unable to load data")
        QMessageBox.warning(self, "Background operation failed", message)

    def clear_image(self):
        self.image_bytes = None
        self.image_preview.clear()
        self.image_preview.setText("Paste a PNG screenshot\nCtrl + V")

    def capture_input_timestamp(self, field, timestamp_attribute):
        try:
            value = float(field.text())
        except ValueError:
            value = 0.0
        if value > 0.0:
            if getattr(self, timestamp_attribute) is None:
                setattr(self, timestamp_attribute, datetime.now().astimezone())
        else:
            setattr(self, timestamp_attribute, None)

    def track_option_entry_time(self):
        self.capture_input_timestamp(self.inputs["option_entry"], "option_entry_typed_at")

    def enter_trade(self):
        if self.exit_timer_started_at is not None:
            return
        self.exit_timer_started_at = datetime.now().astimezone()
        self.exit_timer_active = True
        self.option_exit_input.setEnabled(True)
        self.enter_button.setEnabled(False)

    def track_exit_fields(self):
        try:
            option_exit = float(self.inputs["option_exit"].text())
            stock_exit = float(self.inputs["stock_exit"].text())
        except ValueError:
            option_exit = 0.0
            stock_exit = 0.0
        if (
            not self.exit_timer_active
            or self.exit_timer_started_at is None
            or option_exit <= 0.0
            or stock_exit <= 0.0
        ):
            return
        self.option_exit_typed_at = datetime.now().astimezone()
        self.exit_timer_active = False

    def add_trade(self):
        values = [float(self.inputs[key].text() or 0)
            for key in ("stock_entry", "option_entry", "stock_exit", "option_exit")]
        ticker_symbol = self.ticker_input.text().strip().upper()
        if not ticker_symbol:
            QMessageBox.warning(
                self,
                "Missing ticker symbol",
                "Enter a ticker symbol before saving the trade.",
            )
            return
        if not self.image_bytes:
            QMessageBox.warning(
                self,
                "Missing screenshot",
                "Paste a screenshot before submitting the trade.",
            )
            return
        self.track_exit_fields()
        has_exit_price = values[3] > 0.0
        length_of_trade_seconds = None
        if has_exit_price:
            if self.exit_timer_started_at is None or self.option_exit_typed_at is None:
                QMessageBox.warning(
                    self,
                    "Exit timer required",
                    "Start the exit timer before entering an option exit price.",
                )
                return
            if self.option_exit_typed_at <= self.exit_timer_started_at:
                QMessageBox.warning(
                    self,
                    "Invalid trade timing",
                    "The exit timestamp must be later than the timer start.",
                )
                return
            length_of_trade_seconds = (
                self.option_exit_typed_at - self.exit_timer_started_at
            ).total_seconds()
        self.persist_trade(values, ticker_symbol, length_of_trade_seconds)
        self.reset_entry_form()
        self.load_trades()

    def cancel_trade(self):
        self.reset_entry_form()

    def persist_trade(
        self,
        values,
        ticker_symbol,
        length_of_trade_seconds,
    ):
        exit_timer_started_at = (
            self.exit_timer_started_at.isoformat()
            if self.exit_timer_started_at is not None
            else None
        )

        option_entry_typed_at = (
            self.option_entry_typed_at.isoformat()
            if self.option_entry_typed_at is not None
            else None
        )

        option_exit_typed_at = (
            self.option_exit_typed_at.isoformat()
            if self.option_exit_typed_at is not None
            else None
        )

        with self.db_lock:
            cursor = self.db.execute(
                """
                INSERT INTO trades (
                    stock_entry,
                    option_entry,
                    stock_exit,
                    option_exit,
                    screenshot,
                    created_at,
                    ticker_symbol,
                    option_type,
                    exit_timer_started_at,
                    option_entry_typed_at,
                    option_exit_typed_at,
                    length_of_trade_seconds,
                    premarket_high,
                    premarket_low,
                    previous_day_high,
                    previous_day_low
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    *values,
                    self.image_bytes,
                    datetime.now().astimezone().isoformat(),
                    ticker_symbol,
                    self.option_type_input.currentText(),
                    exit_timer_started_at,
                    option_entry_typed_at,
                    option_exit_typed_at,
                    length_of_trade_seconds,
                ),
            )

            # Save the inserted trade
            self.db.commit()

    def reset_entry_form(self):
        self.exit_timer_started_at = None
        self.exit_timer_active = False
        self.option_entry_typed_at = None
        self.option_exit_typed_at = None
        self.enter_button.setEnabled(True)
        self.option_exit_input.setEnabled(False)
        self.ticker_input.clear()
        self.option_type_input.setCurrentIndex(0)
        for field in self.inputs.values():
            field.clear()
        self.clear_image()

    def load_trades(self):
        self.trade_load_requested.emit()

    @Slot(list)
    def apply_trade_rows(self, result):
        trades, total, total_pnl, win_rate = result
        self.table.setRowCount(len(trades))
        for row_index, trade in enumerate(trades):
            trade_id = trade[0]
            for column, value in enumerate(trade[1:-1]):
                if column == AnalyzeColumns.SCREENSHOT and value == "Attached":
                    screenshot_button = QPushButton("View Screenshot")
                    screenshot_button.setMinimumSize(120, 34)
                    screenshot_button.clicked.connect(
                        lambda checked=False, trade_id=trade_id: self.view_screenshot_for_trade(trade_id)
                    )
                    self.table.setCellWidget(row_index, column, screenshot_button)
                    continue
                item = QTableWidgetItem(value)
                if column in (AnalyzeColumns.OPTION_PNL, AnalyzeColumns.OPTION_PERCENT):
                    item.setForeground(QColor(self.positive_color if trade[-1] else self.negative_color))
                self.table.setItem(row_index, column, item)
            button = QPushButton("View Chart")
            button.setMinimumSize(120, 34)
            button.clicked.connect(lambda checked=False, trade_id=trade_id: self.load_chart_for_trade(trade_id))
            self.table.setCellWidget(row_index, AnalyzeColumns.CHART, button)
        self.table.resizeColumnsToContents()
        self.total_stat[1].setText(str(total))
        sign = "+" if total_pnl >= 0 else "-"
        self.pnl_stat[1].setText(f"{sign}${abs(total_pnl):.2f}")
        self.win_stat[1].setText(f"{win_rate}%")

    @Slot(list)
    def apply_watchlist_stats(self, result):
        rows, errors = result
        self.watchlist_table.setRowCount(0)
        for row_index, stats in enumerate(rows):
            self.watchlist_table.insertRow(row_index)
            values = (
                stats["ticker"],
                f"${stats['daily_range']:.2f}",
                f"{stats['range_percent']:.2f}%",
                f"${stats['last_close']:.2f}",
                f"{stats['days_used']} session snapshot",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setForeground(QColor(self.positive_color))
                self.watchlist_table.setItem(row_index, column, item)
        if rows:
            average_range = sum(row["daily_range"] for row in rows) / len(rows)
            average_percent = sum(row["range_percent"] for row in rows) / len(rows)
            self.watchlist_avg_atr[1].setText(f"${average_range:.2f}")
            self.watchlist_avg_percent[1].setText(f"{average_percent:.2f}%")
            self.watchlist_updated[1].setText(f"{len(rows)} / {len(WatchlistStatsWorker.TICKERS)}")
        self.watchlist_status.setText(
            f"Updated · {len(rows)} symbols" + (f" · {len(errors)} unavailable" if errors else "")
        )
        if errors:
            self.watchlist_status.setToolTip("\n".join(errors))

    def closeEvent(self, event):
        self.trade_load_thread.quit()
        self.image_encode_thread.quit()
        self.watchlist_thread.quit()
        self.chart_thread.quit()
        self.trade_load_thread.wait()
        self.image_encode_thread.wait()
        self.watchlist_thread.wait()
        self.chart_thread.wait()
        self.db.close()
        event.accept()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = QApplication(sys.argv)
    window = TradeTracker()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
