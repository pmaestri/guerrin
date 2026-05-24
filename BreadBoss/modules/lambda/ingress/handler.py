import json
import logging
import os
import socket
import uuid
import time

import boto3
import certifi
from boto3.dynamodb.conditions import Key
from confluent_kafka import Producer
from aws_msk_iam_sasl_signer.MSKAuthTokenProvider import generate_auth_token

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_producer = None
dynamodb = boto3.resource("dynamodb")
menu_table = dynamodb.Table(os.environ.get("MENU_TABLE", "breadboss-menu"))


def _oauth_cb(oauth_config):
    try:
        region = os.environ["AWS_REGION"]
        token, expiry_ms = generate_auth_token(region)
        logger.info(json.dumps({"handler": "ingress", "msg": "oauth token generado OK"}))
        return token, expiry_ms / 1000
    except Exception as e:
        logger.error(json.dumps({"handler": "ingress", "msg": f"oauth_cb error: {e}"}))
        raise


def get_producer():
    global _producer
    if _producer is None:
        bootstrap = os.environ["MSK_BOOTSTRAP"]
        logger.info(json.dumps({"handler": "ingress", "msg": f"creando producer, bootstrap={bootstrap}"}))
        host, port = bootstrap.split(":")
        try:
            with socket.create_connection((host, int(port)), timeout=5) as s:
                logger.info(json.dumps({"handler": "ingress", "msg": f"TCP OK a {host}:{port}"}))
        except Exception as e:
            logger.error(json.dumps({"handler": "ingress", "msg": f"TCP FALLO a {host}:{port}: {e}"}))
        _producer = Producer({
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "OAUTHBEARER",
            "oauth_cb": _oauth_cb,
            "ssl.ca.location": certifi.where(),
            "message.timeout.ms": "12000",
            "socket.connection.setup.timeout.ms": "8000",
        })
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

    delivery_errors = []

    def _delivery_cb(err, msg):
        if err:
            delivery_errors.append(str(err))
            logger.error(json.dumps({"orderId": order_id, "handler": "ingress", "msg": f"delivery error: {err}"}))

    producer = get_producer()
    producer.produce("pedidos", key=order_id.encode(), value=json.dumps(order_event).encode(), callback=_delivery_cb)
    remaining = producer.flush(timeout=15)
    producer.poll(0)  # drain pending delivery callbacks to capture errors
    if remaining > 0 or delivery_errors:
        logger.error(json.dumps({"orderId": order_id, "handler": "ingress", "msg": f"fallo al publicar evento, remaining={remaining}, errors={delivery_errors}"}))
        return {"statusCode": 500, "body": json.dumps({"error": "Error publicando evento"})}

    logger.info(json.dumps({"orderId": order_id, "handler": "ingress", "msg": "ORDER_CREATED publicado", "total": str(total)}))

    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "RECIBIDO", "message": "Pedido recibido!"}),
    }
