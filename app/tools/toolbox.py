"""Registro de ferramentas: schemas para o LLM + execução segura."""

from __future__ import annotations

import logging
from typing import Any

from app.rag.retriever import Retriever
from app.tools.handoff import HandoffQueue
from app.tools.orders import OrderRepository, get_order_status

logger = logging.getLogger(__name__)

HANDOFF_REASONS = ["pedido_do_cliente", "reclamacao", "sem_resposta_na_base", "outro"]

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Busca no cardápio, nas políticas e no FAQ do restaurante. Use para qualquer "
            "pergunta sobre pratos, preços, ingredientes, alergênicos, horários, entrega, "
            "pagamento, cancelamento ou reembolso."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Pergunta do cliente."}},
            "required": ["query"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Consulta o status atual de um pedido pelo número (formato PED-1234).",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Ex.: PED-1002"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Transfere a conversa para um atendente humano. Use quando o cliente pedir, "
            "reclamar de um problema com o pedido, ou quando a base não tiver a resposta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "enum": HANDOFF_REASONS},
                "summary": {"type": "string", "description": "Resumo do caso para o atendente."},
            },
            "required": ["reason", "summary"],
        },
    },
]


class ToolBox:
    def __init__(
        self,
        retriever: Retriever,
        orders: OrderRepository,
        handoffs: HandoffQueue,
        top_k: int = 3,
        min_score: float = 0.12,
        min_coverage: float = 0.3,
    ) -> None:
        self.retriever = retriever
        self.orders = orders
        self.handoffs = handoffs
        self.top_k = top_k
        self.min_score = min_score
        self.min_coverage = min_coverage

    def search_knowledge_base(self, query: str) -> dict[str, Any]:
        # Dois critérios: similaridade suficiente E boa parte da pergunta coberta pelo trecho.
        # Só similaridade deixa passar falsos positivos de uma palavra ("previsão do *tempo*").
        hits = [
            r
            for r in self.retriever.search(query, self.top_k)
            if r.score >= self.min_score and r.coverage >= self.min_coverage
        ]
        return {
            "found": bool(hits),
            "results": [
                {
                    "source": r.chunk.ref,
                    "section": r.chunk.section,
                    "content": r.chunk.text,
                    "score": round(r.score, 3),
                }
                for r in hits
            ],
        }

    def execute(self, name: str, arguments: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Executa uma ferramenta. Nunca levanta exceção: erros viram resultado para o agente."""
        try:
            if name == "search_knowledge_base":
                return self.search_knowledge_base(str(arguments["query"]))
            if name == "get_order_status":
                return get_order_status(str(arguments["order_id"]), self.orders)
            if name == "escalate_to_human":
                reason = arguments.get("reason", "outro")
                if reason not in HANDOFF_REASONS:
                    reason = "outro"
                return self.handoffs.create(session_id, reason, str(arguments.get("summary", "")))
            return {"error": f"ferramenta_desconhecida: {name}"}
        except KeyError as exc:
            return {"error": f"argumento_obrigatorio_ausente: {exc.args[0]}"}
        except Exception:  # pragma: no cover - proteção contra falhas inesperadas
            logger.exception("Falha ao executar a ferramenta %s", name)
            return {"error": "falha_interna_na_ferramenta"}
