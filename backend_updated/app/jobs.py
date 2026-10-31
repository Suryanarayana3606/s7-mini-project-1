"""
app/jobs.py

Replaces Streamlit's synchronous st.progress()/st.spinner() pattern.

In the Streamlit app, a long-running task (BERTopic fit, ABSA inference
over thousands of rows, batched LLM calls) blocked the single script
thread and updated a progress bar in place. A REST API can't do that —
the frontend needs to POST to start the task, get an id back immediately,
and poll for status. This is a deliberately simple in-memory job store;
it's sufficient for a single-server academic/demo deployment. For a real
multi-worker production deployment you'd swap this for Redis/Celery
without changing the router code that calls it.
"""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending | running | done | error
    current: int = 0
    total: int = 0
    message: str = ""
    result: Any = None
    error: Optional[str] = None


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=str(uuid.uuid4()))
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_progress(self, job_id: str, current: int, total: int, message: str = ""):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
                job.current = current
                job.total = total
                if message:
                    job.message = message

    def complete(self, job_id: str, result: Any):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.result = result
                job.current = job.total or job.current

    def fail(self, job_id: str, error: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "error"
                job.error = error

    def run_in_background(self, fn: Callable[[Job], Any]):
        """Creates a job and runs `fn(job)` on a background thread. Returns the job id immediately."""
        job = self.create()

        def _runner():
            try:
                job.status = "running"
                result = fn(job)
                self.complete(job.id, result)
            except Exception as e:  # noqa: BLE001 — surface any failure to the poller
                self.fail(job.id, str(e))

        threading.Thread(target=_runner, daemon=True).start()
        return job


job_manager = JobManager()
