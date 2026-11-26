#!/usr/bin/env python3
"""Connect a Meta WhatsApp app to a deployed stack. Run it yourself: secrets are typed, never pasted in a chat or a file.

    python scripts/connect_whatsapp.py --profile <aws profile> [--stack CornerShop-dev] [--shop casa-01]

It asks for (hidden input) the App secret and the access token, and for the phone_number_id of your WhatsApp number,
stores the two secrets in Secrets Manager (the generated verify_token is kept), links the number to the shop, and prints
the two values to paste into Meta: Callback URL and Verify token (WhatsApp > Configuration > Webhook).
"""
import argparse
import getpass
import json

import boto3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--region", default="eu-central-1")
    ap.add_argument("--stack", default="CornerShop-dev")
    ap.add_argument("--shop", default="casa-01")
    a = ap.parse_args()
    s = boto3.Session(profile_name=a.profile, region_name=a.region)
    out = {o["OutputKey"]: o["OutputValue"]
           for o in s.client("cloudformation").describe_stacks(StackName=a.stack)["Stacks"][0]["Outputs"]}

    app_secret = getpass.getpass("Meta App secret (App settings > Basic, hidden): ").strip()
    token = getpass.getpass("WhatsApp access token (hidden): ").strip()
    pid = input("phone_number_id (WhatsApp > API Setup): ").strip()
    if not (app_secret and token and pid.isdigit()):
        raise SystemExit("all three values are needed (phone_number_id is digits only)")

    sm = s.client("secretsmanager")
    current = json.loads(sm.get_secret_value(SecretId=out["SecretArn"])["SecretString"])
    sm.put_secret_value(SecretId=out["SecretArn"], SecretString=json.dumps(
        {**current, "app_secret": app_secret, "access_token": token}))
    try:
        s.client("dynamodb").put_item(TableName=out["TableName"], ConditionExpression="attribute_not_exists(pk)",
                                      Item={"pk": {"S": f"PHONE#{pid}"}, "sk": {"S": "SHOP"}, "shop_id": {"S": a.shop}})
        print(f"number {pid} -> shop {a.shop}")
    except s.client("dynamodb").exceptions.ConditionalCheckFailedException:
        print(f"number {pid} was already linked (left as is)")
    print("\nPaste into Meta (WhatsApp > Configuration > Webhook), then subscribe to the 'messages' field:")
    print(f"  Callback URL : {out['WebhookUrl']}")
    print(f"  Verify token : {current['verify_token']}")
    print("\nSecrets are cached 5 minutes by the Lambdas: wait 5 minutes or redeploy before the first test.")


if __name__ == "__main__":
    main()
