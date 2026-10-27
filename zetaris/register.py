# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Register the three seed sources in a local Zetaris Lightning platform.

Copies data/seed/*.csv into the query engine container, then creates one logical database
per source and one filestore table in each, and counts the rows back over JDBC.
Run from the repository root with ZETARIS_USER, ZETARIS_PASSWORD, ZETARIS_JDBC_JAR set and
ZETARIS_PLATFORM pointing at the platform folder (docker compose project).
"""

import os
import subprocess
import sys
from pathlib import Path

import jaydebeapi

ROOT = Path(__file__).resolve().parent.parent
TARGET = os.environ.get("FT_CONTAINER_DIR", "/tmp/fasttrack")
SOURCES = {"FT_RULES": "rules", "FT_PRACTICES": "practices", "FT_WAITS": "waits"}


def driver_container(platform: str) -> str:
    out = subprocess.run(["docker", "compose", "ps", "-q", "driver"], cwd=platform, capture_output=True, text=True, check=True)
    cid = out.stdout.strip()
    if not cid:
        sys.exit("driver container not running; start the platform first")
    return cid


def main():
    platform = os.environ.get("ZETARIS_PLATFORM", r"C:\Tools\zetaris-platform")
    cid = driver_container(platform)
    subprocess.run(["docker", "exec", cid, "mkdir", "-p", TARGET], check=True)
    for table in SOURCES.values():
        subprocess.run(["docker", "cp", str(ROOT / "data" / "seed" / f"{table}.csv"), f"{cid}:{TARGET}/{table}.csv"], check=True)
    conn = jaydebeapi.connect(
        "com.zetaris.lightning.jdbc.LightningDriver",
        os.environ.get("ZETARIS_JDBC_URL", "jdbc:zetaris:lightning@localhost:10000"),
        [os.environ["ZETARIS_USER"], os.environ["ZETARIS_PASSWORD"]],
        jars=os.environ["ZETARIS_JDBC_JAR"],
    )
    cur = conn.cursor()
    for db, table in SOURCES.items():
        for sql in (
            f'CREATE LIGHTNING DATABASE {db} DESCRIBE BY "FastTrack Termin {table}"',
            f'CREATE LIGHTNING FILESTORE TABLE {table} FROM {db} FORMAT CSV OPTIONS (PATH "file://{TARGET}/{table}.csv", inferSchema "true", header "true")',
        ):
            try:
                cur.execute(sql)
                print("OK  ", sql[:90])
            except Exception as exc:  # already registered on a rerun is fine; anything else is shown
                print("SKIP", sql[:90], "->", str(exc).splitlines()[0][:160])
        cur.execute(f"SELECT count(*) FROM {db}.{table}")
        print(f"{db}.{table}: {cur.fetchall()[0][0]} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
