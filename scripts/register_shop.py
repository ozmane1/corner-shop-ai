"""Register a shop and the WhatsApp number it owns (writes SHOP#<id>/META and PHONE#<id>/SHOP in one transaction).

    python3 scripts/register_shop.py --table <TableName> --shop casa-01 --name "Corner shop" --city Casablanca \
        --phone-number-id <Meta phone_number_id> [--profile <aws profile>]
"""
import argparse
from datetime import datetime, timezone

import boto3


def main():
    ap = argparse.ArgumentParser()
    for a in ("--table", "--shop", "--name", "--city", "--phone-number-id"):
        ap.add_argument(a, required=True)
    ap.add_argument("--profile")
    a = ap.parse_args()
    client = boto3.Session(profile_name=a.profile).client("dynamodb")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client.transact_write_items(TransactItems=[
        {"Put": {"TableName": a.table, "ConditionExpression": "attribute_not_exists(pk)", "Item": {
            "pk": {"S": f"SHOP#{a.shop}"}, "sk": {"S": "META"}, "name": {"S": a.name}, "city": {"S": a.city},
            "phone_number_id": {"S": a.phone_number_id}, "created_at": {"S": now}}}},
        {"Put": {"TableName": a.table, "ConditionExpression": "attribute_not_exists(pk)", "Item": {
            "pk": {"S": f"PHONE#{a.phone_number_id}"}, "sk": {"S": "SHOP"}, "shop_id": {"S": a.shop}}}},
    ])
    print(f"registered shop {a.shop} for phone_number_id {a.phone_number_id}")


if __name__ == "__main__":
    main()
