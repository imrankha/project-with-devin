"""Adapter stub for sites that expose a (partner) HTTP API.

TODO(real-source): map the provider's catalogue/pricing/coupon endpoints onto SiteQuote.
Read credentials from environment variables (never hard-code them).
"""
import os

from ..models import ListItem, SiteQuote
from .base import PriceSource


class HttpApiPriceSource(PriceSource):
    def __init__(self, name: str, base_url: str, api_key_env: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env

    def _api_key(self) -> str:
        key = os.getenv(self.api_key_env)
        if not key:
            raise RuntimeError(f"{self.api_key_env} is not set")
        return key

    def quote(self, items: list[ListItem]) -> SiteQuote:
        # TODO(real-source):
        #  1. httpx.get(f"{self.base_url}/products/search", params={"q": item.item},
        #               headers={"Authorization": f"Bearer {self._api_key()}"})
        #  2. normalize price/pack size into ItemQuote (price per base unit)
        #  3. fetch active coupons + delivery terms
        raise NotImplementedError(f"API source for {self.name} is not implemented yet")
