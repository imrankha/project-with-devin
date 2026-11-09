"""SQLite persistence for placed orders."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id     TEXT PRIMARY KEY,
    site         TEXT NOT NULL,
    currency     TEXT NOT NULL,
    total        REAL NOT NULL,
    coupon_code  TEXT,
    savings_pct  REAL NOT NULL,
    items_json   TEXT NOT NULL,
    shipping_json TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL
)
"""


class OrderStore:
    def __init__(self, path: str):
        self.path = path
        # An in-memory database exists only on the connection that created it.
        self._shared_conn: sqlite3.Connection | None = None
        if path == ":memory:":
            self._shared_conn = sqlite3.connect(path, check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_order(
        self,
        *,
        order_id: str,
        site: str,
        currency: str,
        total: float,
        coupon_code: str | None,
        savings_pct: float,
        items: list[dict[str, Any]],
        shipping: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert the order; a repeated call for the same order_id is a no-op."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id, site, currency, total, coupon_code, savings_pct,
                    json.dumps(items), json.dumps(shipping), "placed",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        order = self.get_order(order_id)
        assert order is not None
        return order

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return None
        order = dict(row)
        order["items"] = json.loads(order.pop("items_json"))
        order["shipping"] = json.loads(order.pop("shipping_json"))
        return order
