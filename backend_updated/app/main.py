"""
app/main.py

FastAPI entrypoint. Mounts every router; the actual business logic lives
in app/services and app/models, ported unchanged (algorithmically) from
the original Streamlit project — see each module's docstring for exactly
what changed and why (almost entirely: Streamlit UI calls -> HTTP
request/response or background jobs).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth_router,
    dataset_router,
    preprocessing_router,
    aspect_discovery_router,
    sentiment_router,
    rootcause_router,
    recommendation_router,
    report_router,
    settings_router,
    jobs_router,
)

app = FastAPI(title="AI Customer Feedback Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(dataset_router.router)
app.include_router(preprocessing_router.router)
app.include_router(aspect_discovery_router.router)
app.include_router(sentiment_router.router)
app.include_router(rootcause_router.router)
app.include_router(recommendation_router.router)
app.include_router(report_router.router)
app.include_router(settings_router.router)
app.include_router(jobs_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
