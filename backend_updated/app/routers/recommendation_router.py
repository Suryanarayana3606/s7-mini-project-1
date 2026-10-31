"""
app/routers/recommendation_router.py

Adapted from pages/8_Recommendation.py. Batched LLM calls (3 aspects per
call) can take a while depending on provider/model, so this runs as a
background job with per-batch progress, mirroring the original page's
progress bar.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.database import db
from app.jobs import job_manager

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

VALID_STATUSES = {"Pending", "Accepted", "Rejected", "Implemented"}


class StatusPayload(BaseModel):
    status: str
    reviewer_note: str = ""


def _run_recommendations(job):
    rootcause_df = db.load_rootcause()

    if rootcause_df.empty:
        raise ValueError("Complete Root Cause Analysis first.")

    db.clear_recommendations()
    from app.models.recommendation import RecommendationModel
    model = RecommendationModel()

    def progress_cb(current, total, aspects):
        job_manager.update_progress(job.id, current, total, f"Processing batch {current}/{total}: {aspects}")

    recommendations, summary = model.generate(rootcause_df, progress_callback=progress_cb)

    if recommendations is None:
        import pandas as pd
        recommendations = pd.DataFrame()

    if not recommendations.empty:
        db.save_recommendations(recommendations)
    db.save_executive_summary(summary)

    kpis = model.get_kpis(recommendations)
    priority_dist = model.priority_distribution(recommendations)
    dept_dist = model.department_distribution(recommendations)
    top_issues = model.top_issues(recommendations, n=10)

    return {
        "has_results": True,
        "kpis": kpis,
        "priority_distribution": priority_dist.rename(
            columns={"Priority": "priority", "Count": "count"}
        ).to_dict(orient="records"),
        "department_distribution": dept_dist.to_dict(orient="records"),
        "top_issues": top_issues.to_dict(orient="records"),
        "recommendations": recommendations.to_dict(orient="records"),
        "executive_summary": summary,
        "feedback_stats": db.get_recommendation_feedback_stats(),
    }


@router.post("/run")
def start_recommendations(user: str = Depends(get_current_user)):
    job = job_manager.run_in_background(_run_recommendations)
    return {"job_id": job.id}


@router.get("/results")
def get_results(user: str = Depends(get_current_user)):
    recommendations = db.load_recommendations()
    summary = db.load_executive_summary()

    if recommendations.empty:
        return {"has_results": False, "executive_summary": summary}

    from app.models.recommendation import RecommendationModel
    model = RecommendationModel()
    kpis = model.get_kpis(recommendations)
    priority_dist = model.priority_distribution(recommendations)
    dept_dist = model.department_distribution(recommendations)
    top_issues = model.top_issues(recommendations, n=10)

    return {
        "has_results": True,
        "kpis": kpis,
        "priority_distribution": priority_dist.rename(
            columns={"Priority": "priority", "Count": "count"}
        ).to_dict(orient="records"),
        "department_distribution": dept_dist.to_dict(orient="records"),
        "top_issues": top_issues.to_dict(orient="records"),
        "recommendations": recommendations.to_dict(orient="records"),
        "executive_summary": summary,
        "feedback_stats": db.get_recommendation_feedback_stats(),
    }


# =======================================================
# Reviewer Feedback Loop (Accept / Reject / Implement)
# =======================================================
#
# Lets a human reviewer record a decision on each AI-generated
# recommendation. This is what turns the page from "the AI suggested
# something" into a managed workflow with an auditable outcome — and
# the resulting acceptance-rate metric (see feedback_stats above) is a
# concrete, measurable signal of whether the AI's output is actually
# useful, broken down by department.

@router.patch("/{rec_id}/status")
def update_status(rec_id: str, payload: StatusPayload, user: str = Depends(get_current_user)):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )

    updated = db.update_recommendation_status(rec_id, payload.status, payload.reviewer_note)
    if not updated:
        raise HTTPException(status_code=404, detail="Recommendation not found.")

    return {"success": True, "feedback_stats": db.get_recommendation_feedback_stats()}


@router.get("/feedback-stats")
def feedback_stats(user: str = Depends(get_current_user)):
    return db.get_recommendation_feedback_stats()
