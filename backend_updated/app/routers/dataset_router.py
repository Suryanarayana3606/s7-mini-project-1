"""
app/routers/dataset_router.py

Adapted from pages/2_Upload.py and pages/1_Dashboard.py. The column
auto-detection heuristic, validation, and cleaning steps are the exact
same logic as the original Streamlit page — just triggered by an HTTP
request/response cycle instead of a file_uploader widget + button click.
"""

import io

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.auth import get_current_user
from app.database import db
from app.utils.data_validation import clean_dataset, has_usable_review, validate_dataset

router = APIRouter(prefix="/api/dataset", tags=["dataset"])

PREFERRED_COLUMN_NAMES = [
    "review", "reviews", "feedback", "customer_feedback", "review_text",
    "feedback_text", "customer_review", "customer_reviews", "comment",
    "comments", "remarks", "description", "complaint", "text",
]

PARTIAL_MATCH_KEYWORDS = ["review", "feedback", "comment", "remark", "complaint"]


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    """Read common CSV encodings without making users manually convert files."""
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_error = exc
    raise ValueError(f"Unsupported or malformed CSV encoding: {last_error}")


def _normalize(col: str) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def detect_review_column(df: pd.DataFrame):
    normalized_columns = {_normalize(c): c for c in df.columns}

    for name in PREFERRED_COLUMN_NAMES:
        if name in normalized_columns:
            return normalized_columns[name]

    possible = [c for c in df.columns if any(k in _normalize(c) for k in PARTIAL_MATCH_KEYWORDS)]
    if len(possible) == 1:
        return possible[0]

    return None


@router.post("/preview")
async def preview_dataset(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    """Parses the CSV and returns a preview + detected review column, without saving anything yet."""
    raw = await file.read()
    try:
        df = _read_csv_bytes(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read CSV file: {e}")

    detected = detect_review_column(df)

    return {
        "columns": list(df.columns),
        "detected_review_column": detected,
        "preview": df.head(10).fillna("").to_dict(orient="records"),
        "row_count": len(df),
    }


@router.post("/confirm")
async def confirm_and_save(
    file: UploadFile = File(...),
    review_column: str = None,
    user: str = Depends(get_current_user),
):
    """Standardizes the chosen review column, validates, cleans, and persists — same pipeline as the Upload page's Save button."""
    raw = await file.read()
    try:
        df = _read_csv_bytes(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read CSV file: {e}")

    if not review_column or review_column not in df.columns:
        raise HTTPException(status_code=400, detail="A valid review_column must be provided.")

    if review_column != "review":
        if "review" in df.columns:
            df = df.drop(columns=["review"])
        df["review"] = df[review_column].fillna("").astype(str).str.strip()
    else:
        df["review"] = df["review"].fillna("").astype(str).str.strip()

    before = len(df)
    df = df[df["review"].map(has_usable_review)].copy()
    removed_empty = before - len(df)

    errors = validate_dataset(df)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    df, duplicates_removed, missing_filled = clean_dataset(df)

    # A new upload invalidates every derived analysis result. Keeping old
    # master/topics/recommendations would make later pages show stale data.
    db.clear_analysis_results()
    db.save_dataframe(df, table_name="customer_feedback")

    return {
        "success": True,
        "rows": len(df),
        "columns": len(df.columns),
        "removed_empty_reviews": removed_empty,
        "duplicates_removed": duplicates_removed,
        "missing_values_filled": missing_filled,
        "preview": df.head(10).fillna("").to_dict(orient="records"),
    }


@router.get("/dashboard")
def dashboard(user: str = Depends(get_current_user)):
    df = db.load_dataframe("customer_feedback")
    if df.empty:
        return {"has_data": False}

    return {
        "has_data": True,
        "total_reviews": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "preview": df.head(10).fillna("").to_dict(orient="records"),
    }


@router.delete("")
def clear_all(user: str = Depends(get_current_user)):
    db.clear_database()
    return {"success": True}
