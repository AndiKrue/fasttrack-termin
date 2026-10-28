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


# Everyday names -> the value stored in the data. Applied to quoted SQL literals before a query runs,
# so "district = 'Köpenick'" finds the Treptow-Köpenick rows instead of nothing.
NICKNAMES = {
    "köpenick": "Treptow-Köpenick", "koepenick": "Treptow-Köpenick", "treptow": "Treptow-Köpenick",
    "friedrichshain": "Friedrichshain-Kreuzberg", "kreuzberg": "Friedrichshain-Kreuzberg",
    "charlottenburg": "Charlottenburg-Wilmersdorf", "wilmersdorf": "Charlottenburg-Wilmersdorf",
    "steglitz": "Steglitz-Zehlendorf", "zehlendorf": "Steglitz-Zehlendorf",
    "hno": "ENT", "hals-nasen-ohren": "ENT",
    "orthopädie": "orthopaedics", "orthopaede": "orthopaedics", "orthopäde": "orthopaedics", "orthopedics": "orthopaedics",
    "hautarzt": "dermatology", "dermatologie": "dermatology",
    "kardiologie": "cardiology", "kardiologe": "cardiology",
    "augenheilkunde": "ophthalmology", "augenarzt": "ophthalmology",
    "gynäkologie": "gynaecology", "frauenarzt": "gynaecology", "gynecology": "gynaecology",
    "neurologie": "neurology", "neurologe": "neurology",
}
_LITERAL = re.compile(r"'([^']*)'")


def _fold(text: str) -> str:
    """Lower case with umlauts spelled out, so 'Köpenick', 'koepenick' and 'KOEPENICK' compare equal."""
    return text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


with open(SEED / "practices.csv", encoding="utf-8", newline="") as _f:
    # the models also write stored names with the umlaut spelled out ('treptow-koepenick')
    _LOOKUP = {_fold(row["district"]): row["district"] for row in csv.DictReader(_f)}
_LOOKUP.update({_fold(k): v for k, v in NICKNAMES.items()})


def canonical_sql(sql: str) -> str:
    """Replace nickname literals with the stored value; a lower-case literal stays lower-case."""

    def swap(m):
        value = _LOOKUP.get(_fold(m.group(1).strip()))
        if value is not None and value == m.group(1):
            return m.group(0)
        if value is None:
            return m.group(0)
        return f"'{value.lower() if m.group(1) == m.group(1).lower() else value}'"

    return _LITERAL.sub(swap, sql)


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
    """Zetaris when ZETARIS_JDBC_JAR is set and Lightning answers, otherwise the local stand-in.

    The answer footer names the backend (trace source), so a fallback never shows as Zetaris.
    """
    if not os.environ.get("ZETARIS_JDBC_JAR"):
        return LocalSource()
    try:
        return ZetarisSource()
    except Exception as exc:
        print(f"[zetaris] connect failed ({type(exc).__name__}: {str(exc)[:200]}); using local-sqlite", flush=True)
        return LocalSource()
