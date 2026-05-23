import json
import os
import base64
import redis
from datetime import datetime
from kafka import KafkaProducer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider


def _get_redis():
    return redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)


def _get_producer():
    tp = MSKAuthTokenProvider(region=os.environ["AWS_REGION_NAME"])
    return KafkaProducer(
        bootstrap_servers=os.environ["MSK_BOOTSTRAP"].split(","),
        security_protocol="SASL_SSL",
        sasl_mechanism="OAUTHBEARER",
        sasl_oauth_token_provider=tp,
        value_serializer=lambda v: json.dumps(v).encode(),
    )


def handler(event, context):
    r = _get_redis()
    producer = _get_producer()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            r.hset(
                f"order:{order_id}",
                mapping={
                    "status": "EN_PREPARACION",
                    "updated_at": datetime.utcnow().isoformat(),
                    "items": json.dumps(data["items"]),
                },
            )
            r.expire(f"order:{order_id}", 7200)
            r.lpush("kitchen:queue", order_id)

            # Dispara el segundo fan-out: delivery-tracker y notifier escuchan este topic
            producer.send(
                "orders.ready",
                key=order_id.encode(),
                value={
                    "eventType": "ORDER_READY",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": {
                        "orderId": order_id,
                        "customerId": data.get("customerId"),
                        "total": data.get("total"),
                        "status": "LISTO",
                    },
                },
            )
            print(f"Order {order_id} → EN_PREPARACION, ORDER_READY publicado")

    producer.flush()
    return {"statusCode": 200}
