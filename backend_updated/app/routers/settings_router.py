"""
app/routers/settings_router.py

Adapted from pages/7_settings.py. Settings now live in SQLite (see
app/database/db.py) instead of a local JSON file, so they're consistent
across server restarts and (if ever needed) multiple workers.
"""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.auth import get_current_user
from app.config import DEFAULT_SETTINGS
from app.database import db
from app.services.llm.factory import LLMFactory

router = APIRouter(prefix="/api/settings", tags=["settings"])

MODEL_OPTIONS = {
    "Groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"],
    "Ollama": ["llama3.1:8b"],
}


class SettingsPayload(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    use_gpu: bool = True
    seed_topics: str = ""

    @field_validator("seed_topics")
    @classmethod
    def validate_seed_topics(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        try:
            topics = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Seed topics must be valid JSON.") from exc
        if not isinstance(topics, list) or any(
            not isinstance(group, list)
            or not group
            or any(not isinstance(word, str) or not word.strip() for word in group)
            for group in topics
        ):
            raise ValueError("Seed topics must be a JSON list of non-empty keyword lists.")
        return json.dumps([[word.strip() for word in group] for group in topics])

@router.get("")
def get_settings_route(user: str = Depends(get_current_user)):
    return {"settings": db.get_settings(), "model_options": MODEL_OPTIONS}


@router.post("")
def save_settings_route(payload: SettingsPayload, user: str = Depends(get_current_user)):
    db.save_settings(payload.dict())
    return {"success": True, "settings": payload.dict()}


@router.post("/reset")
def reset_settings_route(user: str = Depends(get_current_user)):
    db.save_settings(DEFAULT_SETTINGS)
    return {"success": True, "settings": DEFAULT_SETTINGS}


@router.post("/test")
def test_connection(payload: SettingsPayload, user: str = Depends(get_current_user)):
    try:
        llm = LLMFactory.get_provider(
            provider=payload.provider,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        response = llm.generate("Reply only with OK.")
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}
