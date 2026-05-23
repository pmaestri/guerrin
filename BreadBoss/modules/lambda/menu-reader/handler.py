import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MENU_TABLE"])


def handler(event, context):
    resp = table.scan()
    items = resp.get("Items", [])
    items = json.loads(json.dumps(items, default=str))

    logger.info(json.dumps({"handler": "menu-reader", "msg": f"{len(items)} items returned"}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(items),
    }
