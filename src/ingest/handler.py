"""Ingest Lambda: the WhatsApp Cloud API webhook (behind API Gateway HTTP API).

GET  /webhook  Meta's subscription check: echo hub.challenge when hub.verify_token matches.
POST /webhook  For every inbound message: verify Meta's X-Hub-Signature-256, drop duplicates (Meta retries),
               find the shop that owns the receiving number, queue it on SQS FIFO (ordered per shop), answer 200 fast.
No AI here: this function must stay small, fast and boring. The agents read from the queue (dispatcher).
"""
import hashlib
import hmac
import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

from shared import keys

log = logging.getLogger()
log.setLevel(logging.INFO)

TABLE = os.environ.get("TABLE_NAME", "")
QUEUE_URL = os.environ.get("QUEUE_URL", "")
SECRET_ID = os.environ.get("SECRET_ID", "")

_ddb = _sqs = _secrets = None
_secret_cache: dict = {}


def clients():
    global _ddb, _sqs, _secrets
    if _ddb is None:
        _ddb = boto3.resource("dynamodb").Table(TABLE)
        _sqs = boto3.client("sqs")
        _secrets = boto3.client("secretsmanager")
    return _ddb, _sqs, _secrets


def secret() -> dict:
    """{"app_secret": ..., "verify_token": ...}, cached for 5 minutes (rotation-friendly)."""
    if not _secret_cache or time.time() - _secret_cache["at"] > 300:
        raw = clients()[2].get_secret_value(SecretId=SECRET_ID)["SecretString"]
        _secret_cache.update(value=json.loads(raw), at=time.time())
    return _secret_cache["value"]


def resp(code: int, body: str = "") -> dict:
    return {"statusCode": code, "headers": {"content-type": "text/plain"}, "body": body}


def valid_signature(body: bytes, header: str, app_secret: str) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def first_seen(wamid: str) -> bool:
    """Conditional put: True only the first time this message id arrives."""
    try:
        clients()[0].put_item(Item={**keys.dedup(wamid), "ttl": int(time.time()) + keys.DEDUP_TTL_SECONDS},
                              ConditionExpression="attribute_not_exists(pk)")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def shop_for(phone_number_id: str):
    item = clients()[0].get_item(Key=keys.phone(phone_number_id)).get("Item")
    return item["shop_id"] if item else None


def messages(payload: dict):
    """Yield (phone_number_id, message) for every inbound message in a webhook payload (statuses are skipped)."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            pid = value.get("metadata", {}).get("phone_number_id")
            for msg in value.get("messages", []) or []:
                yield pid, msg


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    if method == "GET":
        q = event.get("queryStringParameters") or {}
        if q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), secret()["verify_token"]):
            return resp(200, q.get("hub.challenge", ""))
        return resp(403, "forbidden")

    raw = event.get("body") or ""
    body = raw.encode() if not event.get("isBase64Encoded") else __import__("base64").b64decode(raw)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if not valid_signature(body, headers.get("x-hub-signature-256", ""), secret()["app_secret"]):
        log.warning("bad signature")
        return resp(401, "bad signature")

    queued = 0
    for pid, msg in messages(json.loads(body or "{}")):
        wamid = msg.get("id")
        if not wamid or not first_seen(wamid):
            continue
        shop_id = shop_for(pid)
        if not shop_id:
            log.warning("message for unknown number %s dropped", pid)
            continue
        clients()[1].send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({"shop_id": shop_id, "phone_number_id": pid, "message": msg}),
            MessageGroupId=shop_id,            # FIFO order per shop, shops run in parallel
            MessageDeduplicationId=wamid,      # second dedupe layer (SQS keeps 5 minutes)
        )
        queued += 1
    log.info("queued %d message(s)", queued)
    return resp(200, "ok")                     # always fast: Meta retries on slow or non-200 answers
