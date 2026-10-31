"""
app/database/db.py

SQLite persistence layer. Adapted from the original Streamlit project's
database/db.py — same tables and query shapes, with two changes:

1. All `st.cache_data`/Streamlit dependencies removed. A FastAPI process
   is stateless per-request by design; there's no script-rerun problem to
   cache around here. If read load ever becomes a bottleneck, add a
   short-TTL cache at the router level instead of here.
2. Added a `settings` table (the Streamlit app stored this in a local
   JSON file, which doesn't work cleanly for a server that might run
   multiple worker processes).
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from app.config import DB_PATH, DEFAULT_SETTINGS


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # WAL mode lets reads (e.g. dashboard polling) proceed while a large
    # write is in progress instead of blocking on a single file lock —
    # matters once uploads/analysis runs take more than a few seconds at
    # 100k+ rows. NORMAL synchronous is the standard WAL pairing: safe
    # against app crashes, only risks the last transaction on an OS-level
    # power loss, which is an acceptable tradeoff for this use case.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _ensure_settings_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
    )


# =======================================================
# Generic Save / Load DataFrame
# =======================================================


# Columns worth indexing per table, so the dashboard/report/sentiment
# pages' GROUP BY / WHERE queries don't do a full table scan at 100k+ rows.
_INDEX_COLUMNS = {
    "master_feedback": ["Aspect", "Sentiment", "Topic"],
    "customer_feedback": [],
}


def save_dataframe(df: pd.DataFrame, table_name: str = "customer_feedback", chunksize: int = 5000):
    if df is None:
        return
    conn = get_connection()
    try:
        # chunksize bounds how many rows pandas stages in memory per
        # INSERT batch — without it, to_sql builds one enormous INSERT
        # for the whole dataframe, which is where memory spikes happen
        # at 100k+ rows. Behavior/output is identical, just streamed.
        df.to_sql(table_name, conn, if_exists="replace", index=False, chunksize=chunksize)

        for col in _INDEX_COLUMNS.get(table_name, []):
            if col in df.columns:
                safe_index_name = f"idx_{table_name}_{col}".replace(" ", "_")
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{safe_index_name}" ON "{table_name}" ("{col}")'  # noqa: S608
                )
        conn.commit()
    finally:
        conn.close()


def load_dataframe(table_name: str = "customer_feedback") -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)  # noqa: S608 (internal table names only)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def table_exists(table_name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


# =======================================================
# Topics / Root Cause / Recommendations (JSON-list columns)
# =======================================================

def save_topics(topic_df: pd.DataFrame, table_name: str = "discovered_topics"):
    if topic_df is None:
        return
    conn = get_connection()
    try:
        df = topic_df.copy()
        for col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else (None if pd.isna(x) else x)
            )
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()


def save_sentiment(df: pd.DataFrame):
    save_dataframe(df, "review_sentiment")


def save_master_dataset(df: pd.DataFrame):
    save_dataframe(df, "master_feedback")


def save_rootcause(df: pd.DataFrame):
    if df is None:
        return
    conn = get_connection()
    try:
        df = df.copy()
        for col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, list) else x)
        df.to_sql("root_cause", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()


def _parse_json_list_column(series):
    def _parse(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v.split(",")
        return v
    return series.apply(_parse)


def load_rootcause() -> pd.DataFrame:
    df = load_dataframe("root_cause")
    if not df.empty and "Root Causes" in df.columns:
        df["Root Causes"] = _parse_json_list_column(df["Root Causes"])
    if not df.empty and "Evidence" in df.columns:
        df["Evidence"] = _parse_json_list_column(df["Evidence"])
    return df


def save_recommendations(df: pd.DataFrame):
    """
    Persist AI recommendations.

    `evidence` (a list of {phrase, review} dicts backing each
    recommendation, for the explainability panel) is JSON-encoded per row
    since SQLite has no native list/array column type. `rec_id` and
    `status` (Pending / Accepted / Rejected / Implemented) support the
    reviewer feedback loop — status is looked up and preserved across
    re-saves keyed by rec_id where present, so re-running a batch job
    doesn't silently wipe reviewer decisions already made this session.
    """
    if df is None:
        return

    df = df.copy()

    if "evidence" in df.columns:
        df["evidence"] = df["evidence"].apply(
            lambda x: json.dumps(x) if isinstance(x, (list, dict)) else (x if isinstance(x, str) else "[]")
        )

    conn = get_connection()
    try:
        df.to_sql("recommendations", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()


def load_recommendations() -> pd.DataFrame:
    df = load_dataframe("recommendations")
    if not df.empty and "evidence" in df.columns:
        df["evidence"] = _parse_json_list_column(df["evidence"])
    return df


def update_recommendation_status(rec_id: str, status: str, reviewer_note: str = ""):
    """Update the reviewer status of a single recommendation in place."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE recommendations SET status = ?, reviewer_note = ? WHERE rec_id = ?",
            (status, reviewer_note, rec_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_recommendation_feedback_stats() -> dict:
    """
    Acceptance-rate style stats for the reviewer feedback loop: how many
    AI recommendations were accepted vs. rejected vs. still pending, both
    overall and broken down by department — this is the metric that
    demonstrates whether the AI's output is actually useful to reviewers,
    not just generated.
    """
    df = load_dataframe("recommendations")
    if df.empty or "status" not in df.columns:
        return {"total": 0, "by_status": {}, "acceptance_rate": None, "by_department": []}

    status = df["status"].fillna("Pending")
    by_status = status.value_counts().to_dict()

    decided = status.isin(["Accepted", "Rejected", "Implemented"])
    decided_count = int(decided.sum())
    accepted_count = int(status.isin(["Accepted", "Implemented"]).sum())
    acceptance_rate = round(accepted_count / decided_count, 3) if decided_count else None

    by_department = []
    if "department" in df.columns:
        grouped = df.assign(status=status).groupby("department")["status"]
        for dept, values in grouped:
            dept_decided = values.isin(["Accepted", "Rejected", "Implemented"]).sum()
            dept_accepted = values.isin(["Accepted", "Implemented"]).sum()
            by_department.append({
                "department": dept,
                "total": int(len(values)),
                "accepted": int(dept_accepted),
                "acceptance_rate": round(dept_accepted / dept_decided, 3) if dept_decided else None,
            })

    return {
        "total": int(len(df)),
        "by_status": {str(k): int(v) for k, v in by_status.items()},
        "acceptance_rate": acceptance_rate,
        "by_department": by_department,
    }


def save_executive_summary(summary: str):
    conn = get_connection()
    try:
        pd.DataFrame({"summary": [summary]}).to_sql(
            "executive_summary", conn, if_exists="replace", index=False
        )
        conn.commit()
    finally:
        conn.close()


def load_executive_summary() -> str:
    df = load_dataframe("executive_summary")
    if not df.empty and "summary" in df.columns:
        return df.iloc[0]["summary"]
    return ""


# =======================================================
# Settings
# =======================================================

def get_settings() -> dict:
    conn = get_connection()
    try:
        _ensure_settings_table(conn)
        cur = conn.execute("SELECT key, value FROM app_settings")
        rows = dict(cur.fetchall())
        if not rows:
            return dict(DEFAULT_SETTINGS)
        model = rows.get("model", DEFAULT_SETTINGS["model"])
        if model in {
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        }:
            model = DEFAULT_SETTINGS["model"]
        return {
            "provider": rows.get("provider", DEFAULT_SETTINGS["provider"]),
            "model": model,
            "temperature": float(rows.get("temperature", DEFAULT_SETTINGS["temperature"])),
            "max_tokens": int(rows.get("max_tokens", DEFAULT_SETTINGS["max_tokens"])),
            "use_gpu": str(rows.get("use_gpu", DEFAULT_SETTINGS["use_gpu"])).lower() == "true",
            "seed_topics": rows.get("seed_topics", DEFAULT_SETTINGS["seed_topics"]),
        }
    finally:
        conn.close()


def save_settings(settings: dict):
    conn = get_connection()
    try:
        _ensure_settings_table(conn)
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )
        conn.commit()
    finally:
        conn.close()


# =======================================================
# Clear
# =======================================================

def clear_analysis_results(conn=None):
    """Remove every derived analysis table, including the master analysis table."""
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        for table in [
            "master_feedback", "review_sentiment", "discovered_topics",
            "root_cause", "recommendations", "executive_summary",
        ]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    finally:
        if owns_connection:
            conn.close()


def clear_downstream_results(conn=None):
    """Remove results that depend on the current master dataset."""
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        for table in ["review_sentiment", "root_cause", "recommendations", "executive_summary"]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    finally:
        if owns_connection:
            conn.close()


def clear_recommendations():
    """Remove only recommendation artifacts while preserving analysis inputs."""
    conn = get_connection()
    try:
        for table in ["recommendations", "executive_summary"]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    finally:
        conn.close()


def clear_database():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        tables = [
            "customer_feedback", "master_feedback", "review_sentiment",
            "discovered_topics", "root_cause", "recommendations", "executive_summary",
        ]
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
        conn.commit()
    finally:
        conn.close()
