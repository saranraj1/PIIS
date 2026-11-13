"""Lexical BM25 Okapi search engine with telecom tokenization."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Dict, List, Optional, Tuple

from piis.knowledge.models import KnowledgeChunk
from piis.retrieval.tokenizer import TelecomTokenizer


class BM25OkapiIndex:
    """Okapi BM25 index customized for telecom technical terminology."""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Optional[TelecomTokenizer] = None,
    ):
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer or TelecomTokenizer()

        self._chunks: Dict[str, KnowledgeChunk] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._avg_doc_len: float = 0.0
        self._doc_frequencies: Dict[str, int] = defaultdict(int)
        self._inverted_index: Dict[str, Dict[str, int]] = defaultdict(dict)  # term -> {chunk_id: tf}
        self._idf_cache: Dict[str, float] = {}
        self._total_chunks: int = 0

    @property
    def total_chunks(self) -> int:
        return self._total_chunks

    def build_index(self, chunks: List[KnowledgeChunk]) -> None:
        """Build in-memory inverted index over the provided knowledge chunks."""
        self._chunks.clear()
        self._doc_lengths.clear()
        self._doc_frequencies.clear()
        self._inverted_index.clear()
        self._idf_cache.clear()

        self._total_chunks = len(chunks)
        if self._total_chunks == 0:
            self._avg_doc_len = 0.0
            return

        total_len = 0
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            tokens = self.tokenizer.tokenize(chunk.content)
            doc_len = len(tokens)
            self._doc_lengths[chunk.chunk_id] = doc_len
            total_len += doc_len

            term_counts = Counter(tokens)
            for term, count in term_counts.items():
                self._inverted_index[term][chunk.chunk_id] = count
                self._doc_frequencies[term] += 1

        self._avg_doc_len = total_len / self._total_chunks

        # Precompute non-negative Robertson-Spärck Jones IDF
        for term, df in self._doc_frequencies.items():
            # Non-negative IDF formula
            idf = math.log(((self._total_chunks - df + 0.5) / (df + 0.5)) + 1.0)
            self._idf_cache[term] = max(0.0, idf)

    def query(self, query_text: str, top_k: int = 10) -> List[Tuple[KnowledgeChunk, float]]:
        """Search index and return ranked (chunk, score) tuples."""
        if self._total_chunks == 0:
            return []

        query_tokens = self.tokenizer.tokenize(query_text)
        if not query_tokens:
            return []

        scores: Dict[str, float] = defaultdict(float)

        for token in query_tokens:
            if token not in self._inverted_index:
                continue

            idf = self._idf_cache.get(token, 0.0)
            postings = self._inverted_index[token]

            for chunk_id, tf in postings.items():
                doc_len = self._doc_lengths.get(chunk_id, 1)
                norm_len = 1.0 - self.b + self.b * (doc_len / (self._avg_doc_len + 1e-9))
                tf_component = (tf * (self.k1 + 1.0)) / (tf + self.k1 * norm_len)
                scores[chunk_id] += idf * tf_component

        if not scores:
            return []

        # Sort descending by score, deterministic tie-breaking by chunk_id
        ranked = sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        results: List[Tuple[KnowledgeChunk, float]] = []
        for chunk_id, score in ranked[:top_k]:
            chunk = self._chunks[chunk_id]
            results.append((chunk, float(score)))

        return results

    def get_chunk(self, chunk_id: str) -> Optional[KnowledgeChunk]:
        """Retrieve chunk by ID."""
        return self._chunks.get(chunk_id)
