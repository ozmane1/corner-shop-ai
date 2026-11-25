import hashlib
import hmac
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.update(AWS_DEFAULT_REGION="eu-west-1", AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test",
                  TABLE_NAME="shop", SECRET_ID="whatsapp")

APP_SECRET, VERIFY = "app-secret-for-tests", "verify-token-for-tests"


@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.resource("dynamodb")
        table = ddb.create_table(TableName="shop", BillingMode="PAY_PER_REQUEST",
                                 KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
                                 AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}])
        q = boto3.client("sqs").create_queue(QueueName="inbox.fifo", Attributes={"FifoQueue": "true"})["QueueUrl"]
        boto3.client("secretsmanager").create_secret(Name="whatsapp", SecretString=json.dumps({"app_secret": APP_SECRET, "verify_token": VERIFY}))
        table.put_item(Item={"pk": "PHONE#111", "sk": "SHOP", "shop_id": "casa-01"})
        os.environ["QUEUE_URL"] = q
        from ingest import handler as ingest
        from dispatcher import handler as dispatcher
        ingest._ddb = ingest._sqs = ingest._secrets = None
        ingest._secret_cache.clear()
        ingest.QUEUE_URL = q
        dispatcher._table = None
        yield {"table": table, "queue": q}


def webhook_event(payload: dict, secret: str = APP_SECRET, signature: str | None = None) -> dict:
    body = json.dumps(payload)
    sig = signature or "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {"requestContext": {"http": {"method": "POST"}}, "headers": {"X-Hub-Signature-256": sig}, "body": body}


def wa_payload(*msgs, phone_number_id="111") -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone_number_id},
        "messages": [{"id": m, "from": "212600000000", "timestamp": "1764100000", "type": "text",
                      "text": {"body": "how much milk is left?"}} for m in msgs]}}]}]}
