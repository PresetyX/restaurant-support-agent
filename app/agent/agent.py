"""Agente de atendimento: orquestra RAG, tool calling e handoff para humano.

Dois modos de execução, com o mesmo conjunto de ferramentas:
- **llm**: Claude decide quais ferramentas chamar (tool calling nativo).
- **offline**: roteador determinístico. Usado sem API key, nos testes e como
  fallback automático se o LLM falhar (timeout, erro de API, loop de ferramentas).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any

from app.agent import router
from app.agent.llm import ToolCallingLLM
from app.agent.prompts import SYSTEM_PROMPT
from app.schemas import AgentReply, Intent, ToolCall
from app.tools.orders import extract_order_id
from app.tools.toolbox import TOOL_SPECS, ToolBox

logger = logging.getLogger(__name__)

ALLERGY_NOTE = (
    "\n\nImportante: em caso de alergia ou doença celíaca, confirme com nossa equipe antes "
    "de pedir. Se quiser, eu te transfiro para um atendente."
)


class SupportAgent:
    def __init__(
        self, toolbox: ToolBox, llm: ToolCallingLLM | None = None, history_limit: int = 10
    ) -> None:
        self.toolbox = toolbox
        self.llm = llm
        self.history_limit = history_limit
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # ------------------------------------------------------------------ API pública
    def reply(self, message: str, session_id: str | None = None) -> AgentReply:
        session_id = session_id or uuid.uuid4().hex[:12]
        message = message.strip()

        # Guardrail: pedido explícito de humano ou reclamação sempre vai para a fila,
        # independentemente do que o LLM decidiria.
        if router.wants_human(message) or router.is_complaint(message):
            result = self._handoff(message, session_id)
        elif self.llm is not None:
            try:
                result = self._reply_llm(message, session_id)
            except Exception:
                logger.exception("Falha no LLM; respondendo em modo offline.")
                result = self._reply_offline(message, session_id)
        else:
            result = self._reply_offline(message, session_id)

        self._remember(session_id, message, result.answer)
        return result

    # ------------------------------------------------------------------ modo LLM
    def _reply_llm(self, message: str, session_id: str) -> AgentReply:
        calls: list[ToolCall] = []

        def execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            result = self.toolbox.execute(name, arguments, session_id)
            calls.append(ToolCall(name=name, arguments=arguments, result=result))
            return result

        messages = [*self._history[session_id], {"role": "user", "content": message}]
        answer = self.llm.run(SYSTEM_PROMPT, messages, TOOL_SPECS, execute)  # type: ignore[union-attr]

        ticket = next((c.result for c in calls if c.name == "escalate_to_human"), None)
        return AgentReply(
            session_id=session_id,
            answer=answer or "Desculpe, não consegui responder agora.",
            intent=self._intent_from_calls(calls),
            mode="llm",
            sources=self._sources_from_calls(calls),
            tool_calls=calls,
            handed_off=ticket is not None,
            ticket_id=ticket.get("ticket_id") if ticket else None,
        )

    # ------------------------------------------------------------------ modo offline
    def _reply_offline(self, message: str, session_id: str) -> AgentReply:
        order_id = extract_order_id(message)
        if order_id:
            return self._order_status(order_id, session_id)
        if router.is_order_question(message):
            return self._make(
                session_id,
                "Claro! Me passa o número do pedido (formato PED-1234) que eu consulto agora.",
                "order_status",
            )
        if router.is_greeting(message):
            return self._make(
                session_id,
                "Olá! Sou o assistente da Cantina Bella Massa. Posso consultar seu pedido "
                "ou tirar dúvidas sobre cardápio, entrega e pagamento.",
                "greeting",
            )
        return self._knowledge(message, session_id)

    def _order_status(self, order_id: str, session_id: str) -> AgentReply:
        args = {"order_id": order_id}
        result = self.toolbox.execute("get_order_status", args, session_id)
        call = ToolCall(name="get_order_status", arguments=args, result=result)
        if not result.get("found"):
            answer = (
                f"Não encontrei o pedido {result['order_id']}. Confira o número "
                "(formato PED-1234) ou peça para falar com um atendente."
            )
        else:
            answer = f"Seu pedido {result['order_id']} está {result['status_label']}."
            if result.get("eta_minutes"):
                answer += f" Previsão de chegada: cerca de {result['eta_minutes']} minutos."
            if result["status"] == "cancelado":
                answer += " Se houve cobrança, o estorno segue a nossa política de reembolso."
        return self._make(session_id, answer, "order_status", tool_calls=[call])

    def _knowledge(self, message: str, session_id: str) -> AgentReply:
        args = {"query": message}
        result = self.toolbox.execute("search_knowledge_base", args, session_id)
        call = ToolCall(name="search_knowledge_base", arguments=args, result=result)
        if not result["found"]:
            return self._handoff(message, session_id, reason="sem_resposta_na_base", prior=[call])

        best = result["results"][0]
        answer = f"{best['section']}:\n{best['content']}"
        if router.mentions_allergy(message):
            answer += ALLERGY_NOTE
        return self._make(
            session_id,
            answer,
            "knowledge",
            tool_calls=[call],
            sources=[best["source"]],
        )

    # ------------------------------------------------------------------ handoff
    def _handoff(
        self,
        message: str,
        session_id: str,
        reason: str | None = None,
        prior: list[ToolCall] | None = None,
    ) -> AgentReply:
        if reason is None:
            reason = "reclamacao" if router.is_complaint(message) else "pedido_do_cliente"
        args = {"reason": reason, "summary": message}
        ticket = self.toolbox.execute("escalate_to_human", args, session_id)
        call = ToolCall(name="escalate_to_human", arguments=args, result=ticket)
        intro = (
            "Não encontrei essa informação na nossa base. "
            if reason == "sem_resposta_na_base"
            else "Entendi. "
        )
        answer = (
            f"{intro}Transferi você para um atendente humano. "
            f"Protocolo: {ticket['ticket_id']}. Em instantes alguém continua a conversa."
        )
        return self._make(
            session_id,
            answer,
            "handoff",
            tool_calls=[*(prior or []), call],
            handed_off=True,
            ticket_id=ticket["ticket_id"],
        )

    # ------------------------------------------------------------------ utilitários
    def _make(self, session_id: str, answer: str, intent: Intent, **kwargs: Any) -> AgentReply:
        return AgentReply(
            session_id=session_id, answer=answer, intent=intent, mode="offline", **kwargs
        )

    def _remember(self, session_id: str, user: str, assistant: str) -> None:
        history = self._history[session_id]
        history.extend(
            [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        )
        del history[: -self.history_limit]

    @staticmethod
    def _intent_from_calls(calls: list[ToolCall]) -> Intent:
        names = {c.name for c in calls}
        if "escalate_to_human" in names:
            return "handoff"
        if "get_order_status" in names:
            return "order_status"
        if "search_knowledge_base" in names:
            return "knowledge"
        return "unknown"

    @staticmethod
    def _sources_from_calls(calls: list[ToolCall]) -> list[str]:
        sources: list[str] = []
        for call in calls:
            for item in call.result.get("results", []):
                if item["source"] not in sources:
                    sources.append(item["source"])
        return sources
