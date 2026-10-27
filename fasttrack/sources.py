# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Three fragmented sources behind one SQL surface: Zetaris Lightning, or a local stand-in.

The agent always writes the same SQL (`FT_RULES.rules`, `FT_PRACTICES.practices`,
`FT_WAITS.waits`). With Zetaris configured, the query runs federated over JDBC; without it,
an in-memory SQLite database with the same three schemas answers, so tests and offline demos
run anywhere. The answer always records which backend produced each row.
"""

from __future__ import annotations

import csv
import os
import re
import sqlite3
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seed"
TABLES = {"FT_RULES": "rules", "FT_PRACTICES": "practices", "FT_WAITS": "waits"}
SCHEMA = """\
FT_RULES.rules(rule_id, topic, rule, legal_basis, applies_to)
FT_PRACTICES.practices(practice_id, name, district, specialty, open_consultation_hours_per_week, accepts_new_patients, online_booking, sample)
FT_WAITS.waits(observation_id, practice_id, channel, days_to_appointment, observed_on, sample)
"""
MAX_ROWS = 200
_SELECT = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|pragma|grant)\b|;", re.IGNORECASE)


def check_sql(sql: str) -> str:
    """Read-only guard: exactly one SELECT, no statement separator, no DDL/DML."""
    sql = sql.strip().rstrip(";").strip()
    if not _SELECT.match(sql) or _FORBIDDEN.search(sql):
        raise ValueError("only a single read-only SELECT is allowed")
    return sql


class LocalSource:
    name = "local-sqlite"

    def __init__(self, seed: Path = SEED):
        self.db = sqlite3.connect(":memory:")
        for schema, table in TABLES.items():
            self.db.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
            with open(seed / f"{table}.csv", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            cols = list(rows[0])
            self.db.execute(f"CREATE TABLE {schema}.{table} ({', '.join(cols)})")
            self.db.executemany(
                f"INSERT INTO {schema}.{table} VALUES ({', '.join('?' * len(cols))})",
                [[_typed(r[c]) for c in cols] for r in rows],
            )

    def query(self, sql: str) -> list[dict]:
        cur = self.db.execute(check_sql(sql))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchmany(MAX_ROWS)]


class ZetarisSource:
    """Zetaris Lightning over JDBC (port 10000) with the driver jar from the platform kit."""

    name = "zetaris-lightning"

    def __init__(self):
        import jaydebeapi  # optional dependency, only needed against a real platform

        self.conn = jaydebeapi.connect(
            "com.zetaris.lightning.jdbc.LightningDriver",
            os.environ.get("ZETARIS_JDBC_URL", "jdbc:zetaris:lightning@localhost:10000"),
            [os.environ["ZETARIS_USER"], os.environ["ZETARIS_PASSWORD"]],
            jars=_jars(os.environ["ZETARIS_JDBC_JAR"]),
        )

    def query(self, sql: str) -> list[dict]:
        cur = self.conn.cursor()
        try:
            cur.execute(check_sql(sql))
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchmany(MAX_ROWS)]
        finally:
            cur.close()


def _jars(path: str) -> list[str]:
    """The driver jar, or every jar in a directory (the compose mount)."""
    p = Path(path)
    return sorted(str(j) for j in p.glob("*.jar")) if p.is_dir() else [path]


def _typed(value: str):
    return int(value) if value.isdigit() else value


def open_source():
    """Zetaris when ZETARIS_JDBC_JAR is set, otherwise the local stand-in."""
    return ZetarisSource() if os.environ.get("ZETARIS_JDBC_JAR") else LocalSource()
