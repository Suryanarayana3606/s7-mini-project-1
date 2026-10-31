"""
app/routers/rootcause_router.py

Adapted from pages/6_Root_Cause.py. TF-IDF root cause extraction is fast
enough on typical dataset sizes to run as a background job mainly for
progress-bar parity with the original page (which reported per-aspect
progress), not because it strictly needs to be async.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import db
from app.jobs import job_manager
from app.models.rootcause import RootCauseAnalyzer
from app.utils.exports import dataframe_download

router = APIRouter(prefix="/api/rootcause", tags=["rootcause"])


def _run_rootcause(job):
    df = db.load_dataframe("master_feedback")

    required = ["Aspect", "Sentiment", "review"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Complete Aspect Discovery and Sentiment Analysis first.")

    analyzer = RootCauseAnalyzer()

    def progress_cb(current, total, aspect):
        job_manager.update_progress(job.id, current, total, f"Processing aspect: {aspect}")

    rootcause_df = analyzer.analyze(df, progress_callback=progress_cb)

    db.clear_downstream_results()
    db.save_rootcause(rootcause_df)

    if rootcause_df.empty:
        return {"has_results": False}

    summary = analyzer.summary(rootcause_df)
    top_causes = analyzer.top_root_causes(rootcause_df)
    treemap = analyzer.treemap_data(rootcause_df)
    bar = analyzer.bar_chart_data(rootcause_df)

    export_df = rootcause_df.copy()
    export_df["Root Causes"] = export_df["Root Causes"].apply(lambda x: x if isinstance(x, list) else [])

    return {
        "has_results": True,
        "summary": summary,
        "table": export_df.to_dict(orient="records"),
        "top_causes": top_causes.to_dict(orient="records"),
        "treemap": treemap.to_dict(orient="records"),
        "bar_chart": bar.to_dict(orient="records"),
    }


@router.post("/run")
def start_rootcause(user: str = Depends(get_current_user)):
    job = job_manager.run_in_background(_run_rootcause)
    return {"job_id": job.id}


@router.get("/results")
def get_results(user: str = Depends(get_current_user)):
    rootcause_df = db.load_rootcause()
    if rootcause_df.empty:
        return {"has_results": False}

    analyzer = RootCauseAnalyzer()
    summary = analyzer.summary(rootcause_df)
    top_causes = analyzer.top_root_causes(rootcause_df)
    treemap = analyzer.treemap_data(rootcause_df)
    bar = analyzer.bar_chart_data(rootcause_df)

    return {
        "has_results": True,
        "summary": summary,
        "table": rootcause_df.to_dict(orient="records"),
        "top_causes": top_causes.to_dict(orient="records"),
        "treemap": treemap.to_dict(orient="records"),
        "bar_chart": bar.to_dict(orient="records"),
    }


@router.get("/export")
def export_rootcause(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    user: str = Depends(get_current_user),
):
    df = db.load_rootcause()
    if df.empty:
        raise HTTPException(status_code=404, detail="No root cause results available.")
    return dataframe_download(df, "root-cause-analysis", format)
