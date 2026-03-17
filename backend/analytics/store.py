"""
analytics/store.py
DuckDB-based storage layer.
Saves normalized records, supports fast SQL queries, writes Parquet snapshots.
"""

import os
import duckdb
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/surveillance.duckdb")
SNAPSHOTS_DIR = Path("data/snapshots")


def get_conn() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS disease_records (
            id          VARCHAR DEFAULT gen_random_uuid(),
            disease     VARCHAR,
            species     VARCHAR,
            disease_type VARCHAR,
            country     VARCHAR,
            iso2        VARCHAR,
            lat         DOUBLE,
            lon         DOUBLE,
            cases_total BIGINT,
            deaths_total BIGINT,
            cases_today BIGINT,
            deaths_today BIGINT,
            cfr         DOUBLE,
            source      VARCHAR,
            fetched_at  VARCHAR,
            snapshot_date VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS outbreak_scores (
            country     VARCHAR,
            disease     VARCHAR,
            score       DOUBLE,
            level       VARCHAR,
            rt          DOUBLE,
            velocity    DOUBLE,
            fetched_at  VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_alerts (
            source      VARCHAR,
            title       VARCHAR,
            summary     VARCHAR,
            link        VARCHAR,
            published   VARCHAR,
            fetched_at  VARCHAR
        )
    """)
    conn.close()


def upsert_records(records: list[dict]):
    """Insert normalized disease records into DuckDB."""
    if not records:
        return
    conn = get_conn()
    today = datetime.now(timezone.utc).date().isoformat()
    conn.execute("DELETE FROM disease_records WHERE snapshot_date = ?", [today])
    conn.executemany(
        """
        INSERT INTO disease_records
        (disease, species, disease_type, country, iso2, lat, lon,
         cases_total, deaths_total, cases_today, deaths_today,
         cfr, source, fetched_at, snapshot_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                r.get("disease", ""),
                r.get("species", ""),
                r.get("disease_type", ""),
                r.get("country", ""),
                r.get("iso2", ""),
                float(r.get("lat", 0) or 0),
                float(r.get("lon", 0) or 0),
                int(r.get("cases_total", 0) or 0),
                int(r.get("deaths_total", 0) or 0),
                int(r.get("cases_today", 0) or 0),
                int(r.get("deaths_today", 0) or 0),
                float(r.get("cfr", 0) or 0),
                r.get("source", ""),
                r.get("fetched_at", ""),
                today,
            )
            for r in records
        ],
    )
    conn.close()


def upsert_scores(scores: list[dict]):
    if not scores:
        return
    conn = get_conn()
    conn.execute("DELETE FROM outbreak_scores WHERE fetched_at LIKE ?",
                 [datetime.now(timezone.utc).date().isoformat() + "%"])
    conn.executemany(
        """INSERT INTO outbreak_scores
           (country, disease, score, level, rt, velocity, fetched_at)
           VALUES (?,?,?,?,?,?,?)""",
        [
            (
                s.get("country", ""),
                s.get("disease", ""),
                float(s.get("score", 0) or 0),
                s.get("level", ""),
                float(s.get("rt", 0) or 0),
                float(s.get("velocity", 0) or 0),
                datetime.now(timezone.utc).isoformat(),
            )
            for s in scores
        ],
    )
    conn.close()


def upsert_alerts(alerts: list[dict]):
    if not alerts:
        return
    conn = get_conn()
    conn.execute("DELETE FROM news_alerts")
    conn.executemany(
        "INSERT INTO news_alerts (source, title, summary, link, published, fetched_at) VALUES (?,?,?,?,?,?)",
        [
            (
                a.get("source", ""),
                a.get("title", ""),
                a.get("summary", ""),
                a.get("link", ""),
                a.get("published", ""),
                a.get("fetched_at", ""),
            )
            for a in alerts
        ],
    )
    conn.close()


def query_available_diseases() -> list[dict]:
    """Return all diseases + species in the DB for the selector."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT disease, species, disease_type,
                   COUNT(*) as country_count,
                   SUM(cases_total) as total_cases
            FROM disease_records
            WHERE cases_total > 0
            GROUP BY disease, species, disease_type
            ORDER BY total_cases DESC
            """
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    cols = ["disease", "species", "disease_type", "country_count", "total_cases"]
    return [dict(zip(cols, r)) for r in rows]


def query_diseases_map(disease: str = "COVID-19") -> list[dict]:
    """All countries for a given disease with lat/lon for map rendering."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT country, iso2, lat, lon,
                   cases_total, deaths_total, cases_today, deaths_today,
                   cfr, species, disease_type, source
            FROM disease_records
            WHERE disease = ? AND cases_total > 0
            ORDER BY cases_total DESC
            """,
            [disease],
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    cols = ["country", "iso2", "lat", "lon", "cases_total", "deaths_total",
            "cases_today", "deaths_today", "cfr", "species", "disease_type", "source"]
    return [dict(zip(cols, r)) for r in rows]


def query_top_countries(disease: str = "COVID-19", limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT country, iso2, lat, lon, cases_total, deaths_total,
               cases_today, cfr
        FROM disease_records
        WHERE disease = ? AND cases_total > 0
        ORDER BY cases_total DESC LIMIT ?
        """,
        [disease, limit],
    ).fetchall()
    conn.close()
    cols = ["country", "iso2", "lat", "lon", "cases_total",
            "deaths_total", "cases_today", "cfr"]
    return [dict(zip(cols, row)) for row in rows]


def query_all_countries_map(disease: str = "COVID-19") -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT country, iso2, lat, lon, cases_total, deaths_total,
               cases_today, deaths_today, cfr
        FROM disease_records
        WHERE disease = ? AND lat != 0 AND lon != 0
        ORDER BY cases_total DESC
        """,
        [disease],
    ).fetchall()
    conn.close()
    cols = ["country", "iso2", "lat", "lon", "cases_total",
            "deaths_total", "cases_today", "deaths_today", "cfr"]
    return [dict(zip(cols, row)) for row in rows]


def query_alerts() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT source, title, summary, link, published FROM news_alerts ORDER BY published DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [dict(zip(["source","title","summary","link","published"], r)) for r in rows]


def query_scores() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT country, disease, score, level, rt, velocity FROM outbreak_scores ORDER BY score DESC"
    ).fetchall()
    conn.close()
    return [dict(zip(["country","disease","score","level","rt","velocity"], r)) for r in rows]


def save_parquet_snapshot(records: list[dict]):
    """Save daily Parquet snapshot for historical analysis."""
    if not records:
        return
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    path = SNAPSHOTS_DIR / f"records_{today}.parquet"
    conn = duckdb.connect()
    import pandas as pd
    df = pd.DataFrame(records)
    conn.execute(f"COPY (SELECT * FROM df) TO '{path}' (FORMAT PARQUET)")
    conn.close()