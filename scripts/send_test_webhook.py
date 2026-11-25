"""Send a signed fake WhatsApp message to the deployed webhook (end-to-end test without Meta).

    python3 scripts/send_test_webhook.py --url <WebhookUrl> --secret-arn <SecretArn> --phone-number-id <id> \
        [--text "how much milk is left?"] [--profile <aws profile>] [--bad-signature]

Signs the body with the app_secret from Secrets Manager exactly like Meta does (X-Hub-Signature-256).
Send the same message twice to see the dedupe; --bad-signature must get 401.
"""
import argparse
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid

import boto3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--secret-arn", required=True)
    ap.add_argument("--phone-number-id", required=True)
    ap.add_argument("--text", default="how much milk is left?")
    ap.add_argument("--wamid", default=f"wamid.test-{uuid.uuid4().hex[:12]}")
    ap.add_argument("--profile")
    ap.add_argument("--bad-signature", action="store_true")
    a = ap.parse_args()
    sess = boto3.Session(profile_name=a.profile)
    app_secret = json.loads(sess.client("secretsmanager").get_secret_value(SecretId=a.secret_arn)["SecretString"])["app_secret"]
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": a.phone_number_id},
        "messages": [{"id": a.wamid, "from": "212600000000", "timestamp": str(int(time.time())), "type": "text",
                      "text": {"body": a.text}}]}}]}]}).encode()
    key = b"wrong" if a.bad_signature else app_secret.encode()
    sig = "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(a.url, data=body, method="POST",
                                 headers={"content-type": "application/json", "X-Hub-Signature-256": sig})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(r.status, r.read().decode(), a.wamid)
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode(), a.wamid)


if __name__ == "__main__":
    main()
