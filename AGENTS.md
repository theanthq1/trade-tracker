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
- Historical trade analysis

---

## Core Objectives

The application must:

1. Read individual trades from `trades.db`.
2. Identify the underlying stock ticker and trade date.
3. Calculate trade statistics such as:
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

Do not change the existing schema without first explaining the reason and migration plan.

Charting is read-only and uses Massive market data for the selected trade.
Preserve actual recorded executions only; do not reintroduce simulated order
entry without an explicit request.
