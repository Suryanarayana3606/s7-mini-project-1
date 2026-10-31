"""
services/llm/ollama_provider.py

Ollama LLM Provider
"""

from app.services.llm.base import BaseLLM


class OllamaProvider(BaseLLM):

    def __init__(
        self,
        model="llama3.1:8b",
        temperature=0.2,
        max_tokens=1500
    ):

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:

        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError("Ollama Python SDK is not installed. Run: pip install ollama") from exc

        response = ollama.chat(

            model=self.model,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            options={

                "temperature": self.temperature,

                "num_predict": self.max_tokens

            }

        )

        return response["message"]["content"]