"""
app/services/llm/factory.py

LLM Factory — unchanged logic, updated import paths only.
"""

from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.groq_provider import GroqProvider


class LLMFactory:

    @staticmethod
    def get_provider(
        provider="Groq",
        model=None,
        temperature=0.2,
        max_tokens=1500,
        max_retries=2,
    ):
        provider = provider.lower()

        if provider == "groq":
            return GroqProvider(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
        elif provider == "ollama":
            return OllamaProvider(model=model, temperature=temperature, max_tokens=max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
