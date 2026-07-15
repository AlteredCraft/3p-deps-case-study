"""Application-factory and CLI behavior."""
from __future__ import annotations


def test_init_db_cli_creates_tables(app, db_path):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    assert "Initialized the database" in result.output

    # Tables exist and are queryable (the schema our tests depend on).
    import sqlite3

    con = sqlite3.connect(db_path)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert {"users", "tasks"} <= names
