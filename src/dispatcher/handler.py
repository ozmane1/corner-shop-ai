"""Dispatcher Lambda: reads the FIFO queue and handles each shop's messages in order.

For every inbound message:
  1. ask the agent on AgentCore Runtime what the owner meant (text messages only)
  2. store the message + what was understood + the reply under its shop (the event log the ML part learns from later)
  3. send the reply on WhatsApp, then mark it sent
A redelivered message never runs twice: an item that exists is not re-asked, a reply marked sent is not re-sent.
Failures are reported per message (partial batch response); after 3 tries a message goes to the DLQ.
"""
import hashlib
import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone

import boto3

from shared import keys

log = logging.getLogger()
log.setLevel(logging.INFO)
GRAPH = "https://graph.facebook.com/v27.0"           # same version as the webhook subscription in the Meta app
_table = _agent = _secrets = None
_secret_cache: dict = {}


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def access_token() -> str | None:
    """WhatsApp Cloud API token from Secrets Manager (cached 5 min); None until a Meta app is connected."""
    global _secrets
    if not os.environ.get("SECRET_ID"):
        return None
    if not _secret_cache or time.time() - _secret_cache["at"] > 300:
        _secrets = _secrets or boto3.client("secretsmanager")
        raw = _secrets.get_secret_value(SecretId=os.environ["SECRET_ID"])["SecretString"]
        _secret_cache.update(value=json.loads(raw), at=time.time())
    token = _secret_cache["value"].get("access_token", "")
    return token if token and token != "set-me" else None


def ask_agent(shop_id: str, sender: str, text: str) -> dict:
    """One message to the agent. Same session id per shop + sender, so a warm session is reused."""
    global _agent
    _agent = _agent or boto3.client("bedrock-agentcore")
    session = hashlib.sha256(f"{shop_id}:{sender}".encode()).hexdigest()       # 64 chars, no phone number in it
    r = _agent.invoke_agent_runtime(agentRuntimeArn=os.environ["AGENT_RUNTIME_ARN"], runtimeSessionId=session,
                                    payload=json.dumps({"text": text}).encode())
    return json.loads(r["response"].read())


def send_whatsapp(phone_number_id: str, to: str, body: str, reply_to: str, token: str) -> None:
    req = urllib.request.Request(
        f"{GRAPH}/{phone_number_id}/messages", method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps({"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body},
                         "context": {"message_id": reply_to}}).encode())
    with urllib.request.urlopen(req, timeout=10) as r:                  # raises on 4xx/5xx -> retried, then DLQ
        r.read()


def key_for(item: dict) -> dict:
    msg = item["message"]
    ts = int(msg.get("timestamp", "0")) or int(datetime.now(timezone.utc).timestamp())
    iso = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return keys.message(item["shop_id"], iso, msg["id"])


def handle(item: dict) -> None:
    msg, key = item["message"], key_for(item)
    saved = table().get_item(Key=key).get("Item")
    if saved is None:
        text = (msg.get("text") or {}).get("body", "")
        understood = ask_agent(item["shop_id"], msg.get("from", ""), text) if text.strip() else None
        saved = {**key, "shop_id": item["shop_id"], "from": msg.get("from", ""), "type": msg.get("type", ""),
                 "text": text, "raw": json.dumps(msg),
                 "understood": json.dumps(understood, ensure_ascii=False) if understood else "",
                 "intent": (understood or {}).get("intent", "none"),
                 "reply": (understood or {}).get("reply", ""),
                 "reply_status": "pending" if (understood or {}).get("reply") else "none"}
        try:
            table().put_item(Item=saved, ConditionExpression="attribute_not_exists(pk)")
        except table().meta.client.exceptions.ConditionalCheckFailedException:
            return                                         # stored by an earlier delivery in the meantime
    if saved.get("reply_status") != "pending":
        return                                             # already sent, or nothing to say
    token = access_token()
    if token is None:
        status = "no_token"                                # Meta app not connected yet: the reply is kept, not sent
    else:
        send_whatsapp(item["phone_number_id"], msg["from"], saved["reply"], msg["id"], token)
        status = "sent"
    table().update_item(Key=key, UpdateExpression="SET reply_status = :s", ExpressionAttributeValues={":s": status})


def handler(event, context):
    records = event.get("Records", [])
    for n, record in enumerate(records):
        try:
            handle(json.loads(record["body"]))
        except Exception:                                  # noqa: BLE001  report, retry, then DLQ
            log.exception("failed %s", record.get("messageId"))
            # FIFO: this message AND everything after it go back to the queue, so order is kept
            return {"batchItemFailures": [{"itemIdentifier": r["messageId"]} for r in records[n:]]}
    return {"batchItemFailures": []}
