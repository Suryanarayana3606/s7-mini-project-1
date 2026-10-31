"""
app/services/sentiment_service.py

Aspect-Based Sentiment Analysis Service — dedicated ABSA transformer
model (yangheng/deberta-v3-base-absa-v1.1). Adapted from the Streamlit
project's services/sentiment_service.py: `@st.cache_resource` is replaced
with a plain module-level lazy singleton (functools.lru_cache), same
reasoning as embedding_service.py. Model architecture and inference logic
are otherwise byte-for-byte identical to the original.
"""

from functools import lru_cache
from typing import List, Dict

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from app.database.db import get_settings

MODEL_NAME = "yangheng/deberta-v3-base-absa-v1.1"


@lru_cache(maxsize=2)
def load_absa_model(use_gpu: bool = True):
    device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.to(device)
    model.eval()
    return tokenizer, model, device


class SentimentService:

    def __init__(self):
        self.use_gpu = get_settings().get("use_gpu", True)
        self.tokenizer, self.model, self.device = load_absa_model(self.use_gpu)
        self.label_map = {0: "negative", 1: "neutral", 2: "positive"}
        # Bigger batches use a GPU far more efficiently at 100k+ rows;
        # on CPU-only machines (e.g. a college lab PC with no GPU) a
        # smaller batch avoids memory spikes and keeps latency per batch
        # reasonable. Both paths still work correctly either way — this
        # only affects throughput.
        self.default_batch_size = 64 if self.device.type == "cuda" else 16

    def predict_aspect(self, text: str, aspect: str) -> Dict:
        if not text or not aspect:
            return {"label": "neutral", "confidence": 0.0}

        text = str(text)
        aspect = str(aspect)

        inputs = self.tokenizer(text, aspect, return_tensors="pt", truncation=True, max_length=512)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)[0]

        predicted_id = int(torch.argmax(probabilities))
        confidence = float(probabilities[predicted_id])

        return {
            "label": self.label_map.get(predicted_id, "neutral"),
            "confidence": round(confidence * 100, 2),
        }

    def predict_aspects_batch(
        self, texts: List[str], aspects: List[str], batch_size: int | None = None
    ) -> List[Dict]:
        batch_size = batch_size or self.default_batch_size
        predictions = []

        for start in range(0, len(texts), batch_size):
            text_batch = texts[start:start + batch_size]
            aspect_batch = aspects[start:start + batch_size]

            inputs = self.tokenizer(
                text_batch, aspect_batch, return_tensors="pt",
                padding=True, truncation=True, max_length=512,
            )
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=-1)

            predicted_ids = torch.argmax(probabilities, dim=-1)

            for index, predicted_id in enumerate(predicted_ids):
                predicted_id = int(predicted_id)
                confidence = float(probabilities[index, predicted_id])
                predictions.append({
                    "label": self.label_map.get(predicted_id, "neutral"),
                    "confidence": round(confidence * 100, 2),
                })

        return predictions
