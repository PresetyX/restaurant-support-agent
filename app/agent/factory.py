"""Monta o agente a partir das configurações."""

from __future__ import annotations

import logging

from app.agent.agent import SupportAgent
from app.agent.llm import AnthropicToolLLM, ToolCallingLLM
from app.config import Settings, get_settings
from app.rag import TfidfRetriever, load_knowledge_base
from app.tools import HandoffQueue, OrderRepository, ToolBox

logger = logging.getLogger(__name__)


def build_agent(settings: Settings | None = None, use_llm: bool | None = None) -> SupportAgent:
    settings = settings or get_settings()
    toolbox = ToolBox(
        retriever=TfidfRetriever(load_knowledge_base(settings.knowledge_dir)),
        orders=OrderRepository(settings.orders_file),
        handoffs=HandoffQueue(),
        top_k=settings.retrieval_top_k,
        min_score=settings.min_retrieval_score,
        min_coverage=settings.min_query_coverage,
    )
    use_llm = settings.llm_enabled if use_llm is None else use_llm
    llm: ToolCallingLLM | None = None
    if use_llm and settings.anthropic_api_key:
        llm = AnthropicToolLLM(
            settings.anthropic_api_key, settings.llm_model, settings.max_tool_iterations
        )
        logger.info("Agente em modo LLM (%s).", settings.llm_model)
    else:
        logger.info("Agente em modo offline (sem ANTHROPIC_API_KEY).")
    return SupportAgent(toolbox, llm=llm, history_limit=settings.history_limit)
