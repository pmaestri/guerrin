import json
import logging
import os
import time

import boto3
import certifi
from boto3.dynamodb.conditions import Key
from confluent_kafka import Producer
from aws_msk_iam_sasl_signer.MSKAuthTokenProvider import generate_auth_token

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])

_producer = None


def _oauth_cb(oauth_config):
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    token, expiry_ms = generate_auth_token(region)
    return token, expiry_ms / 1000


def get_producer():
    global _producer
    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": os.environ["MSK_BOOTSTRAP"],
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "OAUTHBEARER",
            "oauth_cb": _oauth_cb,
            "ssl.ca.location": certifi.where(),
            "message.timeout.ms": "45000",
        })
    return _producer


def _update_dynamo_status(order_id, item, status):
    orders_table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status, ":u": int(time.time() * 1000)},
    )


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = items[0]
    current_status = item.get("status")

    if current_status in ("EN_CAMINO", "ENTREGADO"):
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"orderId": order_id, "status": current_status, "message": "Ya estaba marcado"}),
        }

    if current_status != "EN_PREPARACION":
        return {
            "statusCode": 409,
            "body": json.dumps({"error": f"El pedido esta en estado '{current_status}', solo se puede marcar listo desde EN_PREPARACION"}),
        }

    now_ms = int(time.time() * 1000)
    customer_id = item.get("customerId")
    customer_email = item.get("customerEmail", "")
    total = item.get("total")

    delivery_errors = []

    def _delivery_cb(err, msg):
        if err:
            delivery_errors.append(str(err))
            logger.error(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": f"delivery error: {err}"}))

    producer = get_producer()
    producer.produce(
        "orders.ready",
        key=order_id.encode(),
        value=json.dumps({
            "eventType": "ORDER_READY",
            "timestamp": now_ms,
            "data": {
                "orderId": order_id,
                "customerId": customer_id,
                "customerEmail": customer_email,
                "total": str(total) if total is not None else None,
                "status": "LISTO",
            },
        }).encode(),
        callback=_delivery_cb,
    )
    remaining = producer.flush(timeout=20)
    producer.poll(0)
    if remaining > 0 or delivery_errors:
        logger.error(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": f"fallo al publicar ORDER_READY, remaining={remaining}, errors={delivery_errors}"}))
        return {"statusCode": 500, "body": json.dumps({"error": "Error publicando evento"})}

    _update_dynamo_status(order_id, item, "EN_CAMINO")

    logger.info(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": "ORDER_READY publicado"}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "LISTO", "message": "Pedido marcado como listo"}),
    }
