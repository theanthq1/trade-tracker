"""Market-data provider configuration dialog."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QVBoxLayout,
)

from app.market_data.providers import (
    PROVIDERS, clear_massive_api_key, get_active_market_data_provider,
    get_massive_api_key, provider_settings, save_massive_api_key,
)


class DataConfigDialog(QDialog):
    provider_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Market Data Provider")
        self.setMinimumWidth(500)
        self.settings = provider_settings()
        self.provider = QComboBox()
        self.provider.addItems(list(PROVIDERS))
        selected = self.settings.value("market_data/provider", "Massive", type=str)
        self.provider.setCurrentText(selected if selected in PROVIDERS else "Massive")
        self.provider.currentTextChanged.connect(self._select_page)

        self.pages = QStackedWidget()
        self.page_indexes = {"Massive": 0, "Schwab": 1, "IBKR PRO": 2}
        self.massive_key = QLineEdit()
        self.massive_key.setEchoMode(QLineEdit.Password)
        self.massive_key.setPlaceholderText("Paste Massive API key")
        self.massive_key.setText(get_massive_api_key())
        massive_save = QPushButton("Save and Test Connection")
        massive_save.clicked.connect(self._save_and_test)
        massive_clear = QPushButton("Clear API key")
        massive_clear.clicked.connect(self._clear_key)
        self.massive_status = QLabel()
        massive_form = QFormLayout()
        massive_form.addRow("Massive API Key", self.massive_key)
        massive_actions = QHBoxLayout()
        massive_actions.addWidget(massive_save)
        massive_actions.addWidget(massive_clear)
        massive_form.addRow("", massive_actions)
        massive_form.addRow("Status", self.massive_status)
        self.pages.addWidget(self._group("Massive", massive_form))

        self.schwab_client_id = QLineEdit(self.settings.value("schwab/client_id", "", type=str))
        self.schwab_client_secret = QLineEdit(self.settings.value("schwab/client_secret", "", type=str))
        self.schwab_client_secret.setEchoMode(QLineEdit.Password)
        self.schwab_redirect = QLineEdit(self.settings.value("schwab/redirect_uri", "", type=str))
        schwab_auth = QPushButton("Authorize with Schwab")
        schwab_auth.clicked.connect(lambda: self._set_status(self.schwab_status, "Schwab OAuth is not available in this installation."))
        self.schwab_status = QLabel()
        schwab_form = QFormLayout()
        schwab_form.addRow("Client ID", self.schwab_client_id)
        schwab_form.addRow("Client Secret", self.schwab_client_secret)
        schwab_form.addRow("Redirect URI", self.schwab_redirect)
        schwab_form.addRow("", schwab_auth)
        schwab_form.addRow("Status", self.schwab_status)
        self.pages.addWidget(self._group("Schwab OAuth", schwab_form))

        self.ibkr_url = QLineEdit(self.settings.value("ibkr/base_url", "http://127.0.0.1:5000", type=str))
        self.ibkr_port = QLineEdit(self.settings.value("ibkr/port", "5000", type=str))
        self.ibkr_account = QLineEdit(self.settings.value("ibkr/account", "", type=str))
        self.ibkr_mode = QComboBox()
        self.ibkr_mode.addItems(["Paper", "Live"])
        self.ibkr_mode.setCurrentText(self.settings.value("ibkr/mode", "Paper", type=str))
        ibkr_test = QPushButton("Test Connection")
        ibkr_test.clicked.connect(self._save_and_test)
        self.ibkr_status = QLabel()
        ibkr_form = QFormLayout()
        ibkr_form.addRow("Gateway/TWS URL", self.ibkr_url)
        ibkr_form.addRow("Port", self.ibkr_port)
        ibkr_form.addRow("Account number", self.ibkr_account)
        ibkr_form.addRow("Mode", self.ibkr_mode)
        ibkr_form.addRow("", ibkr_test)
        ibkr_form.addRow("Status", self.ibkr_status)
        self.pages.addWidget(self._group("IBKR PRO", ibkr_form))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Market Data Provider", self.provider)
        layout.addLayout(form)
        layout.addWidget(self.pages)
        layout.addWidget(buttons)
        self._select_page(self.provider.currentText())

    @staticmethod
    def _group(title, form):
        group = QGroupBox(title)
        group.setLayout(form)
        return group

    def _select_page(self, provider):
        self.pages.setCurrentIndex(self.page_indexes[provider])
        self.settings.setValue("market_data/provider", provider)
        self.provider_changed.emit(provider, "gray")

    def _save(self):
        provider = self.provider.currentText()
        if provider == "Massive":
            self._save_massive()
        elif provider == "Schwab":
            self.settings.setValue("schwab/client_id", self.schwab_client_id.text().strip())
            self.settings.setValue("schwab/client_secret", self.schwab_client_secret.text())
            self.settings.setValue("schwab/redirect_uri", self.schwab_redirect.text().strip())
        else:
            self._save_ibkr()
        self.settings.setValue("market_data/provider", provider)
        self.provider_changed.emit(provider, "gray")
        self.accept()

    def _save_and_test(self):
        provider_name = self.provider.currentText()
        if provider_name == "Massive":
            self._save_massive()
        elif provider_name == "Schwab":
            self.settings.setValue("schwab/client_id", self.schwab_client_id.text().strip())
            self.settings.setValue("schwab/client_secret", self.schwab_client_secret.text())
            self.settings.setValue("schwab/redirect_uri", self.schwab_redirect.text().strip())
        else:
            self._save_ibkr()
        self.settings.setValue("market_data/provider", provider_name)
        provider = get_active_market_data_provider()
        self.provider_changed.emit(provider.name, "yellow")
        ok, message = provider.test_connection()
        self.provider_changed.emit(provider.name, "green" if ok else "red")
        self._set_status(self._status_for(provider.name), message)

    def _save_massive(self):
        save_massive_api_key(self.massive_key.text().strip())

    def _clear_key(self):
        clear_massive_api_key()
        self.massive_key.clear()
        self._set_status(self.massive_status, "API key cleared.")

    def _save_ibkr(self):
        self.settings.setValue("ibkr/base_url", self.ibkr_url.text().strip())
        self.settings.setValue("ibkr/port", self.ibkr_port.text().strip())
        self.settings.setValue("ibkr/account", self.ibkr_account.text().strip())
        self.settings.setValue("ibkr/mode", self.ibkr_mode.currentText())

    def _status_for(self, provider):
        return {"Massive": self.massive_status, "Schwab": self.schwab_status, "IBKR PRO": self.ibkr_status}[provider]

    @staticmethod
    def _set_status(label, message):
        label.setText(message)
