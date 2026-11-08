"""Local narrative similarity: lexical TF-IDF or explicitly configured embeddings.

Only narratives enter this channel, never diagnoses, interventions or outcomes.
The lexical default is not a semantic embedding model. The optional semantic
backend loads an already downloaded model; requests never download model weights.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

STOP_WORDS = frozenset("a an and are as at be by for from in is it of on or that the this to was were with".split())


def _terms(text: str) -> Counter:
    return Counter(t for t in re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE)
                   if t not in STOP_WORDS)


@lru_cache(maxsize=16)
def _index(documents: tuple[str, ...]) -> tuple[dict, tuple[dict, ...]]:
    counts = [_terms(d) for d in documents]
    frequency = Counter(term for c in counts for term in c)
    idf = {t: math.log((1 + len(documents)) / (1 + n)) + 1 for t, n in frequency.items()}
    return idf, tuple(_vector(c, idf) for c in counts)


def _vector(counts: Counter, idf: dict) -> dict:
    weighted = {t: (1 + math.log(n)) * idf[t] for t, n in counts.items() if t in idf}
    norm = math.sqrt(sum(v * v for v in weighted.values()))
    return {t: v / norm for t, v in weighted.items()} if norm else {}


def lexical_scores(query: str, documents: list[str]) -> list[float]:
    """Cosine over corpus-fitted TF-IDF vectors; no model, credentials or network."""
    idf, vectors = _index(tuple(documents))
    q = _vector(_terms(query), idf)
    return [max(0.0, min(1.0, sum(v * d.get(t, 0) for t, v in q.items()))) for d in vectors]


class SemanticScores:
    """SentenceTransformer cosine scorer with a bounded, content-keyed cache."""

    def __init__(self, model_path: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Semantic retrieval needs requirements-embeddings.txt.") from exc
        self.model = SentenceTransformer(model_path, local_files_only=True, trust_remote_code=False)
        self._encode = lru_cache(maxsize=512)(self._encode_one)

    def _encode_one(self, text: str) -> tuple[float, ...]:
        vector = tuple(float(x) for x in self.model.encode(text, normalize_embeddings=True))
        if not vector or not all(math.isfinite(x) for x in vector):
            raise ValueError("Embedding model returned an empty or non-finite vector.")
        return vector

    def __call__(self, query: str, documents: list[str]) -> list[float]:
        if not query.strip():
            return [0.0] * len(documents)
        q = self._encode(query)
        scores = []
        for document in documents:
            if not document.strip():
                scores.append(0.0)
                continue
            d = self._encode(document)
            if len(q) != len(d):
                raise ValueError("Embedding dimensions differ between query and case.")
            scores.append(max(0.0, min(1.0, sum(a * b for a, b in zip(q, d)))))
        return scores
