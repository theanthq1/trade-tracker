# Database migrations

The executable SQLite migration API is in `database.py` and is re-exported by
`app.database.migrations`. The `trades` migration rebuilds the table
transactionally when legacy columns, including `status`, are present.
