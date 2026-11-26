import json
from unittest import mock

import boto3
import pytest
from boto3.dynamodb.conditions import Key

UNDERSTOOD = {"intent": "sale", "items": [{"product": "milk", "quantity": 1.0, "unit": None}], "customer": None,
              "amount_mad": None, "language": "en", "reply": "Got it: 1 milk sold."}


def record(n, wamid, shop="casa-01", text="sold 1 milk", kind="text"):
    msg = {"id": wamid, "from": "212600000000", "timestamp": "1764100000", "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    return {"messageId": f"m{n}", "body": json.dumps({"shop_id": shop, "phone_number_id": "111", "message": msg})}


def stored(table, shop="casa-01"):
    return table.query(KeyConditionExpression=Key("pk").eq(f"SHOP#{shop}") & Key("sk").begins_with("MSG#"))["Items"]


@pytest.fixture
def d(aws):
    from dispatcher import handler as d
    with mock.patch.object(d, "ask_agent", return_value=UNDERSTOOD) as agent, \
         mock.patch.object(d, "send_whatsapp") as send:
        d.agent_mock, d.send_mock = agent, send
        yield d


def set_token(token):
    boto3.client("secretsmanager").put_secret_value(SecretId="whatsapp", SecretString=json.dumps(
        {"app_secret": "x", "verify_token": "y", "access_token": token}))


def test_messages_are_understood_and_stored_under_their_shop(aws, d):
    assert d.handler({"Records": [record(1, "wamid.A"), record(2, "wamid.B")]}, None) == {"batchItemFailures": []}
    items = stored(aws["table"])
    assert {i["sk"].split("#")[-1] for i in items} == {"wamid.A", "wamid.B"}
    assert items[0]["sk"].startswith("MSG#2025-11-25T")
    assert items[0]["intent"] == "sale" and json.loads(items[0]["understood"])["items"][0]["product"] == "milk"


def test_without_a_whatsapp_token_the_reply_is_kept_not_sent(aws, d):
    d.handler({"Records": [record(1, "wamid.A")]}, None)
    assert stored(aws["table"])[0]["reply_status"] == "no_token"
    d.send_mock.assert_not_called()


def test_reply_is_sent_once_as_an_answer_to_the_message(aws, d):
    set_token("EAAtest")
    d.handler({"Records": [record(1, "wamid.A")]}, None)
    d.handler({"Records": [record(1, "wamid.A")]}, None)               # Meta/SQS redelivery
    d.send_mock.assert_called_once_with("111", "212600000000", "Got it: 1 milk sold.", "wamid.A", "EAAtest")
    assert d.agent_mock.call_count == 1                                  # the agent is not asked twice either
    assert stored(aws["table"])[0]["reply_status"] == "sent"


def test_failed_send_is_retried_without_asking_the_agent_again(aws, d):
    set_token("EAAtest")
    d.send_mock.side_effect = [OSError("meta down"), None]
    assert d.handler({"Records": [record(1, "wamid.A")]}, None) == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    assert stored(aws["table"])[0]["reply_status"] == "pending"
    assert d.handler({"Records": [record(1, "wamid.A")]}, None) == {"batchItemFailures": []}
    assert d.agent_mock.call_count == 1 and d.send_mock.call_count == 2
    assert stored(aws["table"])[0]["reply_status"] == "sent"


def test_non_text_messages_are_stored_without_the_agent(aws, d):
    d.handler({"Records": [record(1, "wamid.IMG", kind="image")]}, None)
    d.agent_mock.assert_not_called()
    assert stored(aws["table"])[0]["reply_status"] == "none"


def test_failure_returns_it_and_everything_after_it(aws, d):
    calls = []

    def flaky(shop_id, sender, text):
        calls.append(text)
        if text == "B":
            raise RuntimeError("agent down")
        return UNDERSTOOD

    d.agent_mock.side_effect = flaky
    out = d.handler({"Records": [record(1, "wamid.A", text="A"), record(2, "wamid.B", text="B"),
                                 record(3, "wamid.C", text="C")]}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "m2"}, {"itemIdentifier": "m3"}]}   # order kept
    assert calls == ["A", "B"]
    assert len(stored(aws["table"])) == 1                                # nothing half-written for B


def test_session_id_is_long_enough_and_hides_the_phone_number(aws):
    from dispatcher import handler as d
    client = mock.Mock()
    client.invoke_agent_runtime.return_value = {"response": mock.Mock(read=lambda: json.dumps(UNDERSTOOD).encode())}
    with mock.patch.object(d, "_agent", client), mock.patch.dict("os.environ", AGENT_RUNTIME_ARN="arn:x"):
        assert d.ask_agent("casa-01", "212600000000", "sold 1 milk") == UNDERSTOOD
    session = client.invoke_agent_runtime.call_args.kwargs["runtimeSessionId"]
    assert len(session) >= 33 and "212600000000" not in session
