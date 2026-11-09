"""Static, realistic-looking data for three fake sites. Prices are INR per base unit."""
from dataclasses import dataclass, field

from ..models import Coupon, ItemQuote, ListItem, SiteQuote
from ..units import convert
from .base import PriceSource

ITEM_ALIASES = {
    "atta": "wheat flour",
    "flour": "wheat flour",
    "chawal": "rice",
    "basmati rice": "rice",
    "cheeni": "sugar",
    "doodh": "milk",
    "eggs": "egg",
    "dal": "toor dal",
    "tur dal": "toor dal",
    "oil": "sunflower oil",
    "cooking oil": "sunflower oil",
    "onions": "onion",
    "potatoes": "potato",
    "aloo": "potato",
    "tomatoes": "tomato",
    "tea": "tea powder",
}

# item -> (base_unit, {site: price per base unit}); None = out of stock
_CATALOG: dict[str, tuple[str, dict[str, float | None]]] = {
    "sugar": ("kg", {"QuickMart": 48.0, "FreshBuy": 45.0, "ValueStore": 42.0}),
    "rice": ("kg", {"QuickMart": 72.0, "FreshBuy": 68.0, "ValueStore": 60.0}),
    "wheat flour": ("kg", {"QuickMart": 52.0, "FreshBuy": 49.0, "ValueStore": 44.0}),
    "toor dal": ("kg", {"QuickMart": 165.0, "FreshBuy": 158.0, "ValueStore": 149.0}),
    "salt": ("kg", {"QuickMart": 28.0, "FreshBuy": 26.0, "ValueStore": 24.0}),
    "onion": ("kg", {"QuickMart": 45.0, "FreshBuy": 38.0, "ValueStore": 40.0}),
    "potato": ("kg", {"QuickMart": 35.0, "FreshBuy": 30.0, "ValueStore": 32.0}),
    "tomato": ("kg", {"QuickMart": 40.0, "FreshBuy": 36.0, "ValueStore": None}),
    "milk": ("l", {"QuickMart": 66.0, "FreshBuy": 64.0, "ValueStore": 62.0}),
    "sunflower oil": ("l", {"QuickMart": 155.0, "FreshBuy": 149.0, "ValueStore": 139.0}),
    "egg": ("pcs", {"QuickMart": 7.5, "FreshBuy": 7.0, "ValueStore": 6.5}),
    "bread": ("pack", {"QuickMart": 45.0, "FreshBuy": 42.0, "ValueStore": 40.0}),
    "butter": ("kg", {"QuickMart": 560.0, "FreshBuy": 540.0, "ValueStore": None}),
    "tea powder": ("kg", {"QuickMart": 520.0, "FreshBuy": 495.0, "ValueStore": 470.0}),
}

_SITE_TERMS: dict[str, dict] = {
    "QuickMart": {
        "delivery_fee": 30.0,
        "free_delivery_threshold": 499.0,
        "coupons": [
            Coupon(code="QUICK10", description="10% off orders above ₹500 (max ₹150)",
                   kind="percent", value=10, min_cart_value=500, max_discount=150),
        ],
    },
    "FreshBuy": {
        "delivery_fee": 40.0,
        "free_delivery_threshold": 699.0,
        "coupons": [
            Coupon(code="FRESH50", description="Flat ₹50 off orders above ₹300",
                   kind="flat", value=50, min_cart_value=300),
            Coupon(code="STAPLES15", description="15% off rice, wheat flour and toor dal",
                   kind="percent", value=15, applicable_items=["rice", "wheat flour", "toor dal"]),
        ],
    },
    "ValueStore": {
        "delivery_fee": 25.0,
        "free_delivery_threshold": None,
        "coupons": [
            Coupon(code="VALUE20", description="20% off orders above ₹1000 (max ₹250)",
                   kind="percent", value=20, min_cart_value=1000, max_discount=250),
        ],
    },
}


def canonical_item(name: str) -> str:
    name = " ".join(name.lower().split())
    return ITEM_ALIASES.get(name, name)


@dataclass
class MockPriceSource(PriceSource):
    name: str
    prices: dict[str, tuple[str, float]] = field(default_factory=dict)
    coupons: list[Coupon] = field(default_factory=list)
    delivery_fee: float = 0.0
    free_delivery_threshold: float | None = None

    def quote(self, items: list[ListItem]) -> SiteQuote:
        quotes: list[ItemQuote] = []
        missing: list[str] = []
        for li in items:
            entry = self.prices.get(canonical_item(li.item))
            qty = convert(li.quantity, li.unit, entry[0]) if entry else None
            if entry is None or qty is None:
                missing.append(li.item)
                continue
            base_unit, unit_price = entry
            quotes.append(
                ItemQuote(
                    item=canonical_item(li.item),
                    requested_quantity=li.quantity,
                    requested_unit=li.unit,
                    unit_price=unit_price,
                    base_unit=base_unit,
                    line_total=round(unit_price * qty, 2),
                )
            )
        return SiteQuote(
            site=self.name,
            items=quotes,
            missing_items=missing,
            coupons=list(self.coupons),
            delivery_fee=self.delivery_fee,
            free_delivery_threshold=self.free_delivery_threshold,
        )


def default_mock_sources() -> list[PriceSource]:
    sources: list[PriceSource] = []
    for site, terms in _SITE_TERMS.items():
        prices = {
            item: (unit, by_site[site])
            for item, (unit, by_site) in _CATALOG.items()
            if by_site.get(site) is not None
        }
        sources.append(MockPriceSource(name=site, prices=prices, **terms))
    return sources
