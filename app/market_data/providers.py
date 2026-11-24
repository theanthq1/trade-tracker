"""Provider interface, configuration, and active-provider factory."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PySide6.QtCore import QSettings

from app.market_data.massive import MassiveClient, MassiveDataError

PROVIDERS = ("Schwab", "Massive", "IBKR PRO")
KEYRING_SERVICE = "trade-tracker"
KEYRING_USER = "massive-api-key"


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        return None


class MarketDataProvider(ABC):
    name = "Unknown"

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def get_historical_bars(self, symbol, start, end, interval):
        raise NotImplementedError

    @abstractmethod
    def get_historical_trades(self, symbol, start, end):
        raise NotImplementedError

    @abstractmethod
    def get_historical_quotes(self, symbol, start, end):
        raise NotImplementedError

    @abstractmethod
    def get_atr14(self, symbol, end_date=None):
        raise NotImplementedError

    @abstractmethod
    def get_watchlist_statistics(self, symbols):
        raise NotImplementedError


class MassiveMarketDataProvider(MarketDataProvider):
    name = "Massive"

    def __init__(self, api_key=None):
        self.client = MassiveClient(timeout=30, api_key=api_key or get_massive_api_key())

    def test_connection(self):
        try:
            self.client._get("/v2/aggs/ticker/AAPL/prev", {})
        except MassiveDataError as error:
            return False, str(error)
        return True, "Massive connection verified."

    def get_historical_bars(self, symbol, start, end, interval):
        return self.client.get_historical_bars(symbol, start, end, interval)

    def get_historical_trades(self, symbol, start, end):
        return self.client.get_historical_trades(symbol, start, end)

    def get_historical_quotes(self, symbol, start, end):
        return self.client.get_historical_quotes(symbol, start, end)

    def get_atr14(self, symbol, end_date=None):
        return self.client.get_atr14(symbol, end_date)

    def get_watchlist_statistics(self, symbols):
        return self.client.get_watchlist_statistics(symbols)


class SchwabMarketDataProvider(MarketDataProvider):
    name = "Schwab"

    def __init__(self, settings=None):
        self.settings = settings or provider_settings()

    def test_connection(self):
        if not self.settings.value("schwab/client_id", ""):
            return False, "Schwab Client ID is not configured."
        return False, "Schwab OAuth is not configured in this installation."

    def get_historical_bars(self, symbol, start, end, interval):
        raise RuntimeError("Schwab historical bars require a completed OAuth connection.")

    def get_historical_trades(self, symbol, start, end):
        raise RuntimeError("Schwab historical trades require a completed OAuth connection.")

    def get_historical_quotes(self, symbol, start, end):
        raise RuntimeError("Schwab historical quotes require a completed OAuth connection.")

    def get_atr14(self, symbol, end_date=None):
        raise RuntimeError("Schwab ATR requires a completed OAuth connection.")

    def get_watchlist_statistics(self, symbols):
        raise RuntimeError("Schwab watchlist data requires a completed OAuth connection.")


class IBKRMarketDataProvider(MarketDataProvider):
    name = "IBKR PRO"

    def __init__(self, settings=None):
        settings = settings or provider_settings()
        configured = settings.value("ibkr/base_url", "http://127.0.0.1:5000", type=str).rstrip("/")
        port = settings.value("ibkr/port", "5000", type=str).strip()
        parsed = urlsplit(configured)
        hostname = parsed.hostname or "127.0.0.1"
        netloc = f"{hostname}:{port}"
        self.base_url = urlunsplit((parsed.scheme or "http", netloc, parsed.path.rstrip("/"), "", "")).rstrip("/")

    def test_connection(self):
        try:
            request = Request(f"{self.base_url}/v1/api/iserver/auth/status")
            with urlopen(request, timeout=5) as response:
                payload = json.load(response)
            if payload.get("authenticated") is True:
                return True, "IBKR connection verified."
            return False, "IBKR Gateway is reachable but not authenticated."
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            return False, f"IBKR connection failed: {error}"

    def get_historical_bars(self, symbol, start, end, interval):
        raise RuntimeError("IBKR historical bars are not available until Gateway/TWS is connected.")

    def get_historical_trades(self, symbol, start, end):
        raise RuntimeError("IBKR historical trades are not available until Gateway/TWS is connected.")

    def get_historical_quotes(self, symbol, start, end):
        raise RuntimeError("IBKR historical quotes are not available until Gateway/TWS is connected.")

    def get_atr14(self, symbol, end_date=None):
        raise RuntimeError("IBKR ATR is not available until Gateway/TWS is connected.")

    def get_watchlist_statistics(self, symbols):
        raise RuntimeError("IBKR watchlist data is not available until Gateway/TWS is connected.")


def provider_settings():
    return QSettings("TradeTracker", "TradeTracker")


def get_massive_api_key() -> str:
    settings = provider_settings()
    if settings.value("massive/key_cleared", False, type=bool):
        return ""
    keyring = _keyring()
    if keyring:
        try:
            value = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            if value:
                return value
        except Exception:
            pass
    return settings.value("massive/api_key", "", type=str) or os.environ.get("MASSIVE_API_KEY", "")


def save_massive_api_key(value: str) -> None:
    settings = provider_settings()
    settings.setValue("massive/key_cleared", not bool(value))
    settings.setValue("massive/api_key", value)
    keyring = _keyring()
    if keyring:
        try:
            if value:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USER, value)
            else:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
            return
        except Exception:
            pass


def clear_massive_api_key() -> None:
    save_massive_api_key("")


def get_active_market_data_provider() -> MarketDataProvider:
    settings = provider_settings()
    selected = settings.value("market_data/provider", "Massive", type=str)
    if selected == "Schwab":
        return SchwabMarketDataProvider(settings)
    if selected == "IBKR PRO":
        return IBKRMarketDataProvider(settings)
    return MassiveMarketDataProvider()
