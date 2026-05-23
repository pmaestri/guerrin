import json
import logging
import os
import sys
import base64
import random
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DRIVERS = ["driver_01", "driver_02", "driver_03", "driver_04"]

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


def _update_dynamo_status(order_id, status, driver):
    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        logger.warning(json.dumps({"orderId": order_id, "handler": "delivery-tracker", "msg": "orderId no encontrado en DynamoDB"}))
        return
    item = items[0]
    orders_table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, driver = :driver, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":driver": driver,
            ":u": int(time.time() * 1000),
        },
    )


def handler(event, context):
    r = get_redis()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, "delivery-tracker"):
                continue

            driver = random.choice(DRIVERS)
            now_ms = int(time.time() * 1000)

            r.hset(
                f"order:{order_id}",
                mapping={"status": "EN_CAMINO", "driver": driver, "updated_at": str(now_ms)},
            )

            _update_dynamo_status(order_id, "EN_CAMINO", driver)

            logger.info(json.dumps({"orderId": order_id, "handler": "delivery-tracker", "msg": "EN_CAMINO", "driver": driver}))

    return {"statusCode": 200}
