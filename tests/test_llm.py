"""Testa o loop de tool calling da Anthropic sem rede, com um client simulado."""

import json
from types import SimpleNamespace as NS

import pytest

from app.agent.llm import AnthropicToolLLM, MaxIterationsError


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def make_llm(responses, max_iterations=4):
    llm = AnthropicToolLLM.__new__(AnthropicToolLLM)  # evita criar o client real
    llm.client = NS(messages=FakeMessages(responses))
    llm.model = "fake-model"
    llm.max_iterations = max_iterations
    return llm


def tool_use(name, args, id_="tu_1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id=id_, name=name, input=args)])


def final(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


def test_runs_tool_and_returns_final_text():
    llm = make_llm([tool_use("get_order_status", {"order_id": "PED-1002"}), final("Já saiu!")])
    executed = []

    def execute(name, args):
        executed.append((name, args))
        return {"found": True, "status": "saiu_para_entrega"}

    answer = llm.run("sys", [{"role": "user", "content": "e meu pedido?"}], [], execute)

    assert answer == "Já saiu!"
    assert executed == [("get_order_status", {"order_id": "PED-1002"})]
    second_request = llm.client.messages.requests[1]["messages"]
    tool_result = second_request[-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "tu_1"
    assert json.loads(tool_result["content"])["status"] == "saiu_para_entrega"


def test_raises_when_model_loops_on_tools():
    llm = make_llm([tool_use("search_knowledge_base", {"query": "x"})] * 2, max_iterations=2)
    with pytest.raises(MaxIterationsError):
        llm.run("sys", [{"role": "user", "content": "?"}], [], lambda n, a: {})
