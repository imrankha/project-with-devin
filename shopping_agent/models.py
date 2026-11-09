from typing import Literal

from pydantic import BaseModel, Field

Unit = Literal["kg", "g", "l", "ml", "pcs", "dozen", "pack"]


class ListItem(BaseModel):
    item: str = Field(min_length=1, description="Normalized item name, lowercase, singular, e.g. 'sugar'")
    quantity: float = Field(gt=0, description="Numeric quantity")
    unit: Unit = Field(description="Unit of measure")


class ShoppingList(BaseModel):
    items: list[ListItem]


class Coupon(BaseModel):
    code: str
    description: str
    kind: Literal["percent", "flat"]
    value: float = Field(gt=0)
    min_cart_value: float = 0.0
    max_discount: float | None = None
    # Restrict a coupon to specific items; None means the whole cart.
    applicable_items: list[str] | None = None


class ItemQuote(BaseModel):
    item: str
    requested_quantity: float
    requested_unit: str
    unit_price: float = Field(description="Price per base_unit")
    base_unit: str
    line_total: float


class SiteQuote(BaseModel):
    site: str
    currency: str = "INR"
    items: list[ItemQuote]
    missing_items: list[str] = []
    coupons: list[Coupon] = []
    delivery_fee: float = 0.0
    free_delivery_threshold: float | None = None


class SiteComparison(BaseModel):
    site: str
    rank: int | None
    currency: str
    complete: bool
    missing_items: list[str]
    subtotal: float
    coupon_code: str | None
    discount: float
    delivery_fee: float
    total: float
    savings_amount: float
    savings_pct: float
    summary: str


class ShippingDetails(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    address: str = Field(min_length=1)


class CheckoutResult(BaseModel):
    site: str
    status: Literal["ready_for_payment", "skipped", "failed"]
    detail: str = ""
    screenshot_path: str | None = None
