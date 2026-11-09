from abc import ABC, abstractmethod

from ..models import ListItem, SiteQuote


class PriceSource(ABC):
    """A grocery site that can price a shopping list.

    Implementations must be side-effect free: they only read prices and coupons.
    """

    name: str

    @abstractmethod
    def quote(self, items: list[ListItem]) -> SiteQuote:
        """Return per-item prices, items the site cannot supply, coupons and delivery terms."""
