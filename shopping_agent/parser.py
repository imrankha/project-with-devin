"""parse_list: turn free-text shopping input into structured ListItems."""
import logging
import re
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from .models import ListItem
from .units import normalize_unit

log = logging.getLogger(__name__)

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You convert grocery shopping lists into JSON. Respond with JSON only, shaped as "
            '{{"items": [{{"item": str, "quantity": number, "unit": str}}]}}. '
            "Use a lowercase singular item name (e.g. 'egg', 'toor dal'). "
            "unit must be one of: kg, g, l, ml, pcs, dozen, pack. "
            "If no unit is given for a countable item use 'pcs'; if no quantity is given use 1. "
            "Do not invent items that are not in the input.",
        ),
        ("human", "{text}"),
    ]
)


class ParseError(ValueError):
    pass


def _normalize(raw_items: list[dict[str, Any]]) -> list[ListItem]:
    if not raw_items:
        raise ParseError("No items found in input")
    items: list[ListItem] = []
    for raw in raw_items:
        unit = normalize_unit(str(raw.get("unit", "pcs")))
        if unit is None:
            raise ParseError(f"Unsupported unit {raw.get('unit')!r} for item {raw.get('item')!r}")
        try:
            items.append(
                ListItem(
                    item=" ".join(str(raw.get("item", "")).lower().split()),
                    quantity=float(raw.get("quantity", 1)),
                    unit=unit,
                )
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ParseError(f"Invalid item {raw!r}: {exc}") from exc
    return items


def parse_with_llm(text: str, llm: BaseChatModel) -> list[ListItem]:
    chain = PROMPT | llm | JsonOutputParser()
    try:
        result = chain.invoke({"text": text})
    except OutputParserException as exc:
        raise ParseError(f"LLM returned invalid JSON: {exc}") from exc
    raw_items = result.get("items") if isinstance(result, dict) else result
    if not isinstance(raw_items, list):
        raise ParseError(f"LLM returned unexpected payload: {result!r}")
    return _normalize(raw_items)


_NUM = r"(?P<qty>\d+(?:\.\d+)?)"
_QTY_FIRST = re.compile(rf"^{_NUM}\s*(?P<unit>[a-zA-Z.]+)?\s+(?:of\s+)?(?P<name>.+)$")
_NAME_FIRST = re.compile(rf"^(?P<name>.+?)\s*[-:]?\s+{_NUM}\s*(?P<unit>[a-zA-Z.]+)?$")


def parse_rule_based(text: str) -> list[ListItem]:
    """Offline fallback used when no LLM is configured. Handles 'sugar 2 kg' and '2 kg sugar' styles."""
    raw_items: list[dict[str, Any]] = []
    for chunk in re.split(r"[,;\n]|\band\b", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, qty, unit = chunk, 1.0, "pcs"
        if m := _NAME_FIRST.match(chunk):
            # "sugar 2 kg"; an unknown trailing unit is passed through so validation rejects it
            name, qty, unit = m.group("name"), float(m.group("qty")), m.group("unit") or "pcs"
        elif m := _QTY_FIRST.match(chunk):
            # "2 kg sugar" or "6 eggs" (token after the number is part of the name, not a unit)
            name, qty = m.group("name"), float(m.group("qty"))
            raw_unit = m.group("unit")
            if raw_unit and normalize_unit(raw_unit):
                unit = raw_unit
            elif raw_unit:
                name = f"{raw_unit} {name}"
        raw_items.append({"item": name, "quantity": qty, "unit": unit})
    if not raw_items:
        raise ParseError("No items found in input")
    return _normalize(raw_items)


def parse_shopping_list(text: str, llm: BaseChatModel | None) -> list[ListItem]:
    if llm is None:
        log.warning("No LLM configured (OPENAI_API_KEY unset); using rule-based parser")
        return parse_rule_based(text)
    return parse_with_llm(text, llm)


def default_llm() -> BaseChatModel | None:
    from .config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
