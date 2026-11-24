from __future__ import annotations


class AnalyzeTableColumns:
    DATE = 0
    TICKER = 1
    OPTION_TYPE = 2
    STOCK_ENTRY = 3
    OPTION_ENTRY = 4
    STOCK_EXIT = 5
    OPTION_EXIT = 6
    OPTION_PNL = 7
    OPTION_PERCENT = 8
    SCREENSHOT = 9
    CHART = 10

    HEADERS = [
        "Date", "Ticker", "Option type", "Stock entry", "Option entry",
        "Stock exit", "Option exit", "Option P/L", "Option %", "Screenshot", "Chart",
    ]
