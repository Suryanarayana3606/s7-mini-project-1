"""
app/config.py

Application configuration. Adapted from the original Streamlit project's
config.py — same environment variables and defaults, just with the
Streamlit-specific settings persistence removed (settings are now stored
in the SQLite database instead of a local JSON file, since a FastAPI
server may run multiple worker processes that shouldn't each keep their
own local file).
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "AI Customer Feedback Intelligence"

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "customer_feedback.db"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Demo credentials — same as the original Streamlit app. See SECURITY.md
# in the repo root for how to replace this with real auth before any
# real deployment.
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-use-a-32-byte-secret")

DEFAULT_SETTINGS = {
    "provider": "Groq",
    "model": "openai/gpt-oss-120b",
    "temperature": 0.2,
    "max_tokens": 1500,
    "use_gpu": True,
    # Auto-detect non-English reviews on upload and translate a working
    # copy to English before the NLP pipeline runs (original text is
    # always preserved separately). Turn off in air-gapped/offline
    # environments where the translation API has no network access.
    # Optional JSON list of keyword lists, e.g.
        # '[["login","password"],["crash","freeze"]]' — steers
    # BERTopic toward known product aspects instead of pure unsupervised
    # clustering. Leave unset/empty for fully unsupervised discovery.
    "seed_topics": "",
}
