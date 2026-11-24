# Trade Tracker Desktop

A local-first Qt desktop trade journal for Linux, Windows, and macOS. It
records stock and option trades, screenshots, entry/exit timestamps, and
trade-performance statistics in SQLite.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
./run.sh
```

The legacy launcher remains available:

```bash
python trade_tracker.py
```

## Data

Application data is stored outside the source checkout:

- Linux: `~/.local/share/trade-tracker/trades.db`
- Windows: `%APPDATA%\\TradeTracker\\trades.db`
- macOS: `~/Library/Application Support/TradeTracker/trades.db`

Set `TRADE_TRACKER_DATA_DIR` for a deliberate custom data location.

## Analyze tab

Analyze displays the saved trade history, total trades, option P/L, win rate,
screenshots, timestamps, and trade details. The embedded TradingView chart uses
the selected stock ticker and replays one-minute bars from the local
`stock_candles` table from 9:30–10:30 AM America/New_York. The replay starts
empty and reveals one candle at a time with play/pause, stepping, reset, and
speed controls. Simulated orders support close/next-open execution,
slippage, commissions, and P/L metrics. Because the source is OHLC bars, the
replay cannot know the order of price movement inside a minute.

## Backups

The backup service uses SQLite's online backup API and writes timestamped files
under the database directory's `backups/` folder.

```python
from app.database.backup import create_backup
from app.settings import database_path
print(create_backup(database_path()))
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -v
```

Never commit `.env`, database files, screenshots, or credentials.
