"""Configuração via variáveis de ambiente (sem dependências extras)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    llm_model: str
    knowledge_dir: Path
    orders_file: Path
    retrieval_top_k: int
    min_retrieval_score: float
    min_query_coverage: float
    max_tool_iterations: int
    history_limit: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        llm_model=os.getenv("LLM_MODEL", "claude-sonnet-5-5"),
        knowledge_dir=Path(os.getenv("KNOWLEDGE_DIR", BASE_DIR / "data" / "knowledge")),
        orders_file=Path(os.getenv("ORDERS_FILE", BASE_DIR / "data" / "orders.json")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "3")),
        min_retrieval_score=float(os.getenv("MIN_RETRIEVAL_SCORE", "0.12")),
        min_query_coverage=float(os.getenv("MIN_QUERY_COVERAGE", "0.3")),
        max_tool_iterations=int(os.getenv("MAX_TOOL_ITERATIONS", "4")),
        history_limit=int(os.getenv("HISTORY_LIMIT", "10")),
    )
