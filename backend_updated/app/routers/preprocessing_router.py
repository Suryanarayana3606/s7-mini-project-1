"""
app/routers/preprocessing_router.py

Adapted from pages/3_Preprocessing.py. Text cleaning now runs as a
background job (like aspect discovery / sentiment) instead of blocking
the request. It was fast enough to run synchronously at demo-dataset
sizes, but at 100k+ rows even the batched spaCy pipeline (see
preprocessing/processor.py) takes long enough that a browser request
would time out with no visible progress. Kept as a small, focused change
so /run's response shape for existing small-dataset callers doesn't
silently disappear — the frontend polls the job the same way it already
does for aspect discovery and sentiment.
"""

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import db
from app.jobs import job_manager
from app.preprocessing.processor import ReviewProcessor

router = APIRouter(prefix="/api/preprocessing", tags=["preprocessing"])


def _run_preprocessing(job):
    df = db.load_dataframe("customer_feedback")
    if df.empty:
        raise ValueError("No dataset uploaded yet.")

    if "review" not in df.columns:
        raise ValueError("Standardized 'review' column not found.")

    processor = ReviewProcessor()

    def progress_cb(current, total):
        job_manager.update_progress(job.id, current, total, f"Cleaning reviews... {current}/{total}")

    df = processor.preprocess_dataframe(df, text_column="review", progress_callback=progress_cb)

    if not df["clean_review"].astype(str).str.strip().any():
        raise ValueError("Preprocessing produced no usable review text.")

    # Preprocessing changes the source used by every downstream stage.
    db.clear_analysis_results()
    db.save_dataframe(df, table_name="customer_feedback")

    sample = df[["review", "clean_review"]].head(10).fillna("").to_dict(orient="records")

    return {"success": True, "rows": len(df), "sample": sample}


@router.post("/run")
def run_preprocessing(user: str = Depends(get_current_user)):
    job = job_manager.run_in_background(_run_preprocessing)
    return {"job_id": job.id}


@router.get("/status")
def preprocessing_status(user: str = Depends(get_current_user)):
    df = db.load_dataframe("customer_feedback")
    is_preprocessed = "clean_review" in df.columns if not df.empty else False
    sample = []
    if is_preprocessed and "review" in df.columns:
        sample = df[["review", "clean_review"]].head(10).fillna("").to_dict(orient="records")
    return {
        "has_dataset": not df.empty,
        "is_preprocessed": is_preprocessed,
        "row_count": len(df),
        "sample": sample,
    }
