"""Busca vetorial esparsa: TF-IDF + similaridade de cosseno, em Python puro.

Escolha deliberada para o portfólio: roda sem GPU, sem API key e de forma
determinística (testável no CI). A interface `Retriever` permite trocar por
embeddings densos (pgvector, Chroma, OpenAI/Voyage embeddings) sem mudar o agente.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from app.rag.knowledge_base import Chunk
from app.rag.text import tokenize

Vector = dict[str, float]


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float  # similaridade de cosseno (0 a 1)
    coverage: float  # fração dos termos da pergunta presentes no chunk (0 a 1)


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[SearchResult]: ...


class TfidfRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("A base de conhecimento está vazia.")
        self.chunks = chunks
        # O título da seção entra duas vezes: ele resume bem o assunto do chunk.
        docs = [tokenize(f"{c.section} {c.section} {c.text}") for c in chunks]
        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        n = len(docs)
        self.idf = {term: math.log((1 + n) / (1 + freq)) + 1.0 for term, freq in df.items()}
        self.vectors = [self._vectorize(tokens) for tokens in docs]

    def _vectorize(self, tokens: list[str]) -> Vector:
        counts = Counter(t for t in tokens if t in self.idf)
        vec = {t: (1.0 + math.log(c)) * self.idf[t] for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {t: v / norm for t, v in vec.items()} if norm else {}

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        terms = tokenize(query, expand=True)
        qvec = self._vectorize(terms)
        if not qvec:
            return []
        unique_terms = set(terms)
        scored = []
        for chunk, dvec in zip(self.chunks, self.vectors, strict=True):
            score = sum(w * dvec.get(t, 0.0) for t, w in qvec.items())
            if score > 0:
                coverage = len(unique_terms & dvec.keys()) / len(unique_terms)
                scored.append(SearchResult(chunk=chunk, score=score, coverage=coverage))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
