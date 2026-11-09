import pytest

from shopping_agent.models import Coupon, ItemQuote, ListItem, SiteQuote
from shopping_agent.optimizer import coupon_discount, optimize, price_cart
from shopping_agent.price_sources import default_mock_sources


def quote(site, lines, coupons=(), delivery_fee=0.0, threshold=None, missing=()):
    return SiteQuote(
        site=site,
        items=[
            ItemQuote(item=name, requested_quantity=1, requested_unit="kg", unit_price=total,
                      base_unit="kg", line_total=total)
            for name, total in lines.items()
        ],
        missing_items=list(missing),
        coupons=list(coupons),
        delivery_fee=delivery_fee,
        free_delivery_threshold=threshold,
    )


def by_site(results):
    return {r.site: r for r in results}


def test_savings_pct_vs_most_expensive():
    results = optimize([quote("A", {"rice": 100.0}), quote("B", {"rice": 70.0}), quote("C", {"rice": 85.0})])
    assert [r.site for r in results] == ["B", "C", "A"]
    assert [r.rank for r in results] == [1, 2, 3]
    r = by_site(results)
    assert r["B"].savings_amount == 30.0 and r["B"].savings_pct == 30.0
    assert r["C"].savings_pct == 15.0
    assert r["A"].savings_pct == 0.0
    assert r["B"].summary.startswith("Buy from B — save 30%")


def test_percent_coupon_min_cart_and_cap():
    c = Coupon(code="P10", description="", kind="percent", value=10, min_cart_value=500, max_discount=150)
    assert coupon_discount(c, quote("A", {"x": 400.0}), 400.0) == 0.0
    assert coupon_discount(c, quote("A", {"x": 600.0}), 600.0) == 60.0
    assert coupon_discount(c, quote("A", {"x": 2000.0}), 2000.0) == 150.0


def test_item_scoped_coupon_only_discounts_eligible_lines():
    c = Coupon(code="S15", description="", kind="percent", value=15, applicable_items=["rice"])
    q = quote("A", {"rice": 200.0, "sugar": 100.0})
    assert coupon_discount(c, q, 300.0) == 30.0


def test_best_single_coupon_and_delivery_threshold():
    coupons = [
        Coupon(code="FLAT50", description="", kind="flat", value=50, min_cart_value=300),
        Coupon(code="P20", description="", kind="percent", value=20),
    ]
    # 20% (=100) beats flat 50, but drops the cart below free delivery (450 < 480) and adds 40.
    q = quote("A", {"rice": 500.0}, coupons=coupons, delivery_fee=40.0, threshold=440.0)
    assert price_cart(q) == (500.0, "P20", 100.0, 40.0, 440.0)
    q2 = quote("A", {"rice": 500.0}, coupons=coupons, delivery_fee=80.0, threshold=450.0)
    # P20: 400 + 80 = 480; FLAT50: 450 + 0 = 450 -> FLAT50 wins
    assert price_cart(q2) == (500.0, "FLAT50", 50.0, 0.0, 450.0)


def test_sites_missing_items_are_not_ranked_or_used_as_baseline():
    results = optimize([
        quote("A", {"rice": 100.0}),
        quote("B", {"rice": 80.0}),
        quote("Cheap", {"rice": 10.0}, missing=["sugar"]),
    ])
    r = by_site(results)
    assert r["Cheap"].rank is None and not r["Cheap"].complete
    assert r["B"].rank == 1 and r["B"].savings_pct == 20.0


def test_no_complete_site_yields_no_ranking():
    results = optimize([quote("A", {}, missing=["x"])])
    assert results[0].rank is None


def test_unitless_count_matches_items_sold_per_pack():
    items = [ListItem(item="bread", quantity=2, unit="pcs")]
    quotes = [s.quote(items) for s in default_mock_sources()]
    assert all(not q.missing_items for q in quotes)
    assert {q.site: q.items[0].line_total for q in quotes}["ValueStore"] == 80.0


def test_mock_sources_example_cart():
    items = [ListItem(item="sugar", quantity=2, unit="kg"), ListItem(item="rice", quantity=5, unit="kg")]
    r = by_site(optimize([s.quote(items) for s in default_mock_sources()]))
    # QuickMart: 96 + 360 = 456, below QUICK10 min and free-delivery threshold -> 456 + 30
    assert r["QuickMart"].total == 486.0 and r["QuickMart"].coupon_code is None
    # FreshBuy: 430 - 15% of rice (51) = 379 + 40 delivery
    assert (r["FreshBuy"].coupon_code, r["FreshBuy"].total) == ("STAPLES15", 419.0)
    # ValueStore: 84 + 300 + 25 delivery
    assert r["ValueStore"].total == 409.0 and r["ValueStore"].rank == 1
    assert r["ValueStore"].savings_pct == pytest.approx(round(77 / 486 * 100, 1))
