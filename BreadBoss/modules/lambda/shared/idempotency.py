import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

dynamodb = boto3.resource("dynamodb")
_table = None


def _get_table():
    global _table
    if _table is None:
        _table = dynamodb.Table(os.environ["PROCESSED_TABLE"])
    return _table


def already_processed(order_id: str, consumer: str) -> bool:
    """
    Intenta registrar (orderId, consumer) como procesado.
    Retorna True si ya fue procesado antes (skip), False si es nuevo (procesar).
    TTL: 24 horas.
    """
    table = _get_table()
    expires_at = int(time.time()) + 86400  # 24h
    try:
        table.put_item(
            Item={"orderId": order_id, "consumer": consumer, "expiresAt": expires_at},
            ConditionExpression="attribute_not_exists(orderId) AND attribute_not_exists(consumer)",
        )
        return False  # nuevo, procesar
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info(f"[idempotency] skip — orderId={order_id} consumer={consumer}")
            return True  # ya procesado
        raise
