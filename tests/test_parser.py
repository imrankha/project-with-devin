import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from shopping_agent.models import ListItem
from shopping_agent.parser import ParseError, parse_rule_based, parse_shopping_list, parse_with_llm


def _as_tuples(items):
    return [(i.item, i.quantity, i.unit) for i in items]


def test_rule_based_parses_example_input():
    items = parse_rule_based("sugar 2 kg, rice 5 kg")
    assert all(isinstance(i, ListItem) for i in items)
    assert _as_tuples(items) == [("sugar", 2.0, "kg"), ("rice", 5.0, "kg")]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2 kg sugar", [("sugar", 2.0, "kg")]),
        ("Milk 1.5 litres; 500 g Toor Dal", [("milk", 1.5, "l"), ("toor dal", 500.0, "g")]),
        ("6 eggs and bread", [("eggs", 6.0, "pcs"), ("bread", 1.0, "pcs")]),
        ("atta 10kgs\nonion 2 kilo", [("atta", 10.0, "kg"), ("onion", 2.0, "kg")]),
    ],
)
def test_rule_based_formats(text, expected):
    assert _as_tuples(parse_rule_based(text)) == expected


def test_llm_output_is_validated_and_normalized():
    payload = {"items": [{"item": "Sugar", "quantity": 2, "unit": "kgs"},
                         {"item": "rice", "quantity": "5", "unit": "KG"}]}
    llm = FakeListChatModel(responses=[f"```json\n{json.dumps(payload)}\n```"])
    items = parse_with_llm("sugar 2 kg, rice 5 kg", llm)
    assert _as_tuples(items) == [("sugar", 2.0, "kg"), ("rice", 5.0, "kg")]
    for item in items:
        assert set(item.model_dump()) == {"item", "quantity", "unit"}


@pytest.mark.parametrize(
    "bad_item",
    [
        {"item": "sugar", "quantity": 2, "unit": "bushel"},
        {"item": "sugar", "quantity": 0, "unit": "kg"},
        {"item": "", "quantity": 1, "unit": "kg"},
    ],
)
def test_llm_output_rejects_invalid_items(bad_item):
    llm = FakeListChatModel(responses=[json.dumps({"items": [bad_item]})])
    with pytest.raises(ParseError):
        parse_with_llm("whatever", llm)


def test_llm_empty_list_is_rejected():
    llm = FakeListChatModel(responses=['{"items": []}'])
    with pytest.raises(ParseError):
        parse_with_llm("hello", llm)


def test_falls_back_to_rule_based_without_llm():
    assert _as_tuples(parse_shopping_list("salt 1 kg", llm=None)) == [("salt", 1.0, "kg")]


def test_empty_input_raises():
    with pytest.raises(ParseError):
        parse_rule_based(" , ")
