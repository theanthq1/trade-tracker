# Project instructions

Always use the OpenAI Developer Docs MCP server for work involving the OpenAI API, plugins, ChatGPT, or Codex, without requiring the user to ask explicitly.

# AGENTS.md

## Project Overview

This is a Python Qt desktop trading-analysis application.

Project location:

/home/spitfire/Applications/trade-tracker-desktop/

Launch command:

python3 trade_tracker.py

The application uses:

- Python
- Qt GUI
- SQLite
- Massive MCP data
- TradingView-compatible chart rendering
- Historical trade analysis
- Market replay functionality

---

## Core Objectives

The application must:

1. Read individual trades from `trades.db`.
2. Identify the underlying stock ticker and trade date.
3. Retrieve historical stock market data for the first hour of the trading day.
4. Display candlestick charts from premarket to the end of the first hour.
5. Mark actual stock entry and exit executions.
6. Support historical price-action replay.
7. Calculate trade statistics such as:
   - Percentage return
   - Win/loss result
   - Mean return
   - Variance
   - Standard deviation
   - Sharpe ratio
   - Holding period
   - ATR

---

## Database

Inspect the database schema before modifying queries.

Primary tables currently include:

### `trades`

Relevant fields may include:

- `id`
- `ticker_symbol`
- `option_type`
- `stock_entry`
- `stock_exit`
- `option_entry`
- `option_exit`
- `created_at`
- `exit_timer_started_at`
- `option_entry_typed_at`
- `option_exit_typed_at`
- `length_of_trade_seconds`

### `stock_candles`

Relevant fields may include:

- `symbol`
- `trading_date`
- `candle_time`
- `open`
- `high`
- `low`
- `close`
- `volume`

Do not change the existing schema without first explaining the reason and migration plan.

---

## Trade Selection Workflow

The chart must begin from a specific row in the Analyze tab.

When the user clicks a row's Chart button:

1. Retrieve the exact trade ID.
2. Load the corresponding row from `trades`.
3. Read the underlying stock ticker.
4. Read the trade date.
5. Read stock entry timestamp and price.
6. Read stock exit timestamp and price.
7. Load market data for that ticker and date.
8. Render the chart for that specific trade.

Never use a hard-coded ticker or date.

Use the underlying stock ticker, not the option contract symbol.

---

## Market Data

Use the connected Massive MCP 