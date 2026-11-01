"""LOAD: write clean data into SQLite and export a CSV copy."""
import logging
import sqlite3
from contextlib import closing

import pandas as pd

import config
from transform import FINAL_COLUMNS

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS weather_readings (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    city                 TEXT NOT NULL,
    observed_at          TEXT NOT NULL,   -- UTC
    temperature_c        REAL,
    temperature_f        REAL,
    feels_like_c         REAL,
    humidity_pct         REAL,
    precipitation_mm     REAL,
    wind_speed_kmh       REAL,
    wind_speed_ms        REAL,
    weather_code         INTEGER,
    weather_description  TEXT,
    feels_like_category  TEXT,
    is_rainy             INTEGER,
    ingested_at          TEXT NOT NULL,
    UNIQUE (city, observed_at)            -- prevents duplicates when the pipeline re-runs
);
"""

INSERT_SQL = f"""
INSERT OR IGNORE INTO weather_readings ({", ".join(FINAL_COLUMNS)})
VALUES ({", ".join(":" + c for c in FINAL_COLUMNS)});
"""


def load(df: pd.DataFrame) -> int:
    """Insert rows; return how many NEW rows were added."""
    # Convert pandas NA/NaN to None so SQLite stores NULL
    records = df.astype(object).where(df.notna(), None).to_dict("records")
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        conn.execute(SCHEMA)
        before = conn.total_changes
        conn.executemany(INSERT_SQL, records)
        conn.commit()
        inserted = conn.total_changes - before
    log.info("Loaded %d new rows (%d duplicates skipped)", inserted, len(records) - inserted)
    return inserted


def export_csv() -> None:
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        df = pd.read_sql_query("SELECT * FROM weather_readings ORDER BY city, observed_at", conn)
    df.to_csv(config.CSV_EXPORT_PATH, index=False)
    log.info("Exported %d rows to %s", len(df), config.CSV_EXPORT_PATH)
