import json
import logging
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    resp = table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = items[0]

    if item.get("status") == "ENTREGADO":
        return {"statusCode": 200, "body": json.dumps({"orderId": order_id, "status": "ENTREGADO"})}

    created_at = int(item.get("timestamp", int(time.time() * 1000)))
    now_ms = int(time.time() * 1000)
    tiempo_entrega_min = round((now_ms - created_at) / 60000, 1)

    table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, tiempo_entrega_min = :t, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "ENTREGADO",
            ":t": str(tiempo_entrega_min),
            ":u": now_ms,
        },
    )

    logger.info(json.dumps({"orderId": order_id, "handler": "order-finalizer", "msg": "ENTREGADO", "tiempo_min": tiempo_entrega_min}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "ENTREGADO", "tiempo_entrega_min": tiempo_entrega_min}),
    }
