import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    orders_db_path: str
    checkpoint_db_path: str
    checkout_mode: str
    checkout_base_url: str
    checkout_headless: bool
    checkout_username: str | None
    checkout_password: str | None
    host: str
    port: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        orders_db_path=os.getenv("ORDERS_DB_PATH", "data/orders.sqlite"),
        checkpoint_db_path=os.getenv("CHECKPOINT_DB_PATH", "data/checkpoints.sqlite"),
        checkout_mode=os.getenv("CHECKOUT_MODE", "playwright").lower(),
        checkout_base_url=os.getenv("CHECKOUT_BASE_URL", "http://localhost:5000/mock-shop"),
        checkout_headless=_bool(os.getenv("CHECKOUT_HEADLESS"), True),
        checkout_username=os.getenv("CHECKOUT_USERNAME") or None,
        checkout_password=os.getenv("CHECKOUT_PASSWORD") or None,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
