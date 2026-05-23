import json
import logging
import os
import sys
import base64

import boto3

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")
ses = boto3.client("ses")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
SES_SENDER = os.environ["SES_SENDER"]

MENSAJES = {
    "ORDER_CREATED": {
        "subject": "Pedido recibido",
        "body": lambda d: (
            f"Tu pedido fue recibido!\n"
            f"Total: ${d.get('total', 0)}\n"
            f"Estado: RECIBIDO\n"
            f"ID: {d['orderId'][:8]}"
        ),
    },
    "ORDER_READY": {
        "subject": "Tu pedido está en camino",
        "body": lambda d: (
            f"Tu pedido ya salió!\n"
            f"Repartidor asignado. Llegará en los próximos minutos.\n"
            f"ID: {d['orderId'][:8]}"
        ),
    },
}


def handler(event, context):
    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            event_type = payload.get("eventType", "ORDER_CREATED")
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, f"notifier-{event_type}"):
                continue

            template = MENSAJES.get(event_type)
            if not template:
                logger.warning(json.dumps({"handler": "notifier", "msg": f"evento desconocido: {event_type}"}))
                continue

            customer_email = data.get("customerEmail", "")
            if not customer_email:
                logger.warning(json.dumps({"orderId": order_id, "handler": "notifier", "msg": "sin customerEmail, skip SES"}))

            subject = f"{template['subject']} — {order_id[:8]}"
            body = template["body"](data)

            sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=body)

            if customer_email:
                ses.send_email(
                    Source=SES_SENDER,
                    Destination={"ToAddresses": [customer_email]},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {"Text": {"Data": body}},
                    },
                )

            logger.info(json.dumps({"orderId": order_id, "handler": "notifier", "msg": "notificación enviada", "eventType": event_type}))

    return {"statusCode": 200}
