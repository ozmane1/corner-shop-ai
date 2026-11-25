"""Dispatcher Lambda: reads the FIFO queue and handles each shop's messages in order.

Part 2: store every inbound message under its shop (the raw event log the forecasting model learns from later).
Part 3 adds the Strands supervisor agent on AgentCore Runtime here and the WhatsApp reply.
Failures are reported per message (partial batch response); after 3 tries a message goes to the DLQ.
"""
import json
import logging
import os
from datetime import datetime, timezone

import boto3

from shared import keys

log = logging.getLogger()
log.setLevel(logging.INFO)
_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def store(item: dict) -> None:
    msg = item["message"]
    ts = int(msg.get("timestamp", "0")) or int(datetime.now(timezone.utc).timestamp())
    iso = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table().put_item(
        Item={**keys.message(item["shop_id"], iso, msg["id"]), "shop_id": item["shop_id"], "from": msg.get("from", ""),
              "type": msg.get("type", ""), "text": (msg.get("text") or {}).get("body", ""), "raw": json.dumps(msg)},
        ConditionExpression="attribute_not_exists(pk)",   # idempotent: a redelivery never writes twice
    )


def handler(event, context):
    records = event.get("Records", [])
    for n, record in enumerate(records):
        try:
            store(json.loads(record["body"]))
        except table().meta.client.exceptions.ConditionalCheckFailedException:
            pass                                           # already stored: fine
        except Exception:                                  # noqa: BLE001  report, retry, then DLQ
            log.exception("failed %s", record.get("messageId"))
            # FIFO: this message AND everything after it go back to the queue, so order is kept
            return {"batchItemFailures": [{"itemIdentifier": r["messageId"]} for r in records[n:]]}
    return {"batchItemFailures": []}
