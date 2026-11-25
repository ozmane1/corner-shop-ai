import json

import boto3

from conftest import VERIFY, wa_payload, webhook_event


def queued(q):
    out = boto3.client("sqs").receive_message(QueueUrl=q, MaxNumberOfMessages=10, AttributeNames=["All"])
    return out.get("Messages", [])


def test_meta_verification_handshake(aws):
    from ingest.handler import handler
    ok = handler({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": {
        "hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"}}, None)
    bad = handler({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": {
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"}}, None)
    assert (ok["statusCode"], ok["body"]) == (200, "12345")
    assert bad["statusCode"] == 403


def test_valid_message_is_queued_per_shop(aws):
    from ingest.handler import handler
    r = handler(webhook_event(wa_payload("wamid.A")), None)
    msgs = queued(aws["queue"])
    assert r["statusCode"] == 200 and len(msgs) == 1
    body = json.loads(msgs[0]["Body"])
    assert body["shop_id"] == "casa-01" and body["message"]["text"]["body"] == "how much milk is left?"
    assert msgs[0]["Attributes"]["MessageGroupId"] == "casa-01"


def test_bad_or_missing_signature_is_rejected(aws):
    from ingest.handler import handler
    assert handler(webhook_event(wa_payload("wamid.B"), secret="attacker"), None)["statusCode"] == 401
    assert handler(webhook_event(wa_payload("wamid.B"), signature="nope"), None)["statusCode"] == 401
    assert queued(aws["queue"]) == []


def test_meta_retry_is_deduplicated(aws):
    from ingest.handler import handler
    handler(webhook_event(wa_payload("wamid.C")), None)
    handler(webhook_event(wa_payload("wamid.C")), None)          # Meta retries the same message
    assert len(queued(aws["queue"])) == 1


def test_unknown_number_is_dropped_but_answered(aws):
    from ingest.handler import handler
    r = handler(webhook_event(wa_payload("wamid.D", phone_number_id="999")), None)
    assert r["statusCode"] == 200 and queued(aws["queue"]) == []


def test_status_updates_are_ignored(aws):
    from ingest.handler import handler
    payload = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "111"}, "statuses": [{"id": "x"}]}}]}]}
    assert handler(webhook_event(payload), None)["statusCode"] == 200
    assert queued(aws["queue"]) == []
