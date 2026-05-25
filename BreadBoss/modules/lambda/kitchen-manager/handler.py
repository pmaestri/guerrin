import json
import logging
import os
import sys
import base64
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


def _update_dynamo_status(order_id, status):
    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        logger.warning(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "orderId no encontrado en DynamoDB"}))
        return
    item = items[0]
    orders_table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status, ":u": int(time.time() * 1000)},
    )


def handler(event, context):
    r = get_redis()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, "kitchen-manager"):
                continue

            now_ms = int(time.time() * 1000)

            r.hset(
                f"order:{order_id}",
                mapping={"status": "EN_PREPARACION", "updated_at": str(now_ms), "items": json.dumps(data["items"])},
            )
            r.expire(f"order:{order_id}", 7200)
            r.lpush("kitchen:queue", order_id)

            _update_dynamo_status(order_id, "EN_PREPARACION")

            logger.info(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "EN_PREPARACION — esperando confirmacion manual"}))

    return {"statusCode": 200}
