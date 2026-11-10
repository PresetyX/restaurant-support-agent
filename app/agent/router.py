"""Regras determinísticas: guardrails do modo LLM e roteador do modo offline."""

from __future__ import annotations

import re

from app.rag.text import normalize

HUMAN_REQUEST = re.compile(
    r"\b(atendente|humano|pessoa de verdade|falar com (alguem|uma pessoa)|gerente|"
    r"suporte humano)\b"
)
COMPLAINT = re.compile(
    r"\b(reclama\w*|veio errado|errad[oa]|faltando|faltou|estragad[oa]|fri[oa]|crua?|"
    r"pessim[oa]|absurdo|procon|cobrad[oa] duas vezes|cobranca indevida)\b"
)
ORDER_QUESTION = re.compile(
    r"\b(meu pedido|status do pedido|status|cade|onde esta|rastrear|acompanhar|"
    r"ja saiu|vai chegar|chega quando)\b"
)
# Perguntas de política que mencionam "pedido" mas não pedem status ("posso cancelar meu pedido?").
POLICY_QUESTION = re.compile(r"\b(cancel\w*|reembols\w*|estorn\w*|minimo|taxa|troc\w*)\b")
ALLERGY = re.compile(r"\b(alergi\w*|alergic\w*|celiac\w*|intoleran\w*)\b")
GREETINGS = {"oi", "ola", "bom dia", "boa tarde", "boa noite", "eai", "e ai", "hello", "opa"}


def wants_human(text: str) -> bool:
    return bool(HUMAN_REQUEST.search(normalize(text)))


def is_complaint(text: str) -> bool:
    return bool(COMPLAINT.search(normalize(text)))


def is_order_question(text: str) -> bool:
    normalized = normalize(text)
    return bool(ORDER_QUESTION.search(normalized)) and not POLICY_QUESTION.search(normalized)


def mentions_allergy(text: str) -> bool:
    return bool(ALLERGY.search(normalize(text)))


def is_greeting(text: str) -> bool:
    cleaned = re.sub(r"[^a-z ]", "", normalize(text)).strip()
    return cleaned in GREETINGS
