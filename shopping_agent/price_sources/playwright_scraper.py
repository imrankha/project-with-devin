"""Adapter stub for sites without an API: scrape search results with Playwright.

TODO(real-source): implement per-site selectors and wire into `graph.build_graph(price_sources=...)`.
Respect each site's Terms of Service and robots.txt before scraping; prefer an official API or
affiliate/partner feed where one exists.
"""
from dataclasses import dataclass

from ..models import ListItem, SiteQuote
from .base import PriceSource


@dataclass
class SiteSelectors:
    search_url: str  # e.g. "https://example-grocer.test/search?q={query}"
    product_card: str  # CSS selector for one result
    product_name: str
    product_price: str
    pack_size: str  # e.g. "1 kg" / "500 g"; needed to derive price per base unit
    coupons_url: str | None = None
    coupon_card: str | None = None


class PlaywrightScraperSource(PriceSource):
    def __init__(self, name: str, selectors: SiteSelectors, headless: bool = True):
        self.name = name
        self.selectors = selectors
        self.headless = headless

    def quote(self, items: list[ListItem]) -> SiteQuote:
        # TODO(real-source):
        #  1. with sync_playwright() as p: browser = p.chromium.launch(headless=self.headless)
        #  2. for each item: page.goto(search_url.format(query=item.item)); pick best-matching card
        #  3. parse price + pack size -> unit price per base unit (see units.convert)
        #  4. scrape coupons page into models.Coupon; set delivery fee/threshold
        #  5. add caching + rate limiting; never log in or add to cart from a price source
        raise NotImplementedError(f"Playwright scraper for {self.name} is not implemented yet")
