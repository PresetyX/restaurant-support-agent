"""Loop de tool calling com a API da Anthropic (Claude)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


class ToolCallingLLM(Protocol):
    def run(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        execute: ToolExecutor,
    ) -> str: ...


class MaxIterationsError(RuntimeError):
    pass


class AnthropicToolLLM:
    def __init__(self, api_key: str, model: str, max_iterations: int = 4) -> None:
        from anthropic import Anthropic  # import tardio: o modo offline não precisa do SDK

        self.client = Anthropic(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model
        self.max_iterations = max_iterations

    def run(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        execute: ToolExecutor,
    ) -> str:
        convo: list[dict[str, Any]] = list(messages)
        for _ in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=tools,
                messages=convo,
            )
            if response.stop_reason != "tool_use":
                return "".join(b.text for b in response.content if b.type == "text").strip()

            convo.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = execute(block.name, dict(block.input))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output, ensure_ascii=False),
                        }
                    )
            convo.append({"role": "user", "content": results})
        raise MaxIterationsError("O modelo excedeu o limite de chamadas de ferramenta.")
