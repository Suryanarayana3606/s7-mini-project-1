"""
app/routers/sentiment_router.py

Adapted from pages/5_Aspect_Sentiment.py. Runs as a background job with
real progress reporting (batch-by-batch), same granularity the original
Streamlit progress bar had.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import db
from app.jobs import job_manager
from app.utils.exports import dataframe_download

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


def _run_sentiment(job):
    df = db.load_dataframe("master_feedback")

    if df.empty:
        raise ValueError("Run Aspect Discovery first.")

    aspect_column = "Aspect" if "Aspect" in df.columns else ("Topic" if "Topic" in df.columns else None)
    if aspect_column is None:
        raise ValueError("Aspect information not found. Run Aspect Discovery first.")

    from app.models.sentiment import SentimentAnalyzer
    analyzer = SentimentAnalyzer()

    def progress_cb(current, total):
        job_manager.update_progress(job.id, current, total, f"Analyzing aspect sentiment... {current}/{total}")

    result_df = analyzer.analyze_dataframe(
        df=df,
        text_column="review",
        aspect_column=aspect_column,
        batch_size=None,  # SentimentService picks 64 on GPU / 16 on CPU automatically
        progress_callback=progress_cb,
    )

    db.clear_downstream_results()
    db.save_dataframe(result_df, table_name="master_feedback")

    summary = analyzer.sentiment_summary(result_df)
    avg_confidence = analyzer.average_confidence(result_df)

    return {
        "summary": summary,
        "average_confidence": avg_confidence,
        "rows": len(result_df),
    }


@router.post("/run")
def start_sentiment(user: str = Depends(get_current_user)):
    job = job_manager.run_in_background(_run_sentiment)
    return {"job_id": job.id}


@router.get("/results")
def get_results(user: str = Depends(get_current_user)):
    df = db.load_dataframe("master_feedback")
    if df.empty or "Sentiment" not in df.columns:
        return {"has_results": False}

    aspect_column = "Aspect" if "Aspect" in df.columns else "Topic"

    sentiment_counts = df["Sentiment"].value_counts().to_dict()
    by_aspect = (
        df.groupby([aspect_column, "Sentiment"]).size().reset_index(name="count").to_dict(orient="records")
    )
    confidence_by_aspect = (
        df.groupby(aspect_column)["Confidence"].mean().round(2).reset_index().to_dict(orient="records")
    )

    display_cols = [c for c in ["review", "clean_review", aspect_column, "Sentiment", "Confidence"] if c in df.columns]

    return {
        "has_results": True,
        "sentiment_counts": sentiment_counts,
        "average_confidence": round(float(df["Confidence"].mean()), 2),
        "by_aspect": by_aspect,
        "confidence_by_aspect": confidence_by_aspect,
        "rows": df[display_cols].fillna("").to_dict(orient="records"),
    }


@router.get("/export")
def export_sentiment(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    user: str = Depends(get_current_user),
):
    df = db.load_dataframe("master_feedback")
    if df.empty or "Sentiment" not in df.columns:
        raise HTTPException(status_code=404, detail="No sentiment results available.")
    return dataframe_download(df, "sentiment-analysis", format)
