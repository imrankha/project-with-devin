"""optimize: deterministic cart costing and ranking across sites (no LLM)."""
from .models import Coupon, SiteComparison, SiteQuote
from .price_sources.mock import canonical_item


def _r(x: float) -> float:
    return round(x + 0.0, 2)


def coupon_discount(coupon: Coupon, quote: SiteQuote, subtotal: float) -> float:
    if subtotal < coupon.min_cart_value:
        return 0.0
    if coupon.applicable_items is None:
        eligible = subtotal
    else:
        allowed = {canonical_item(i) for i in coupon.applicable_items}
        eligible = sum(q.line_total for q in quote.items if canonical_item(q.item) in allowed)
    if eligible <= 0:
        return 0.0
    discount = eligible * coupon.value / 100 if coupon.kind == "percent" else coupon.value
    if coupon.max_discount is not None:
        discount = min(discount, coupon.max_discount)
    return _r(min(discount, eligible))


def delivery_fee(quote: SiteQuote, amount_after_discount: float) -> float:
    if quote.free_delivery_threshold is not None and amount_after_discount >= quote.free_delivery_threshold:
        return 0.0
    return quote.delivery_fee


def price_cart(quote: SiteQuote) -> tuple[float, str | None, float, float, float]:
    """Return (subtotal, coupon_code, discount, delivery, total), picking the single coupon
    (coupons don't stack) that minimizes the final total, delivery included."""
    subtotal = _r(sum(q.line_total for q in quote.items))
    best: tuple[str | None, float] = (None, 0.0)
    best_total = _r(subtotal + delivery_fee(quote, subtotal))
    for coupon in quote.coupons:
        discount = coupon_discount(coupon, quote, subtotal)
        if discount <= 0:
            continue
        total = _r(subtotal - discount + delivery_fee(quote, subtotal - discount))
        if total < best_total:
            best, best_total = (coupon.code, discount), total
    code, discount = best
    fee = delivery_fee(quote, subtotal - discount)
    return subtotal, code, discount, fee, best_total


def _fmt_pct(pct: float) -> str:
    return f"{pct:g}%"


def optimize(quotes: list[SiteQuote]) -> list[SiteComparison]:
    """Rank sites by final cart total. Only sites that stock every item are ranked and
    compared; savings % is measured against the most expensive complete cart."""
    priced = [(q, *price_cart(q)) for q in quotes]
    complete = [p for p in priced if not p[0].missing_items]
    complete.sort(key=lambda p: (p[5], p[0].site))
    max_total = max((p[5] for p in complete), default=0.0)
    priciest = next((p[0].site for p in complete if p[5] == max_total), None)

    results: list[SiteComparison] = []
    for rank, (q, subtotal, code, discount, fee, total) in enumerate(complete, start=1):
        saving = _r(max_total - total)
        pct = round(saving / max_total * 100, 1) if max_total > 0 else 0.0
        summary = f"Buy from {q.site} — save {_fmt_pct(pct)}"
        if saving > 0:
            summary += f" (₹{saving:.2f} less than {priciest})"
        results.append(
            SiteComparison(
                site=q.site, rank=rank, currency=q.currency, complete=True, missing_items=[],
                subtotal=subtotal, coupon_code=code, discount=discount, delivery_fee=fee,
                total=total, savings_amount=saving, savings_pct=pct, summary=summary,
            )
        )
    for q, subtotal, code, discount, fee, total in priced:
        if not q.missing_items:
            continue
        results.append(
            SiteComparison(
                site=q.site, rank=None, currency=q.currency, complete=False,
                missing_items=q.missing_items, subtotal=subtotal, coupon_code=code,
                discount=discount, delivery_fee=fee, total=total, savings_amount=0.0,
                savings_pct=0.0, summary=f"{q.site} — not ranked, missing: {', '.join(q.missing_items)}",
            )
        )
    return results
