from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.jobs import job_manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job_status(job_id: str, user: str = Depends(get_current_user)):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": job.id,
        "status": job.status,
        "current": job.current,
        "total": job.total,
        "message": job.message,
        "result": job.result if job.status == "done" else None,
        "error": job.error,
    }
