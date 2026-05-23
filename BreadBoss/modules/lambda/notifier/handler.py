import json
import os
import base64
import boto3


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

            template = MENSAJES.get(event_type)
            if not template:
                print(f"Tipo de evento desconocido: {event_type}, se omite")
                continue

            subject = f"{template['subject']} — {order_id[:8]}"
            body = template["body"](data)

            sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=body)

            ses.send_email(
                Source=SES_SENDER,
                Destination={"ToAddresses": [SES_SENDER]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )

            print(f"Order {order_id} → notificación enviada ({event_type})")

    return {"statusCode": 200}
