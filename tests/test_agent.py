"""The agent's contract, without calling a model (the real-model check is scripts/eval_agent.py)."""
import os
import sys
from unittest import mock

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
import main  # noqa: E402
import shop_agent  # noqa: E402
from shop_agent import Item, Understood  # noqa: E402


def fake_agent(result: Understood):
    agent = mock.Mock()
    agent.return_value.structured_output = result
    return agent


def test_understand_asks_for_the_typed_result():
    want = Understood(intent="sale", items=[Item(product="bread", quantity=3)], language="en", reply="Got it: 3 bread.")
    agent = fake_agent(want)
    assert shop_agent.understand("  sold 3 bread ", agent) == want
    agent.assert_called_once_with("sold 3 bread", structured_output_model=Understood)


def test_long_messages_are_cut():
    agent = fake_agent(Understood(intent="other", language="en", reply="ok"))
    shop_agent.understand("x" * 5000, agent)
    assert len(agent.call_args.args[0]) == 1000


def test_only_known_intents_and_languages():
    with pytest.raises(ValidationError):
        Understood(intent="delete_everything", language="en", reply="")
    with pytest.raises(ValidationError):
        Understood(intent="sale", language="de", reply="")


def test_entrypoint_returns_json_and_skips_empty_text():
    assert main.invoke({"text": "   "})["reply"] == ""
    want = Understood(intent="credit", customer="Karim", amount_mad=40, language="en", reply="Karim owes 40 dh.")
    with mock.patch.object(main, "understand", return_value=want):
        out = main.invoke({"text": "Karim owes 40 dh"})
    assert out["intent"] == "credit" and out["amount_mad"] == 40


def test_model_is_the_eu_haiku_by_default():
    assert shop_agent.MODEL_ID.startswith("eu.anthropic.claude-haiku")
