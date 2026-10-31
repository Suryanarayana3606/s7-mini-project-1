"""
app/routers/report_router.py

Adapted from pages/9_Report.py — aggregates data from every prior stage
into the executive summary view. Pure data aggregation, no ML calls, so
it runs synchronously.
"""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import db
from app.utils.exports import workbook_download

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("")
def get_report(user: str = Depends(get_current_user)):
    master_df = db.load_dataframe("master_feedback")

    if master_df.empty:
        return {"has_data": False}

    rootcause_df = db.load_rootcause()
    recommendation_df = db.load_recommendations()
    executive_summary = db.load_executive_summary()

    total_reviews = len(master_df)
    positive = negative = neutral = 0
    if "Sentiment" in master_df.columns:
        s = master_df["Sentiment"].astype(str).str.lower()
        positive = int((s == "positive").sum())
        negative = int((s == "negative").sum())
        neutral = int((s == "neutral").sum())

    total_aspects = len(rootcause_df)
    recommendations_count = len(recommendation_df)
    departments = int(recommendation_df["department"].nunique()) if not recommendation_df.empty else 0

    top_aspects = []
    if not rootcause_df.empty:
        top_aspects = (
            rootcause_df.sort_values("Negative Reviews", ascending=False)
            .head(10)[["Aspect", "Negative Reviews"]]
            .to_dict(orient="records")
        )

    top_root_causes = []
    if not rootcause_df.empty:
        counter = Counter()
        for causes in rootcause_df["Root Causes"]:
            if isinstance(causes, list):
                counter.update(causes)
        top_root_causes = [{"cause": c, "frequency": f} for c, f in counter.most_common(10)]

    priority_dist = []
    if not recommendation_df.empty:
        priority_dist = (
            recommendation_df["priority"].value_counts().rename_axis("priority").reset_index(name="count")
            .to_dict(orient="records")
        )

    top_recommendations = []
    if not recommendation_df.empty:
        cols = [c for c in ["aspect", "priority", "department", "recommendation"] if c in recommendation_df.columns]
        top_recommendations = recommendation_df[cols].head(5).to_dict(orient="records")

    highest_risk = "-"
    if not recommendation_df.empty:
        high_priority = recommendation_df[recommendation_df["priority"].astype(str).str.lower().isin(["critical", "high"])]
        if not high_priority.empty:
            highest_risk = high_priority.iloc[0]["aspect"]

    top_department = "-"
    if not recommendation_df.empty:
        top_department = recommendation_df["department"].value_counts().idxmax()

    best_improvement = "-"
    if not recommendation_df.empty and "expected_improvement" in recommendation_df.columns:
        best_improvement = recommendation_df["expected_improvement"].iloc[0]

    roadmap = []
    if not recommendation_df.empty:
        cols = [c for c in ["implementation_order", "aspect", "priority", "department"] if c in recommendation_df.columns]
        roadmap_df = recommendation_df[cols].copy()
        if "implementation_order" in roadmap_df.columns:
            roadmap_df = roadmap_df.sort_values("implementation_order")
        roadmap = roadmap_df.to_dict(orient="records")

    return {
        "has_data": True,
        "kpis": {
            "reviews": total_reviews,
            "aspects": total_aspects,
            "negative": negative,
            "recommendations": recommendations_count,
            "departments": departments,
        },
        "sentiment_distribution": {"positive": positive, "negative": negative, "neutral": neutral},
        "top_aspects": top_aspects,
        "top_root_causes": top_root_causes,
        "priority_distribution": priority_dist,
        "top_recommendations": top_recommendations,
        "insights": {
            "highest_risk": highest_risk,
            "top_department": top_department,
            "recommendations_count": recommendations_count,
            "best_improvement": best_improvement,
        },
        "roadmap": roadmap,
        "executive_summary": executive_summary,
    }


@router.get("/export")
def export_report(user: str = Depends(get_current_user)):
    master_df = db.load_dataframe("master_feedback")
    if master_df.empty:
        raise HTTPException(status_code=404, detail="No report data available.")
    return workbook_download(
        {
            "Sentiment": master_df,
            "Root Causes": db.load_rootcause(),
            "Recommendations": db.load_recommendations(),
        },
        "customer-feedback-report",
    )
