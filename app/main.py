"""API HTTP do agente (FastAPI)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from app import __version__
from app.agent import SupportAgent, build_agent
from app.schemas import AgentReply, ChatRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Restaurant Support Agent",
    version=__version__,
    description="Agente de atendimento para restaurantes com RAG, tool calling e handoff.",
)


@lru_cache
def get_agent() -> SupportAgent:
    return build_agent()


AgentDep = Annotated[SupportAgent, Depends(get_agent)]


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health(agent: AgentDep) -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "mode": "llm" if agent.llm else "offline",
        "chunks_indexed": len(agent.toolbox.retriever.chunks),  # type: ignore[attr-defined]
    }


@app.post("/chat", response_model=AgentReply)
def chat(request: ChatRequest, agent: AgentDep) -> AgentReply:
    return agent.reply(request.message, request.session_id)


@app.get("/handoffs")
def handoffs(agent: AgentDep) -> list[dict[str, Any]]:
    """Fila de atendimento humano (para o painel do atendente / demo)."""
    return agent.toolbox.handoffs.list()
