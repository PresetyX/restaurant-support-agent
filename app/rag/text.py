"""Normalização e tokenização de texto em português."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = set(
    """
    a o os as ao aos de do da dos das e em no na nos nas um uma uns umas para pra pro por
    pelo pela com que qual quais eu voce voces vcs vc meu minha tem ter ser se como quanto
    quantos quando onde ola oi bom boa dia tarde noite favor gostaria queria quero saber
    posso pode sim isso esse essa este esta ja mais muito obrigado obrigada ai la aqui
    tambem vou ha sao estou seu sua sou comer algum alguma dar
    """.split()  # noqa: SIM905 - mais legível que uma lista literal longa
)

# Expansão leve de sinônimos: aproxima a linguagem do cliente da linguagem da base.
SYNONYMS = {
    "abre": "horario funcionamento",
    "abrem": "horario funcionamento",
    "fecha": "horario funcionamento",
    "fecham": "horario funcionamento",
    "aberto": "horario funcionamento",
    "pix": "pagamento",
    "cartao": "pagamento",
    "pagar": "pagamento",
    "frete": "taxa entrega",
    "demora": "tempo entrega",
    "cancelar": "cancelamento",
    "devolucao": "reembolso",
    "celiaco": "sem gluten",
    "vegano": "vegano vegetal",
    "cupom": "cupom promocao",
    "cerveja": "bebida alcoolica",
    "vinho": "bebida alcoolica",
    "refri": "refrigerante",
    "beber": "bebida",
}


def normalize(text: str) -> str:
    """Minúsculas e sem acentos: 'Glúten' -> 'gluten'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem(token: str) -> str:
    # Stemming mínimo: plural simples ("massas" -> "massa", "pizzas" -> "pizza").
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def tokenize(text: str, expand: bool = False) -> list[str]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOPWORDS]
    if expand:
        extra: list[str] = []
        for t in tokens:
            if t in SYNONYMS:
                extra.extend(SYNONYMS[t].split())
        tokens.extend(extra)
    return [_stem(t) for t in tokens]
