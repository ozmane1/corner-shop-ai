import json
from unittest import mock

from boto3.dynamodb.conditions import Key


def record(n, wamid, shop="casa-01"):
    return {"messageId": f"m{n}", "body": json.dumps({"shop_id": shop, "phone_number_id": "111", "message": {
        "id": wamid, "from": "212600000000", "timestamp": "1764100000", "type": "text", "text": {"body": "milk?"}}})}


def stored(table, shop="casa-01"):
    return table.query(KeyConditionExpression=Key("pk").eq(f"SHOP#{shop}") & Key("sk").begins_with("MSG#"))["Items"]


def test_messages_are_stored_under_their_shop(aws):
    from dispatcher.handler import handler
    assert handler({"Records": [record(1, "wamid.A"), record(2, "wamid.B")]}, None) == {"batchItemFailures": []}
    items = stored(aws["table"])
    assert {i["sk"].split("#")[-1] for i in items} == {"wamid.A", "wamid.B"}
    assert items[0]["sk"].startswith("MSG#2025-11-25T")


def test_redelivery_never_writes_twice(aws):
    from dispatcher.handler import handler
    handler({"Records": [record(1, "wamid.A")]}, None)
    assert handler({"Records": [record(1, "wamid.A")]}, None) == {"batchItemFailures": []}
    assert len(stored(aws["table"])) == 1


def test_failure_returns_it_and_everything_after_it(aws):
    from dispatcher import handler as d
    real = d.store
    calls = []

    def flaky(item):
        calls.append(item["message"]["id"])
        if item["message"]["id"] == "wamid.B":
            raise RuntimeError("boom")
        real(item)

    with mock.patch.object(d, "store", flaky):
        out = d.handler({"Records": [record(1, "wamid.A"), record(2, "wamid.B"), record(3, "wamid.C")]}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "m2"}, {"itemIdentifier": "m3"}]}   # order kept
    assert calls == ["wamid.A", "wamid.B"]
