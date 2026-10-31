"""
app/services/embedding_service.py

Sentence embedding generation for Aspect Discovery (BERTopic input).

Scaling changes from the original version:
1. Device-aware: uses GPU when available (laptop), falls back cleanly to
   CPU (college lab machines) without the caller needing to know which.
   Respects the same `use_gpu` setting the ABSA sentiment model uses, so
   there's one on/off switch for the whole app rather than two.
2. Batched encoding with a configurable batch_size instead of the
   sentence-transformers default (32) — larger batches use the GPU more
   efficiently and cut wall-clock time substantially on 100k+ documents.
3. Persistent embedding cache (SQLite-backed): each review's embedding is
   stored keyed by a hash of its cleaned text. When new data is appended
   later (the stated 100k+ growth case), only *new* text gets embedded —
   previously-seen reviews are served from cache instantly. This is the
   single biggest recurring cost saver as the dataset grows incrementally
   rather than being uploaded once.
"""

import hashlib
import sqlite3
from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import DB_PATH
from app.database.db import get_settings

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size


@lru_cache(maxsize=1)
def _load_embedding_model(device: str) -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)


def _resolve_device(use_gpu: bool) -> str:
    return "cuda" if use_gpu and torch.cuda.is_available() else "cpu"


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Tiny key-value cache for embeddings, stored alongside the app's
    existing SQLite database so no extra infra is needed. Safe to skip
    (pass use_cache=False) for one-off experimentation."""

    def __init__(self):
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS embedding_cache ("
            "text_hash TEXT PRIMARY KEY, model_name TEXT, vector BLOB)"
        )
        self._conn.commit()

    def get_many(self, texts: list[str]) -> dict[str, np.ndarray]:
        hashes = [_text_hash(t) for t in texts]
        found: dict[str, np.ndarray] = {}
        # SQLite has a default limit of 999 bound variables per query.
        for start in range(0, len(hashes), 900):
            chunk = hashes[start:start + 900]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT text_hash, vector FROM embedding_cache "
                f"WHERE model_name = ? AND text_hash IN ({placeholders})",
                (EMBEDDING_MODEL_NAME, *chunk),
            ).fetchall()
            for text_hash, blob in rows:
                found[text_hash] = np.frombuffer(blob, dtype=np.float32)
        return found

    def put_many(self, texts: list[str], vectors: np.ndarray):
        rows = [
            (_text_hash(t), EMBEDDING_MODEL_NAME, np.asarray(v, dtype=np.float32).tobytes())
            for t, v in zip(texts, vectors)
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache (text_hash, model_name, vector) VALUES (?, ?, ?)",
            rows,
        )
        self._conn.commit()


class EmbeddingService:

    def __init__(self):
        settings = get_settings()
        self.use_gpu = settings.get("use_gpu", True)
        self.device = _resolve_device(self.use_gpu)
        self.model = _load_embedding_model(self.device)
        self.batch_size = 256 if self.device == "cuda" else 64
        self.cache = EmbeddingCache()

    def generate_embeddings(self, documents: list[str], use_cache: bool = True, progress_callback=None) -> np.ndarray:
        if not documents:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

        n = len(documents)

        if not use_cache:
            return self.model.encode(
                documents, batch_size=self.batch_size, show_progress_bar=False, convert_to_numpy=True
            )

        cached = self.cache.get_many(documents)
        result = np.empty((n, EMBEDDING_DIM), dtype=np.float32)

        to_encode_idx = []
        to_encode_text = []
        for i, doc in enumerate(documents):
            h = _text_hash(doc)
            if h in cached:
                result[i] = cached[h]
            else:
                to_encode_idx.append(i)
                to_encode_text.append(doc)

        if to_encode_text:
            new_vectors = self.model.encode(
                to_encode_text, batch_size=self.batch_size, show_progress_bar=False, convert_to_numpy=True
            )
            for pos, i in enumerate(to_encode_idx):
                result[i] = new_vectors[pos]
            self.cache.put_many(to_encode_text, new_vectors)

        if progress_callback:
            progress_callback(n, n, cache_hits=n - len(to_encode_text), cache_misses=len(to_encode_text))

        return result
