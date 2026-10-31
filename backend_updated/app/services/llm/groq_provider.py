"""
app/services/llm/groq_provider.py

Groq LLM Provider — unchanged logic from the original, only the config
import path is updated (app.config instead of top-level config).
"""

from app.config import GROQ_API_KEY
from app.services.llm.base import BaseLLM


class GroqProvider(BaseLLM):

    def __init__(
        self,
        model="openai/gpt-oss-120b",
        temperature=0.2,
        max_tokens=1500,
        max_retries=2,
    ):
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("Groq SDK is not installed. Run: pip install groq") from exc
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        self.client = Groq(api_key=GROQ_API_KEY, max_retries=max_retries)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_completion_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
