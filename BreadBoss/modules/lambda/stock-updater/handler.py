import json
import base64
import boto3


dynamodb = boto3.resource("dynamodb")
menu_table = dynamodb.Table("breadboss-menu")


def handler(event, context):
    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            items = payload["data"]["items"]
            order_id = payload["data"]["orderId"]

            for item in items:
                response = menu_table.update_item(
                    Key={"itemId": item["itemId"]},
                    UpdateExpression="SET stock = stock - :qty",
                    ConditionExpression="stock >= :qty",
                    ExpressionAttributeValues={":qty": item["qty"]},
                    ReturnValues="UPDATED_NEW",
                )
                stock_restante = int(response["Attributes"]["stock"])
                if stock_restante < 5:
                    print(f"ALERTA stock bajo — itemId={item['itemId']} stock={stock_restante}")

            print(f"Order {order_id} → stock actualizado para {len(items)} items")

    return {"statusCode": 200}
