import json
import logging
import os
import uuid
import time

import boto3
from boto3.dynamodb.conditions import Key
from kafka import KafkaProducer
from aws_msk_iam_sasl_signer.MSKAuthTokenProvider import MSKAuthTokenProvider

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_producer = None
dynamodb = boto3.resource("dynamodb")
menu_table = dynamodb.Table(os.environ.get("MENU_TABLE", "breadboss-menu"))


def get_producer():
    global _producer
    if _producer is None:
        tp = MSKAuthTokenProvider(region=os.environ["AWS_REGION"])
        _producer = KafkaProducer(
            bootstrap_servers=os.environ["MSK_BOOTSTRAP"].split(","),
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_oauth_token_provider=tp,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
    return _producer


def _validate_and_price(items):
    """Valida items y retorna lista con precio del backend. Lanza ValueError si hay error."""
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("'items' debe ser una lista no vacía")

    priced = []
    for i, item in enumerate(items):
        if not isinstance(item.get("itemId"), str) or not item["itemId"]:
            raise ValueError(f"items[{i}].itemId inválido")
        qty = item.get("qty")
        if not isinstance(qty, int) or qty <= 0:
            raise ValueError(f"items[{i}].qty debe ser entero > 0")

        resp = menu_table.get_item(Key={"itemId": item["itemId"]})
        menu_item = resp.get("Item")
        if not menu_item:
            raise ValueError(f"itemId '{item['itemId']}' no existe en el menú")

        priced.append({
            "itemId": item["itemId"],
            "qty": qty,
            "name": menu_item.get("name", ""),
            "price": float(menu_item["price"]),
        })

    return priced


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Body inválido"})}

    if "deliveryAddress" not in body or not body["deliveryAddress"]:
        return {"statusCode": 400, "body": json.dumps({"error": "Falta deliveryAddress"})}

    try:
        items = _validate_and_price(body.get("items", []))
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    customer_id = claims["sub"]
    customer_email = claims.get("email", "")

    total = sum(i["price"] * i["qty"] for i in items)
    order_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)

    order_event = {
        "eventType": "ORDER_CREATED",
        "timestamp": created_at,
        "data": {
            "orderId": order_id,
            "channel": body.get("channel", "app"),
            "customerId": customer_id,
            "customerEmail": customer_email,
            "items": items,
            "total": total,
            "deliveryAddress": body["deliveryAddress"],
            "status": "RECIBIDO",
        },
    }

    producer = get_producer()
    producer.send("pedidos", key=order_id.encode(), value=order_event)
    producer.flush()

    logger.info(json.dumps({"orderId": order_id, "handler": "ingress", "msg": "ORDER_CREATED publicado", "total": total}))

    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "RECIBIDO", "message": "Pedido recibido!"}),
    }
