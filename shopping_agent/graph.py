"""LangGraph wiring: parse_list -> find_prices -> optimize -> checkout -> payment."""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .checkout import CheckoutAgent
from .models import ListItem, ShippingDetails, SiteQuote
from .optimizer import optimize
from .parser import ParseError, parse_shopping_list
from .price_sources import PriceSource
from .store import OrderStore

log = logging.getLogger(__name__)


class ShoppingState(TypedDict, total=False):
    order_id: str
    raw_text: str
    shipping: dict[str, Any]
    items: list[dict[str, Any]]
    quotes: list[dict[str, Any]]
    comparison: list[dict[str, Any]]
    recommendation: str | None
    selected_site: str | None
    checkout: dict[str, Any] | None
    order: dict[str, Any] | None
    status: str
    error: str | None


def _continue_unless_error(next_node: str):
    def route(state: ShoppingState) -> str:
        return END if state.get("error") else next_node

    return route


def build_graph(
    *,
    llm: BaseChatModel | None,
    price_sources: list[PriceSource],
    checkout_agent: CheckoutAgent,
    order_store: OrderStore,
    checkpointer: BaseCheckpointSaver,
):
    if checkpointer is None:
        raise ValueError("A checkpointer is required: the payment step pauses with interrupt()")

    def parse_list(state: ShoppingState) -> dict:
        try:
            items = parse_shopping_list(state["raw_text"], llm)
        except ParseError as exc:
            return {"status": "parse_failed", "error": str(exc)}
        return {"items": [i.model_dump() for i in items], "status": "parsed"}

    def find_prices(state: ShoppingState) -> dict:
        items = [ListItem(**i) for i in state["items"]]

        def fetch(source: PriceSource) -> SiteQuote | None:
            try:
                return source.quote(items)
            except Exception:
                log.exception("Price source %s failed", getattr(source, "name", source))
                return None

        with ThreadPoolExecutor(max_workers=max(1, len(price_sources))) as pool:
            quotes = [q for q in pool.map(fetch, price_sources) if q is not None]
        if not quotes:
            return {"status": "no_prices", "error": "No price source returned a quote"}
        return {"quotes": [q.model_dump() for q in quotes], "status": "priced"}

    def optimize_node(state: ShoppingState) -> dict:
        ranked = optimize([SiteQuote(**q) for q in state["quotes"]])
        best = next((c for c in ranked if c.rank == 1), None)
        update: dict = {"comparison": [c.model_dump() for c in ranked]}
        if best is None:
            return {**update, "recommendation": None, "status": "no_complete_cart",
                    "error": "No site stocks every item on the list"}
        return {**update, "recommendation": best.summary, "selected_site": best.site, "status": "optimized"}

    def checkout(state: ShoppingState) -> dict:
        result = checkout_agent.run(
            state["selected_site"], state["items"], ShippingDetails(**state["shipping"])
        )
        if result.status == "failed":
            return {"checkout": result.model_dump(), "status": "checkout_failed", "error": result.detail}
        return {"checkout": result.model_dump(), "status": "awaiting_approval"}

    def payment(state: ShoppingState) -> dict:
        best = next(c for c in state["comparison"] if c["site"] == state["selected_site"])
        # Pauses the graph until a human resumes it via POST /order/{id}/confirm.
        decision = interrupt(
            {
                "question": f"Approve payment of {best['currency']} {best['total']:.2f} to {best['site']}?",
                "order_id": state["order_id"],
                "site": best["site"],
                "total": best["total"],
                "currency": best["currency"],
                "coupon_code": best["coupon_code"],
            }
        )
        approved = isinstance(decision, dict) and decision.get("approved") is True
        if not approved:
            return {"status": "cancelled"}
        order = order_store.record_order(
            order_id=state["order_id"],
            site=best["site"],
            currency=best["currency"],
            total=best["total"],
            coupon_code=best["coupon_code"],
            savings_pct=best["savings_pct"],
            items=state["items"],
            shipping=state["shipping"],
        )
        return {"order": order, "status": "placed"}

    g = StateGraph(ShoppingState)
    g.add_node("parse_list", parse_list)
    g.add_node("find_prices", find_prices)
    g.add_node("optimize", optimize_node)
    g.add_node("checkout", checkout)
    g.add_node("payment", payment)
    g.add_edge(START, "parse_list")
    g.add_conditional_edges("parse_list", _continue_unless_error("find_prices"), ["find_prices", END])
    g.add_conditional_edges("find_prices", _continue_unless_error("optimize"), ["optimize", END])
    g.add_conditional_edges("optimize", _continue_unless_error("checkout"), ["checkout", END])
    g.add_conditional_edges("checkout", _continue_unless_error("payment"), ["payment", END])
    g.add_edge("payment", END)
    return g.compile(checkpointer=checkpointer)


def build_default_graph():
    import sqlite3
    from pathlib import Path

    from langgraph.checkpoint.sqlite import SqliteSaver

    from .checkout import default_checkout_agent
    from .config import get_settings
    from .parser import default_llm
    from .price_sources import default_mock_sources

    s = get_settings()
    Path(s.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(s.checkpoint_db_path, check_same_thread=False)
    return build_graph(
        llm=default_llm(),
        price_sources=default_mock_sources(),
        checkout_agent=default_checkout_agent(),
        order_store=OrderStore(s.orders_db_path),
        checkpointer=SqliteSaver(conn),
    )
