import json
import logging
import base64
import os
import time
from decimal import Decimal
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))


def handler(event, context):
    for topic, records in event["records"].items():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            created_at = int(time.time() * 1000)

            table.put_item(Item={
                "orderId":         order_id,
                "timestamp":       created_at,
                "channel":         data["channel"],
                "status":          data["status"],
                "customerId":      data["customerId"],
                "customerEmail":   data.get("customerEmail", ""),
                "items":           [{**i, "price": Decimal(str(i["price"]))} for i in data["items"]],
                "total":           Decimal(str(data["total"])),
                "deliveryAddress": data["deliveryAddress"],
                "fecha":           datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                "incidencia":      "ninguna",
                "timestamps": {
                    "received": payload["timestamp"]
                },
            })

            logger.info(json.dumps({"orderId": order_id, "handler": "order-processor", "msg": "guardado en DynamoDB"}))

    return {"statusCode": 200}
