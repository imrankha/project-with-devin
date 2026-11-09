import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from shopping_agent.api import create_app
from shopping_agent.checkout import SkipCheckoutAgent
from shopping_agent.graph import build_graph
from shopping_agent.price_sources import default_mock_sources
from shopping_agent.store import OrderStore

ORDER = {
    "text": "sugar 2 kg, rice 5 kg",
    "shipping": {"first_name": "Asha", "last_name": "Rao", "address": "12 MG Road, Bengaluru"},
}


@pytest.fixture
def store(tmp_path):
    return OrderStore(str(tmp_path / "orders.sqlite"))


@pytest.fixture
def client(store):
    graph = build_graph(
        llm=None,
        price_sources=default_mock_sources(),
        checkout_agent=SkipCheckoutAgent(),
        order_store=store,
        checkpointer=InMemorySaver(),
    )
    with TestClient(create_app(graph)) as c:
        yield c


def test_order_pauses_for_approval_without_recording(client, store):
    resp = client.post("/order", json=ORDER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "awaiting_approval"
    assert body["recommendation"].startswith("Buy from ValueStore — save")
    assert [c["rank"] for c in body["comparison"]] == [1, 2, 3]
    assert body["pending_approval"]["site"] == "ValueStore"
    assert store.get_order(body["order_id"]) is None


def test_confirm_records_order_once(client, store):
    order_id = client.post("/order", json=ORDER).json()["order_id"]
    resp = client.post(f"/order/{order_id}/confirm", json={"approved": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "placed"
    saved = store.get_order(order_id)
    assert saved["site"] == "ValueStore" and saved["total"] == 409.0
    assert client.post(f"/order/{order_id}/confirm", json={"approved": True}).status_code == 409


def test_reject_cancels_without_recording(client, store):
    order_id = client.post("/order", json=ORDER).json()["order_id"]
    resp = client.post(f"/order/{order_id}/confirm", json={"approved": False})
    assert resp.json()["status"] == "cancelled"
    assert store.get_order(order_id) is None


def test_confirm_requires_explicit_decision(client):
    order_id = client.post("/order", json=ORDER).json()["order_id"]
    assert client.post(f"/order/{order_id}/confirm", json={}).status_code == 422
    assert client.get(f"/order/{order_id}").json()["status"] == "awaiting_approval"


def test_unknown_order_and_unparseable_input(client):
    assert client.post("/order/nope/confirm", json={"approved": True}).status_code == 404
    assert client.post("/order", json={**ORDER, "text": "sugar 2 bushels"}).status_code == 422
