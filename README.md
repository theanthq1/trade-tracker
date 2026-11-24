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

Application data is stored in the application directory at `trades.db`.
Backups are stored in the adjacent `backups/` directory.

## Analyze tab

Analyze displays the saved trade history, total trades, option P/L, win rate,
screenshots, timestamps, and trade details. Each row has a read-only View Chart
action that retrieves one-minute historical OHLC data from Massive for the
underlying ticker, from 4:00 AM through 10:30 AM America/New_York. The chart
marks the actual recorded stock entry and exit; it does not create simulated
orders. Massive's free Stocks Basic plan is end-of-day, so a chart for a trade
recorded today becomes available after midnight Eastern Time; the app avoids
sending that request and explains the delay instead of returning a plan error.

## Planned market replay

The desktop application uses Massive's direct REST integration because the
hosted Massive MCP server is an OAuth connection for MCP clients, not an
in-process API available to the Qt application. The REST client reads
`MASSIVE_API_KEY` from `.env`; the key is never stored in source code or
printed in logs. OHLC data cannot reveal the intrabar path, so finer replay
accuracy would require Massive trade/quote data.

The Data button on the main menu selects Schwab, Massive, or IBKR PRO. The
selection persists in application settings and controls charts and ATR. A
provider is never substituted automatically when the selected provider fails.
Massive keys are stored in the operating-system keyring when available, with a
local settings fallback.

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
