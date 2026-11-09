from shopping_agent.store import OrderStore


def test_in_memory_store_round_trip():
    store = OrderStore(":memory:")
    store.record_order(order_id="o1", site="QuickMart", currency="INR", total=10.0, coupon_code=None,
                       savings_pct=0.0, items=[{"item": "salt"}], shipping={"first_name": "A"})
    assert store.get_order("o1")["items"] == [{"item": "salt"}]
