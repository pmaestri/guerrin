import json
import logging
import base64
import os
import sys

import boto3

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
menu_table = dynamodb.Table(os.environ.get("MENU_TABLE", "breadboss-menu"))


def handler(event, context):
    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            items = payload["data"]["items"]
            order_id = payload["data"]["orderId"]

            if already_processed(order_id, "stock-updater"):
                continue

            for item in items:
                response = menu_table.update_item(
                    Key={"itemId": item["itemId"]},
                    UpdateExpression="SET stock = stock - :qty",
                    ConditionExpression="stock >= :qty",
                    ExpressionAttributeValues={":qty": item["qty"]},
                    ReturnValues="UPDATED_NEW",
                )
                stock_restante = int(response["Attributes"]["stock"])
                if stock_restante < 5:
                    logger.warning(json.dumps({"handler": "stock-updater", "msg": "stock bajo", "itemId": item["itemId"], "stock": stock_restante}))

            logger.info(json.dumps({"orderId": order_id, "handler": "stock-updater", "msg": f"stock actualizado para {len(items)} items"}))

    return {"statusCode": 200}
