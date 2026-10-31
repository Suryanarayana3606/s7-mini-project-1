"""
app/routers/aspect_discovery_router.py

Adapted from pages/4_Aspect_Discovery.py. BERTopic fitting is the single
slowest step in the whole pipeline (embedding + UMAP + HDBSCAN), so it
always runs as a background job even though the original Streamlit page
ran it synchronously behind st.spinner — a blocking HTTP request that
takes 30+ seconds on a larger dataset is a bad idea for a browser client
(timeouts, no visible progress), whereas polling a job id works cleanly.
"""

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import db
from app.jobs import job_manager

router = APIRouter(prefix="/api/aspect-discovery", tags=["aspect-discovery"])


def _run_discovery(job):
    df = db.load_dataframe("customer_feedback")

    if df.empty or "clean_review" not in df.columns:
        raise ValueError("Run preprocessing before Aspect Discovery.")

    usable = df["clean_review"].fillna("").astype(str).str.strip()
    if "review" in df.columns:
        fallback = df["review"].fillna("").astype(str).str.strip()
        usable = usable.mask(usable.eq(""), fallback)
    if usable.eq("").all():
        raise ValueError("No usable review text remains after preprocessing.")

    job_manager.update_progress(job.id, 0, 1, "Embedding reviews, fitting BERTopic, and labeling aspects...")

    from app.models.aspect_discovery import AspectDiscovery
    engine = AspectDiscovery()
    result = engine.run(df)

    topic_df = result["topic_info"][["Topic", "Count", "Raw Aspect", "Aspect"]].copy()
    topic_df["Topic"] = topic_df["Topic"].astype(int)
    topic_df["Count"] = topic_df["Count"].astype(int)

    db.clear_analysis_results()
    db.save_topics(topic_df)
    db.save_master_dataset(result["master_df"])

    total_topics = int((topic_df["Topic"] != -1).sum())
    largest_topic = int(topic_df["Count"].max()) if not topic_df.empty else 0
    noise_row = topic_df.loc[topic_df["Topic"] == -1, "Count"]
    noise = int(noise_row.iloc[0]) if not noise_row.empty else 0

    return {
        "topics": topic_df.to_dict(orient="records"),
        "summary": {
            "total_topics": total_topics,
            "largest_topic": largest_topic,
            "reviews": len(df),
            "noise_reviews": noise,
        },
    }


@router.post("/run")
def start_discovery(user: str = Depends(get_current_user)):
    job = job_manager.run_in_background(_run_discovery)
    return {"job_id": job.id}


@router.get("/results")
def get_results(user: str = Depends(get_current_user)):
    topic_df = db.load_dataframe("discovered_topics")
    if topic_df.empty:
        return {"has_results": False}

    topic_df["Topic"] = topic_df["Topic"].astype(int)
    topic_df["Count"] = topic_df["Count"].astype(int)

    return {
        "has_results": True,
        "topics": topic_df.to_dict(orient="records"),
    }
