"""Dense bi-encoder vector search index with configurable model and local fallback."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from piis.knowledge.models import KnowledgeChunk


class DenseBiEncoderIndex:
    """Local vector index computing dense semantic embeddings and cosine similarity."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        dimension: int = 384,
        force_local_fallback: bool = False,
    ):
        self.model_name = model_name
        self.dimension = dimension
        self.force_local_fallback = force_local_fallback

        self._model: Any = None
        self._fallback_vectorizer: Any = None
        self._chunks: Dict[str, KnowledgeChunk] = {}
        self._chunk_ids: List[str] = []
        self._embeddings: Optional[np.ndarray] = None
        self._index_fingerprint: str = ""
        self._is_fallback_mode: bool = False

        self._init_encoder()

    def _init_encoder(self) -> None:
        """Initialize SentenceTransformer if available, or initialize local deterministic fallback."""
        if self.force_local_fallback:
            self._setup_local_fallback()
            return

        try:
            # Set USE_TF=0 to prevent Keras 3 conflict with Transformers
            # Set offline flags to prevent hanging on network timeouts in air-gapped/offline environments
            os.environ["USE_TF"] = "0"
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from sentence_transformers import SentenceTransformer
            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self.model_name)
            self._is_fallback_mode = False
        except Exception:
            # Fall back cleanly to deterministic local vectorizer
            self._setup_local_fallback()

    def _setup_local_fallback(self) -> None:
        """Set up local deterministic word-level TF-IDF projection as embedding baseline."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._fallback_vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            stop_words="english",
            max_features=self.dimension,
            norm="l2",
        )
        self._is_fallback_mode = True

    @property
    def is_fallback_mode(self) -> bool:
        return self._is_fallback_mode

    @property
    def index_fingerprint(self) -> str:
        return self._index_fingerprint

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode text strings into L2-normalized dense embeddings."""
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        if not self._is_fallback_mode and self._model is not None:
            try:
                embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return np.array(embeddings, dtype=np.float32)
            except Exception:
                # If model runtime fails, use fallback
                self._setup_local_fallback()

        # Local deterministic fallback
        if self._fallback_vectorizer is not None:
            try:
                # Check if vectorizer is already fitted
                mat = self._fallback_vectorizer.transform(texts).toarray()
            except Exception:
                mat = self._fallback_vectorizer.fit_transform(texts).toarray()

            # Ensure exact dimension
            if mat.shape[1] < self.dimension:
                pad = np.zeros((mat.shape[0], self.dimension - mat.shape[1]), dtype=np.float32)
                mat = np.hstack([mat, pad])
            elif mat.shape[1] > self.dimension:
                mat = mat[:, :self.dimension]

            # Re-normalize L2
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return (mat / norms).astype(np.float32)

        return np.zeros((len(texts), self.dimension), dtype=np.float32)

    def build_index(self, chunks: List[KnowledgeChunk]) -> None:
        """Compute embeddings for all chunks and build dense index."""
        self._chunks.clear()
        self._chunk_ids.clear()
        self._embeddings = None

        if not chunks:
            self._index_fingerprint = ""
            return

        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            self._chunk_ids.append(chunk.chunk_id)

        texts = [chunk.content for chunk in chunks]

        # Fit fallback vectorizer on the corpus if in fallback mode
        if self._is_fallback_mode and self._fallback_vectorizer is not None:
            self._fallback_vectorizer.fit(texts)

        self._embeddings = self.encode(texts)

        # Compute deterministic SHA-256 index fingerprint
        hasher = hashlib.sha256()
        hasher.update(self.model_name.encode())
        hasher.update(str(self.dimension).encode())
        hasher.update(self._embeddings.tobytes())
        self._index_fingerprint = hasher.hexdigest()

    def query(self, query_text: str, top_k: int = 10) -> List[Tuple[KnowledgeChunk, float]]:
        """Search dense vector index using cosine similarity."""
        if self._embeddings is None or len(self._chunk_ids) == 0:
            return []

        q_vec = self.encode([query_text])[0]  # shape: (dimension,)
        # Dot product with normalized chunk embeddings equals cosine similarity
        similarities = np.dot(self._embeddings, q_vec)

        # Truncate negative/orthogonal noise to 0.0
        scores = np.maximum(0.0, similarities)

        ranked_indices = np.argsort(-scores)[:top_k]

        results: List[Tuple[KnowledgeChunk, float]] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score <= 0.05:
                continue
            chunk_id = self._chunk_ids[idx]
            chunk = self._chunks[chunk_id]
            results.append((chunk, score))

        return results

    def get_metadata(self) -> Dict[str, Any]:
        """Return index configuration metadata for index cards and audit."""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "total_vectors": len(self._chunk_ids),
            "is_fallback_mode": self._is_fallback_mode,
            "index_fingerprint": self._index_fingerprint,
        }
