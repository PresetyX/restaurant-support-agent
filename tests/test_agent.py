from app.agent import SupportAgent


class FakeLLM:
    """Simula o Claude: chama ferramentas na ordem definida e devolve um texto final."""

    def __init__(self, plan, answer="ok"):
        self.plan = plan
        self.answer = answer
        self.calls = 0
        self.last_messages = None

    def run(self, system, messages, tools, execute):
        self.calls += 1
        self.last_messages = messages
        assert {t["name"] for t in tools} == {
            "search_knowledge_base",
            "get_order_status",
            "escalate_to_human",
        }
        for name, args in self.plan:
            execute(name, args)
        return self.answer


class BrokenLLM:
    def run(self, *args, **kwargs):
        raise TimeoutError("API fora do ar")


# ---------------------------------------------------------------- modo offline
def test_offline_order_status_calls_tool(offline_agent):
    reply = offline_agent.reply("Cadê meu pedido PED-1002?")
    assert reply.intent == "order_status"
    assert reply.tool_calls[0].name == "get_order_status"
    assert "a caminho" in reply.answer
    assert "12 minutos" in reply.answer


def test_offline_asks_for_order_number(offline_agent):
    reply = offline_agent.reply("cadê meu pedido?")
    assert reply.intent == "order_status"
    assert "PED-1234" in reply.answer
    assert reply.tool_calls == []


def test_offline_unknown_order(offline_agent):
    reply = offline_agent.reply("status do PED-9999")
    assert "Não encontrei o pedido PED-9999" in reply.answer


def test_offline_policy_question_mentioning_order_uses_rag(offline_agent):
    reply = offline_agent.reply("Posso cancelar meu pedido?")
    assert reply.intent == "knowledge"
    assert reply.sources == ["politicas.md › Cancelamento"]


def test_offline_knowledge_answer_cites_source(offline_agent):
    reply = offline_agent.reply("Vocês aceitam pix?")
    assert reply.intent == "knowledge"
    assert reply.sources == ["faq.md › Formas de pagamento"]
    assert "Pix" in reply.answer


def test_offline_allergy_question_adds_safety_note(offline_agent):
    reply = offline_agent.reply("Sou celíaco, tem opção sem glúten?")
    assert "contaminação cruzada" in reply.answer
    assert "confirme com nossa equipe" in reply.answer


def test_offline_handoff_when_base_has_no_answer(offline_agent):
    reply = offline_agent.reply("Qual a capital da França?")
    assert reply.handed_off is True
    assert reply.intent == "handoff"
    assert reply.ticket_id == "ATD-0001"
    assert [c.name for c in reply.tool_calls] == ["search_knowledge_base", "escalate_to_human"]
    assert reply.tool_calls[-1].result["reason"] == "sem_resposta_na_base"


def test_offline_greeting(offline_agent):
    assert offline_agent.reply("Oi!").intent == "greeting"


# ---------------------------------------------------------------- guardrails
def test_human_request_always_escalates_even_with_llm(toolbox):
    llm = FakeLLM(plan=[])
    agent = SupportAgent(toolbox, llm=llm)
    reply = agent.reply("Quero falar com um atendente")
    assert reply.handed_off is True
    assert reply.tool_calls[0].result["reason"] == "pedido_do_cliente"
    assert llm.calls == 0  # o LLM nem é chamado


def test_complaint_escalates_with_reason(offline_agent):
    reply = offline_agent.reply("Meu pedido veio errado e a pizza veio fria")
    assert reply.handed_off is True
    assert reply.tool_calls[0].result["reason"] == "reclamacao"


# ---------------------------------------------------------------- modo LLM
def test_llm_mode_records_tool_calls_and_sources(toolbox):
    llm = FakeLLM(
        plan=[("search_knowledge_base", {"query": "taxa de entrega"})],
        answer="A taxa é R$ 5,99 até 3 km.",
    )
    reply = SupportAgent(toolbox, llm=llm).reply("Qual a taxa de entrega?", session_id="abc")
    assert reply.mode == "llm"
    assert reply.intent == "knowledge"
    assert reply.answer == "A taxa é R$ 5,99 até 3 km."
    assert reply.sources[0] == "politicas.md › Área e taxa de entrega"
    assert reply.session_id == "abc"


def test_llm_mode_order_tool(toolbox):
    llm = FakeLLM(plan=[("get_order_status", {"order_id": "PED-1001"})], answer="Em preparo!")
    reply = SupportAgent(toolbox, llm=llm).reply("e o PED-1001?")
    assert reply.intent == "order_status"
    assert reply.tool_calls[0].result["status"] == "em_preparo"


def test_llm_mode_escalation_sets_ticket(toolbox):
    llm = FakeLLM(
        plan=[("escalate_to_human", {"reason": "sem_resposta_na_base", "summary": "x"})],
        answer="Transferi.",
    )
    reply = SupportAgent(toolbox, llm=llm).reply("pergunta difícil")
    assert reply.handed_off is True
    assert reply.ticket_id == "ATD-0001"


def test_llm_failure_falls_back_to_offline(toolbox):
    reply = SupportAgent(toolbox, llm=BrokenLLM()).reply("status do PED-1002")
    assert reply.mode == "offline"
    assert reply.intent == "order_status"
    assert "a caminho" in reply.answer


def test_history_is_kept_per_session_and_trimmed(toolbox):
    llm = FakeLLM(plan=[])
    agent = SupportAgent(toolbox, llm=llm, history_limit=4)
    for i in range(5):
        agent.reply(f"mensagem {i}", session_id="s1")
    # 4 mensagens anteriores (2 trocas) + a atual
    assert len(llm.last_messages) == 5
    assert llm.last_messages[-1]["content"] == "mensagem 4"
    agent.reply("outra sessão", session_id="s2")
    assert len(llm.last_messages) == 1
