import sqlite3
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2 import Binary


PROJECT_DIR = Path(__file__).resolve().parent
SQLITE_PATH = PROJECT_DIR / "trades.db"

env = dotenv_values(PROJECT_DIR / ".env")
database_url = env.get("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL is missing from .env")


columns = [
    "id",
    "stock_entry",
    "option_entry",
    "stock_exit",
    "option_exit",
    "screenshot",
    "created_at",
    "ticker_symbol",
    "option_type",
    "exit_timer_started_at",
    "option_entry_typed_at",
    "option_exit_typed_at",
    "length_of_trade_seconds",
    "premarket_high",
    "premarket_low",
    "regular_session_open",
    "previous_day_open",
    "previous_day_high",
    "previous_day_low",
]

column_sql = ", ".join(columns)
placeholders = ", ".join(["%s"] * len(columns))

update_sql = ", ".join(
    f"{column} = EXCLUDED.{column}"
    for column in columns
    if column != "id"
)

insert_sql = f"""
    INSERT INTO public.trades ({column_sql})
    VALUES ({placeholders})
    ON CONFLICT (id) DO UPDATE SET {update_sql}
"""


with sqlite3.connect(SQLITE_PATH) as sqlite_connection:
    sqlite_connection.row_factory = sqlite3.Row
    rows = sqlite_connection.execute(
        f"SELECT {column_sql} FROM trades ORDER BY id"
    ).fetchall()


with psycopg2.connect(database_url) as postgres_connection:
    with postgres_connection.cursor() as cursor:
        for row in rows:
            values = [row[column] for column in columns]

            screenshot_index = columns.index("screenshot")
            if values[screenshot_index] is not None:
                values[screenshot_index] = Binary(values[screenshot_index])

            cursor.execute(insert_sql, values)

    postgres_connection.commit()


print(f"Migrated {len(rows)} trades to Supabase.")