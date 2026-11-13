import pytest
from fastapi.testclient import TestClient

from app.main import app, get_agent


@pytest.fixture
def client(offline_agent):
    app.dependency_overrides[get_agent] = lambda: offline_agent
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "offline"
    assert body["chunks_indexed"] > 10


def test_chat_order_status(client):
    response = client.post("/chat", json={"message": "status do PED-1005"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_status"
    assert body["tool_calls"][0]["result"]["status"] == "recebido"
    assert body["session_id"]


def test_chat_keeps_session_id(client):
    body = client.post("/chat", json={"message": "oi", "session_id": "minha-sessao"}).json()
    assert body["session_id"] == "minha-sessao"


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 1001}])
def test_chat_validates_input(client, payload):
    assert client.post("/chat", json=payload).status_code == 422


def test_handoffs_endpoint_lists_tickets(client):
    client.post("/chat", json={"message": "quero falar com um atendente"})
    tickets = client.get("/handoffs").json()
    assert len(tickets) == 1
    assert tickets[0]["ticket_id"] == "ATD-0001"


def test_index_serves_demo_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Cantina Bella Massa" in response.text
