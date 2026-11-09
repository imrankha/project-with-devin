import threading
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from .mock_shop import router as mock_shop_router
from .models import ShippingDetails


class OrderRequest(BaseModel):
    text: str
    shipping: ShippingDetails


class ConfirmRequest(BaseModel):
    approved: bool


class OrderResponse(BaseModel):
    order_id: str
    status: str
    error: str | None = None
    items: list[dict[str, Any]] = []
    comparison: list[dict[str, Any]] = []
    recommendation: str | None = None
    checkout: dict[str, Any] | None = None
    pending_approval: dict[str, Any] | None = None
    order: dict[str, Any] | None = None


def create_app(graph=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.graph is None:
            from .graph import build_default_graph

            app.state.graph = build_default_graph()
        yield

    app = FastAPI(title="Shopping Agent", lifespan=lifespan)
    app.state.graph = graph
    confirm_lock = threading.Lock()
    app.include_router(mock_shop_router, prefix="/mock-shop", include_in_schema=False)

    def _config(order_id: str) -> dict:
        return {"configurable": {"thread_id": order_id}}

    def _response(order_id: str) -> OrderResponse:
        snap = app.state.graph.get_state(_config(order_id))
        if not snap.values:
            raise HTTPException(404, "Order not found")
        v = snap.values
        pending = snap.interrupts[0].value if snap.interrupts else None
        return OrderResponse(
            order_id=order_id,
            status=v.get("status", "unknown"),
            error=v.get("error"),
            items=v.get("items", []),
            comparison=v.get("comparison", []),
            recommendation=v.get("recommendation"),
            checkout=v.get("checkout"),
            pending_approval=pending,
            order=v.get("order"),
        )

    # Sync handlers run in a worker thread, which the sync Playwright API requires.
    @app.post("/order", response_model=OrderResponse)
    def create_order(req: OrderRequest) -> OrderResponse:
        order_id = uuid.uuid4().hex
        app.state.graph.invoke(
            {"order_id": order_id, "raw_text": req.text, "shipping": req.shipping.model_dump()},
            _config(order_id),
        )
        resp = _response(order_id)
        if resp.status == "parse_failed":
            raise HTTPException(422, resp.error)
        return resp

    @app.get("/order/{order_id}", response_model=OrderResponse)
    def get_order(order_id: str) -> OrderResponse:
        return _response(order_id)

    @app.post("/order/{order_id}/confirm", response_model=OrderResponse)
    def confirm_order(order_id: str, req: ConfirmRequest) -> OrderResponse:
        with confirm_lock:
            current = _response(order_id)
            if current.pending_approval is None:
                raise HTTPException(409, f"Order is not awaiting approval (status: {current.status})")
            app.state.graph.invoke(Command(resume={"approved": req.approved}), _config(order_id))
        return _response(order_id)

    return app


app = create_app()
