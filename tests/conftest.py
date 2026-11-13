from __future__ import annotations

import pytest

from app.agent import SupportAgent
from app.config import get_settings
from app.rag import TfidfRetriever, load_knowledge_base
from app.tools import HandoffQueue, OrderRepository, ToolBox


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def retriever(settings):
    return TfidfRetriever(load_knowledge_base(settings.knowledge_dir))


@pytest.fixture(scope="session")
def orders(settings):
    return OrderRepository(settings.orders_file)


@pytest.fixture
def toolbox(retriever, orders, settings):
    return ToolBox(
        retriever,
        orders,
        HandoffQueue(),
        min_score=settings.min_retrieval_score,
        min_coverage=settings.min_query_coverage,
    )


@pytest.fixture
def offline_agent(toolbox):
    return SupportAgent(toolbox, llm=None)
