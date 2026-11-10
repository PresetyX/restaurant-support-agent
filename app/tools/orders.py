"""Consulta de status de pedido (API simulada sobre um JSON local)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ORDER_ID_PATTERN = re.compile(r"^PED-\d{4}$")
# Encontra "PED-1002", "ped 1002", "PED1002" ou "#1002" dentro de uma frase.
ORDER_ID_IN_TEXT = re.compile(r"(?:\bPED[-\s#]?|#)(\d{4})\b", re.IGNORECASE)

STATUS_LABELS = {
    "recebido": "recebido pelo restaurante",
    "em_preparo": "em preparo na cozinha",
    "saiu_para_entrega": "a caminho com o entregador",
    "entregue": "entregue",
    "cancelado": "cancelado",
}


def normalize_order_id(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return f"PED-{digits}" if digits else raw.strip().upper()


def extract_order_id(text: str) -> str | None:
    match = ORDER_ID_IN_TEXT.search(text)
    return f"PED-{match.group(1)}" if match else None


class OrderRepository:
    """Simula a API de pedidos. Em produção, seria um client HTTP para o serviço real."""

    def __init__(self, orders_file: Path) -> None:
        data = json.loads(orders_file.read_text(encoding="utf-8"))
        self._orders: dict[str, dict[str, Any]] = {o["order_id"]: o for o in data}

    def get(self, order_id: str) -> dict[str, Any] | None:
        return self._orders.get(order_id)


def get_order_status(order_id: str, repo: OrderRepository) -> dict[str, Any]:
    normalized = normalize_order_id(order_id)
    if not ORDER_ID_PATTERN.match(normalized):
        return {
            "found": False,
            "order_id": order_id,
            "error": "formato_invalido",
            "hint": "O número do pedido segue o formato PED-1234.",
        }
    order = repo.get(normalized)
    if order is None:
        return {"found": False, "order_id": normalized, "error": "pedido_nao_encontrado"}
    return {
        "found": True,
        "order_id": normalized,
        "status": order["status"],
        "status_label": STATUS_LABELS.get(order["status"], order["status"]),
        "eta_minutes": order.get("eta_minutes"),
        "items": order.get("items", []),
        "updated_at": order.get("updated_at"),
    }
