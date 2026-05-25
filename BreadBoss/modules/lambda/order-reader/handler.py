import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def _get_one(order_id):
    resp = table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}
    item = json.loads(json.dumps(items[0], default=str))
    logger.info(json.dumps({"orderId": order_id, "handler": "order-reader", "msg": "found"}))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(item),
    }


def _list_by_status(status):
    resp = table.scan(FilterExpression=Attr("status").eq(status))
    raw = resp.get("Items", [])
    items = json.loads(json.dumps(raw, default=str))
    logger.info(json.dumps({"handler": "order-reader", "msg": "list", "status": status, "count": len(items)}))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"items": items, "count": len(items)}),
    }


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("orderId")
    if order_id:
        return _get_one(order_id)

    qs = event.get("queryStringParameters") or {}
    status = qs.get("status")
    if not status:
        return {"statusCode": 400, "body": json.dumps({"error": "Falta query param 'status'"})}
    return _list_by_status(status)
