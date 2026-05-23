import json
import logging
import os
import sys
import base64
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key
from kafka import KafkaProducer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None
_producer = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


def get_producer():
    global _producer
    if _producer is None:
        tp = MSKAuthTokenProvider(region=os.environ["AWS_REGION_NAME"])
        _producer = KafkaProducer(
            bootstrap_servers=os.environ["MSK_BOOTSTRAP"].split(","),
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_oauth_token_provider=tp,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
    return _producer


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
    producer = get_producer()

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

            producer.send(
                "orders.ready",
                key=order_id.encode(),
                value={
                    "eventType": "ORDER_READY",
                    "timestamp": now_ms,
                    "data": {
                        "orderId": order_id,
                        "customerId": data.get("customerId"),
                        "customerEmail": data.get("customerEmail", ""),
                        "total": data.get("total"),
                        "status": "LISTO",
                    },
                },
            )

            logger.info(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "EN_PREPARACION, ORDER_READY publicado"}))

    producer.flush()
    return {"statusCode": 200}
