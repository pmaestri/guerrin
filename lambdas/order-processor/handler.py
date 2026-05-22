import json
import base64
import time

import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('breadboss-orders')


def handler(event, context):
    for topic, records in event['records'].items():
        for record in records:
            payload = json.loads(
                base64.b64decode(record['value']).decode()
            )
            data = payload['data']

            table.put_item(Item={
                'orderId':         data['orderId'],
                'timestamp':       int(time.time()),
                'channel':         data['channel'],
                'status':          data['status'],
                'customerId':      data['customerId'],
                'items':           data['items'],
                'total':           str(data['total']),  # DynamoDB no acepta float
                'deliveryAddress': data['deliveryAddress'],
                'timestamps': {
                    'received': payload['timestamp']
                }
            })
            print(f"Order {data['orderId']} saved to DynamoDB")

    return {'statusCode': 200}
