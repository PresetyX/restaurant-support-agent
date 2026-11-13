import pytest

from app.tools.orders import extract_order_id, get_order_status


def test_get_order_status_found(orders):
    result = get_order_status("PED-1002", orders)
    assert result["found"] is True
    assert result["status"] == "saiu_para_entrega"
    assert result["eta_minutes"] == 12


@pytest.mark.parametrize("raw", ["ped-1002", " PED 1002 ", "1002", "#1002"])
def test_get_order_status_normalizes_id(orders, raw):
    assert get_order_status(raw, orders)["order_id"] == "PED-1002"


def test_get_order_status_not_found(orders):
    result = get_order_status("PED-9999", orders)
    assert result == {"found": False, "order_id": "PED-9999", "error": "pedido_nao_encontrado"}


def test_get_order_status_invalid_format(orders):
    result = get_order_status("abc", orders)
    assert result["found"] is False
    assert result["error"] == "formato_invalido"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("cadê o PED-1001?", "PED-1001"),
        ("pedido ped1003 atrasado", "PED-1003"),
        ("é o #1004", "PED-1004"),
        ("a pizza custa 5990", None),
    ],
)
def test_extract_order_id(text, expected):
    assert extract_order_id(text) == expected


def test_toolbox_executes_order_tool(toolbox):
    result = toolbox.execute("get_order_status", {"order_id": "PED-1001"}, "s1")
    assert result["status"] == "em_preparo"


def test_toolbox_search_returns_sources(toolbox):
    result = toolbox.execute("search_knowledge_base", {"query": "taxa de entrega"}, "s1")
    assert result["found"] is True
    assert result["results"][0]["source"] == "politicas.md › Área e taxa de entrega"


def test_toolbox_escalate_creates_sequential_tickets(toolbox):
    t1 = toolbox.execute("escalate_to_human", {"reason": "reclamacao", "summary": "a"}, "s1")
    t2 = toolbox.execute("escalate_to_human", {"reason": "invalido", "summary": "b"}, "s2")
    assert (t1["ticket_id"], t2["ticket_id"]) == ("ATD-0001", "ATD-0002")
    assert t2["reason"] == "outro"  # motivo desconhecido é normalizado
    assert len(toolbox.handoffs.list()) == 2


def test_toolbox_handles_bad_calls_without_raising(toolbox):
    assert "ferramenta_desconhecida" in toolbox.execute("delete_db", {}, "s1")["error"]
    assert "argumento_obrigatorio_ausente" in toolbox.execute("get_order_status", {}, "s1")["error"]
