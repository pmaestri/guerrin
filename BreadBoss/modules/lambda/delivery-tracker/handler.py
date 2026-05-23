import json
import os
import base64
import random
import redis
from datetime import datetime


DRIVERS = ["driver_01", "driver_02", "driver_03", "driver_04"]


def _get_redis():
    return redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)


def handler(event, context):
    r = _get_redis()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            driver = random.choice(DRIVERS)

            r.hset(
                f"order:{order_id}",
                mapping={
                    "status": "EN_CAMINO",
                    "driver": driver,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            print(f"Order {order_id} → EN_CAMINO, asignado a {driver}")

    return {"statusCode": 200}
