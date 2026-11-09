"""Runs the Playwright checkout agent against the bundled mock shop. Skipped if Chromium isn't installed."""
import socket
import threading
import time

import pytest
import uvicorn

from shopping_agent.checkout import PlaywrightCheckoutAgent
from shopping_agent.models import ShippingDetails


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _chromium_available(), reason="run `playwright install chromium`")


@pytest.fixture
def shop_url():
    from fastapi import FastAPI

    from shopping_agent.mock_shop import router

    app = FastAPI()
    app.include_router(router, prefix="/mock-shop")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mock-shop"
    server.should_exit = True
    thread.join(timeout=5)


def test_agent_logs_in_and_fills_checkout(shop_url, tmp_path, monkeypatch):
    monkeypatch.delenv("CHECKOUT_USERNAME", raising=False)
    from shopping_agent.config import get_settings

    get_settings.cache_clear()
    agent = PlaywrightCheckoutAgent(shop_url, "demo", "pw", screenshot_dir=str(tmp_path))
    result = agent.run("ValueStore", [], ShippingDetails(first_name="Asha", last_name="Rao", address="12 MG Road"))
    get_settings.cache_clear()
    assert result.status == "ready_for_payment", result.detail
    assert (tmp_path / "checkout-valuestore.png").exists()
