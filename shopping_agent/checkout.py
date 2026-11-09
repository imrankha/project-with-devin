"""checkout: browser-automation agent that logs in and fills the checkout form.

It stops on the order-review page; the order is only placed after human approval
in the payment step.
"""
import logging
import re
import uuid
from pathlib import Path
from typing import Protocol

from .models import CheckoutResult, ShippingDetails

log = logging.getLogger(__name__)


class CheckoutAgent(Protocol):
    def run(self, site: str, items: list[dict], shipping: ShippingDetails) -> CheckoutResult: ...


class SkipCheckoutAgent:
    def run(self, site: str, items: list[dict], shipping: ShippingDetails) -> CheckoutResult:
        return CheckoutResult(site=site, status="skipped", detail="CHECKOUT_MODE=skip")


def site_slug(site: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", site.lower()).strip("-")


class PlaywrightCheckoutAgent:
    """Drives the (mock) shop's login + checkout pages.

    TODO(real-source): real sites need per-site selectors, add-to-cart for each item,
    CAPTCHA/2FA handling (hand back to the human), and stored-session reuse.
    """

    def __init__(
        self,
        base_url: str,
        username: str | None,
        password: str | None,
        headless: bool = True,
        screenshot_dir: str = "artifacts",
        timeout_ms: int = 15_000,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.timeout_ms = timeout_ms

    def run(self, site: str, items: list[dict], shipping: ShippingDetails) -> CheckoutResult:
        if not self.username or not self.password:
            return CheckoutResult(site=site, status="failed",
                                  detail="CHECKOUT_USERNAME / CHECKOUT_PASSWORD are not set")
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        slug = site_slug(site)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    page.goto(f"{self.base_url}/{slug}/checkout")

                    if page.locator("#login-form").count():
                        page.fill("input[name=username]", self.username)
                        page.fill("input[name=password]", self.password)
                        page.click("#login-form button[type=submit]")
                        page.wait_for_selector("#checkout-form, #login-error")
                        if page.locator("#login-error").count():
                            return CheckoutResult(site=site, status="failed", detail="Login rejected")

                    page.fill("input[name=first_name]", shipping.first_name)
                    page.fill("input[name=last_name]", shipping.last_name)
                    page.fill("textarea[name=address]", shipping.address)
                    page.click("#checkout-form button[type=submit]")
                    page.wait_for_selector("#order-review")

                    Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
                    shot = str(Path(self.screenshot_dir) / f"checkout-{slug}-{uuid.uuid4().hex[:12]}.png")
                    page.screenshot(path=shot, full_page=True)
                    review = page.inner_text("#order-review")
                finally:
                    browser.close()
        except PlaywrightError as exc:
            log.exception("Checkout automation failed for %s", site)
            return CheckoutResult(site=site, status="failed", detail=str(exc).splitlines()[0])

        expected = f"{shipping.first_name} {shipping.last_name}"
        if expected not in review:
            return CheckoutResult(site=site, status="failed", detail="Review page did not show shipping details")
        return CheckoutResult(site=site, status="ready_for_payment",
                              detail="Logged in and filled shipping details", screenshot_path=shot)


def default_checkout_agent() -> CheckoutAgent:
    from .config import get_settings

    s = get_settings()
    if s.checkout_mode == "skip":
        return SkipCheckoutAgent()
    return PlaywrightCheckoutAgent(
        base_url=s.checkout_base_url,
        username=s.checkout_username,
        password=s.checkout_password,
        headless=s.checkout_headless,
    )
