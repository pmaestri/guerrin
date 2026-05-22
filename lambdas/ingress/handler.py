import json
import os
import uuid
from datetime import datetime

from kafka import KafkaProducer
from aws_msk_iam_sasl_signer.MSKAuthTokenProvider import MSKAuthTokenProvider


def get_producer():
    tp = MSKAuthTokenProvider(region=os.environ['AWS_REGION'])
    return KafkaProducer(
        bootstrap_servers=os.environ['MSK_BOOTSTRAP'].split(','),
        security_protocol='SASL_SSL',
        sasl_mechanism='OAUTHBEARER',
        sasl_oauth_token_provider=tp,
        value_serializer=lambda v: json.dumps(v).encode()
    )


def handler(event, context):
    body = json.loads(event['body'])

    for field in ['items', 'deliveryAddress']:
        if field not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Falta {field}'})
            }

    customer_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

    order_id = str(uuid.uuid4())
    order_event = {
        'eventType': 'ORDER_CREATED',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'data': {
            'orderId': order_id,
            'channel': body.get('channel', 'app'),
            'customerId': customer_id,
            'items': body['items'],
            'total': sum(i['price'] * i['qty'] for i in body['items']),
            'deliveryAddress': body['deliveryAddress'],
            'status': 'RECIBIDO'
        }
    }

    producer = get_producer()
    producer.send('pedidos', key=order_id.encode(), value=order_event)
    producer.flush()

    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'orderId': order_id,
            'status': 'RECIBIDO',
            'message': 'Pedido recibido!'
        })
    }
