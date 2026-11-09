"""A tiny local login + checkout site the Playwright agent runs against in the demo."""
import secrets
from html import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import get_settings

router = APIRouter()
_sessions: dict[str, str] = {}
COOKIE = "mockshop_session"


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>body{{font-family:sans-serif;max-width:480px;margin:40px auto}}
label{{display:block;margin:12px 0 4px}}input,textarea{{width:100%;padding:6px}}
button{{margin-top:16px;padding:8px 16px}}.err{{color:#b00}}</style></head>
<body><h1>{escape(title)}</h1>{body}</body></html>"""
    )


def _credentials_ok(username: str, password: str) -> bool:
    s = get_settings()
    if s.checkout_username and s.checkout_password:
        return secrets.compare_digest(username, s.checkout_username) and secrets.compare_digest(
            password, s.checkout_password
        )
    return bool(username and password)


def _logged_in(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    return bool(token and token in _sessions)


def _login_form(site: str, error: str = "") -> HTMLResponse:
    err = f'<p id="login-error" class="err">{escape(error)}</p>' if error else ""
    return _page(
        f"{site} — Sign in",
        f"""{err}<form id="login-form" method="post" action="login">
<label>Username<input name="username" autocomplete="username"></label>
<label>Password<input name="password" type="password" autocomplete="current-password"></label>
<button type="submit">Sign in</button></form>""",
    )


@router.get("/{site}/login")
def login_page(site: str):
    return _login_form(site)


@router.post("/{site}/login")
def login(site: str, username: str = Form(""), password: str = Form("")):
    if not _credentials_ok(username, password):
        return _login_form(site, "Invalid username or password")
    token = secrets.token_urlsafe(16)
    _sessions[token] = username
    resp = RedirectResponse(f"/mock-shop/{site}/checkout", status_code=303)
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", path=f"/mock-shop/{site}")
    return resp


@router.get("/{site}/checkout")
def checkout_page(site: str, request: Request):
    if not _logged_in(request):
        return RedirectResponse(f"/mock-shop/{site}/login", status_code=303)
    return _page(
        f"{site} — Checkout",
        """<form id="checkout-form" method="post" action="checkout">
<label>First name<input name="first_name" required></label>
<label>Last name<input name="last_name" required></label>
<label>Address<textarea name="address" rows="3" required></textarea></label>
<button type="submit">Continue to review</button></form>""",
    )


@router.post("/{site}/checkout")
def submit_checkout(
    site: str,
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    address: str = Form(...),
):
    if not _logged_in(request):
        return RedirectResponse(f"/mock-shop/{site}/login", status_code=303)
    return _page(
        f"{site} — Review order",
        f"""<div id="order-review"><p>Ship to: <strong>{escape(first_name)} {escape(last_name)}</strong></p>
<p>{escape(address)}</p></div>
<p>Payment is pending human approval in the shopping agent.</p>
<button disabled>Place order</button>""",
    )
