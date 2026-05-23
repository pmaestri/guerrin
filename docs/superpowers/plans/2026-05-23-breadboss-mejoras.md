# BreadBoss Mejoras Prioritarias — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir los 3 bugs críticos del ciclo de negocio (ciclo de vida, notificaciones, idempotencia) y agregar funcionalidad faltante (GET endpoints, validación, CORS, logging).

**Architecture:** Sistema event-driven con Kafka (MSK) + Lambda. Los cambios siguen el patrón existente: consumers de Kafka con guard de idempotencia en DynamoDB, nuevas lambdas registradas en `main.tf` con el mismo mecanismo de packaging (simple vs packaged). El endpoint `POST /orders/{id}/deliver` llama a una nueva lambda `order-finalizer` que actualiza DynamoDB directamente.

**Tech Stack:** Python 3.11, boto3, kafka-python-ng, aws-msk-iam-sasl-signer-python, redis, Terraform (AWS provider).

---

## Mapa de archivos

| Archivo | Acción | Qué hace |
|---|---|---|
| `BreadBoss/modules/dynamodb/main.tf` | Modificar | Agregar tabla `breadboss-processed` |
| `BreadBoss/modules/lambda/order-finalizer/handler.py` | Crear | Lambda para `POST /orders/{id}/deliver` |
| `BreadBoss/modules/lambda/order-reader/handler.py` | Crear | Lambda para `GET /orders/{id}` |
| `BreadBoss/modules/lambda/menu-reader/handler.py` | Crear | Lambda para `GET /menu` |
| `BreadBoss/modules/lambda/ingress/handler.py` | Modificar | Validación, precio backend, email en evento, timestamp ms, conexión global |
| `BreadBoss/modules/lambda/notifier/handler.py` | Modificar | Email al cliente, idempotencia, logging |
| `BreadBoss/modules/lambda/stock-updater/handler.py` | Modificar | Idempotencia, logging |
| `BreadBoss/modules/lambda/kitchen-manager/handler.py` | Modificar | DynamoDB en cada transición, idempotencia, conexiones globales, logging |
| `BreadBoss/modules/lambda/delivery-tracker/handler.py` | Modificar | DynamoDB al asignar driver, idempotencia, conexión global, logging |
| `BreadBoss/modules/lambda/order-processor/handler.py` | Modificar | Timestamp epoch ms, logging |
| `BreadBoss/modules/lambda/main.tf` | Modificar | Registrar 3 nuevas lambdas |
| `BreadBoss/modules/lambda/variables.tf` | Modificar | Variable para tabla idempotencia |
| `BreadBoss/modules/lambda/package.sh` | Modificar | Incluir nuevas lambdas en build |
| `BreadBoss/modules/api_gateway/main.tf` | Modificar | CORS, throttling, 3 rutas nuevas |
| `BreadBoss/modules/api_gateway/variables.tf` | Modificar | ARNs y nombres de nuevas lambdas |
| `BreadBoss/main.tf` | Modificar | Pasar nuevas variables a módulos |

---

## Task 1: Tabla DynamoDB para idempotencia

**Files:**
- Modify: `BreadBoss/modules/dynamodb/main.tf`

- [ ] **Step 1: Agregar tabla `breadboss-processed` al final de `dynamodb/main.tf`**

```hcl
resource "aws_dynamodb_table" "processed" {
  name         = "${var.prefix}-processed"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"
  range_key    = "consumer"

  attribute {
    name = "orderId"
    type = "S"
  }
  attribute {
    name = "consumer"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  tags = { Name = "${var.prefix}-processed" }
}

output "processed_table_name" {
  value = aws_dynamodb_table.processed.name
}
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/dynamodb/main.tf
git commit -m "feat(dynamodb): tabla breadboss-processed para idempotencia"
```

---

## Task 2: Lambda `order-finalizer` — cerrar ciclo de vida

Esta lambda recibe el call directo de API Gateway (`POST /orders/{id}/deliver`), calcula el tiempo de entrega y marca el pedido como `ENTREGADO` en DynamoDB. No necesita Kafka.

**Files:**
- Create: `BreadBoss/modules/lambda/order-finalizer/handler.py`

- [ ] **Step 1: Crear el directorio y el handler**

```python
# BreadBoss/modules/lambda/order-finalizer/handler.py
import json
import logging
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    response = table.get_item(Key={"orderId": order_id, "timestamp": _get_timestamp(order_id)})
    if "Item" not in response:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = response["Item"]

    if item.get("status") == "ENTREGADO":
        return {"statusCode": 200, "body": json.dumps({"orderId": order_id, "status": "ENTREGADO"})}

    created_at = int(item.get("timestamp", int(time.time() * 1000)))
    now_ms = int(time.time() * 1000)
    tiempo_entrega_min = round((now_ms - created_at) / 60000, 1)

    table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, tiempo_entrega_min = :t, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "ENTREGADO",
            ":t": str(tiempo_entrega_min),
            ":u": now_ms,
        },
    )

    logger.info(json.dumps({"orderId": order_id, "handler": "order-finalizer", "msg": "ENTREGADO", "tiempo_min": tiempo_entrega_min}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "ENTREGADO", "tiempo_entrega_min": tiempo_entrega_min}),
    }


def _get_timestamp(order_id):
    # Query por orderId para obtener el timestamp (range key)
    dynamodb_client = boto3.resource("dynamodb")
    t = dynamodb_client.Table(os.environ["ORDERS_TABLE"])
    resp = t.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return None
    return items[0]["timestamp"]
```

Nota: `_get_timestamp` hace un query extra. Para simplificar, reescribimos el handler usando `query` directamente:

```python
# BreadBoss/modules/lambda/order-finalizer/handler.py  (versión final limpia)
import json
import logging
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    resp = table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = items[0]

    if item.get("status") == "ENTREGADO":
        return {"statusCode": 200, "body": json.dumps({"orderId": order_id, "status": "ENTREGADO"})}

    created_at = int(item.get("timestamp", int(time.time() * 1000)))
    now_ms = int(time.time() * 1000)
    tiempo_entrega_min = round((now_ms - created_at) / 60000, 1)

    table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, tiempo_entrega_min = :t, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "ENTREGADO",
            ":t": str(tiempo_entrega_min),
            ":u": now_ms,
        },
    )

    logger.info(json.dumps({"orderId": order_id, "handler": "order-finalizer", "msg": "ENTREGADO", "tiempo_min": tiempo_entrega_min}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "ENTREGADO", "tiempo_entrega_min": tiempo_entrega_min}),
    }
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/order-finalizer/
git commit -m "feat(lambda): order-finalizer — cierra ciclo de vida del pedido"
```

---

## Task 3: Lambda `order-reader` — GET /orders/{id}

**Files:**
- Create: `BreadBoss/modules/lambda/order-reader/handler.py`

- [ ] **Step 1: Crear el handler**

```python
# BreadBoss/modules/lambda/order-reader/handler.py
import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    resp = table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = items[0]
    # Convertir Decimal a str/int para JSON serialization
    item = json.loads(json.dumps(item, default=str))

    logger.info(json.dumps({"orderId": order_id, "handler": "order-reader", "msg": "found"}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(item),
    }
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/order-reader/
git commit -m "feat(lambda): order-reader — GET /orders/{id}"
```

---

## Task 4: Lambda `menu-reader` — GET /menu

**Files:**
- Create: `BreadBoss/modules/lambda/menu-reader/handler.py`

- [ ] **Step 1: Crear el handler**

```python
# BreadBoss/modules/lambda/menu-reader/handler.py
import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["MENU_TABLE"])


def handler(event, context):
    resp = table.scan()
    items = resp.get("Items", [])
    items = json.loads(json.dumps(items, default=str))

    logger.info(json.dumps({"handler": "menu-reader", "msg": f"{len(items)} items returned"}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(items),
    }
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/menu-reader/
git commit -m "feat(lambda): menu-reader — GET /menu"
```

---

## Task 5: Registrar nuevas lambdas en Terraform

**Files:**
- Modify: `BreadBoss/modules/lambda/main.tf`
- Modify: `BreadBoss/modules/lambda/variables.tf`
- Modify: `BreadBoss/modules/lambda/outputs.tf`

- [ ] **Step 1: Agregar variable para tabla de orders en `variables.tf`**

Agregar al final de `BreadBoss/modules/lambda/variables.tf`:

```hcl
variable "orders_table_name" { type = string }
variable "menu_table_name"   { type = string }
```

- [ ] **Step 2: Actualizar `locals` en `main.tf`**

En `BreadBoss/modules/lambda/main.tf`, modificar `local.simple_functions`:

```hcl
simple_functions = toset(["order-processor", "stock-updater", "notifier", "order-finalizer", "order-reader", "menu-reader"])
```

Modificar `local.functions` agregando las 3 entradas nuevas:

```hcl
order-finalizer = {
  env_extras = { ORDERS_TABLE = var.orders_table_name }
}
order-reader = {
  env_extras = { ORDERS_TABLE = var.orders_table_name }
}
menu-reader = {
  env_extras = { MENU_TABLE = var.menu_table_name }
}
```

- [ ] **Step 3: Agregar outputs para las nuevas lambdas en `outputs.tf`**

Agregar al final de `BreadBoss/modules/lambda/outputs.tf`:

```hcl
output "order_finalizer_arn"  { value = aws_lambda_function.this["order-finalizer"].arn }
output "order_finalizer_name" { value = aws_lambda_function.this["order-finalizer"].function_name }
output "order_reader_arn"     { value = aws_lambda_function.this["order-reader"].arn }
output "order_reader_name"    { value = aws_lambda_function.this["order-reader"].function_name }
output "menu_reader_arn"      { value = aws_lambda_function.this["menu-reader"].arn }
output "menu_reader_name"     { value = aws_lambda_function.this["menu-reader"].function_name }
```

- [ ] **Step 4: Pasar nuevas variables desde `BreadBoss/main.tf`**

En el bloque `module "lambda"` de `BreadBoss/main.tf`, agregar:

```hcl
orders_table_name = "${var.prefix}-orders"
menu_table_name   = "${var.prefix}-menu"
```

- [ ] **Step 5: Commit**

```bash
git add BreadBoss/modules/lambda/main.tf BreadBoss/modules/lambda/variables.tf BreadBoss/modules/lambda/outputs.tf BreadBoss/main.tf
git commit -m "feat(lambda/tf): registrar order-finalizer, order-reader, menu-reader"
```

---

## Task 6: API Gateway — CORS, throttling y rutas nuevas

**Files:**
- Modify: `BreadBoss/modules/api_gateway/main.tf`
- Modify: `BreadBoss/modules/api_gateway/variables.tf`

- [ ] **Step 1: Agregar variables para nuevas lambdas en `variables.tf`**

Agregar al final de `BreadBoss/modules/api_gateway/variables.tf`:

```hcl
variable "order_finalizer_arn"  { type = string }
variable "order_finalizer_name" { type = string }
variable "order_reader_arn"     { type = string }
variable "order_reader_name"    { type = string }
variable "menu_reader_arn"      { type = string }
variable "menu_reader_name"     { type = string }
```

- [ ] **Step 2: Agregar CORS y throttling en `main.tf`**

Reemplazar el bloque `resource "aws_apigatewayv2_api" "this"` existente:

```hcl
resource "aws_apigatewayv2_api" "this" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
  }

  tags = { Name = "${var.prefix}-api" }
}
```

Reemplazar el bloque `resource "aws_apigatewayv2_stage" "default"`:

```hcl
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}
```

- [ ] **Step 3: Agregar integraciones y rutas nuevas en `main.tf`**

Agregar al final de `BreadBoss/modules/api_gateway/main.tf`:

```hcl
# --- order-finalizer ---
resource "aws_apigatewayv2_integration" "order_finalizer" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_finalizer_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "deliver_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /orders/{orderId}/deliver"
  target             = "integrations/${aws_apigatewayv2_integration.order_finalizer.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_finalizer" {
  statement_id  = "AllowAPIGatewayInvokeOrderFinalizer"
  action        = "lambda:InvokeFunction"
  function_name = var.order_finalizer_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- order-reader ---
resource "aws_apigatewayv2_integration" "order_reader" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_reader_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /orders/{orderId}"
  target             = "integrations/${aws_apigatewayv2_integration.order_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_reader" {
  statement_id  = "AllowAPIGatewayInvokeOrderReader"
  action        = "lambda:InvokeFunction"
  function_name = var.order_reader_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- menu-reader ---
resource "aws_apigatewayv2_integration" "menu_reader" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.menu_reader_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_menu" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /menu"
  target             = "integrations/${aws_apigatewayv2_integration.menu_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "menu_reader" {
  statement_id  = "AllowAPIGatewayInvokeMenuReader"
  action        = "lambda:InvokeFunction"
  function_name = var.menu_reader_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
```

- [ ] **Step 4: Pasar nuevas variables desde `BreadBoss/main.tf`**

En el bloque `module "api_gateway"` de `BreadBoss/main.tf`, agregar:

```hcl
order_finalizer_arn  = module.lambda.order_finalizer_arn
order_finalizer_name = module.lambda.order_finalizer_name
order_reader_arn     = module.lambda.order_reader_arn
order_reader_name    = module.lambda.order_reader_name
menu_reader_arn      = module.lambda.menu_reader_arn
menu_reader_name     = module.lambda.menu_reader_name
```

- [ ] **Step 5: Commit**

```bash
git add BreadBoss/modules/api_gateway/main.tf BreadBoss/modules/api_gateway/variables.tf BreadBoss/main.tf
git commit -m "feat(api_gateway): CORS, throttling y rutas order-finalizer/order-reader/menu-reader"
```

---

## Task 7: Fix `ingress` — validación, precio backend, email en evento

**Files:**
- Modify: `BreadBoss/modules/lambda/ingress/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo del handler**

```python
# BreadBoss/modules/lambda/ingress/handler.py
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
```

- [ ] **Step 2: Agregar `MENU_TABLE` a las env vars de ingress en `lambda/main.tf`**

En `local.functions`, modificar la entrada `ingress`:

```hcl
ingress = {
  env_extras = { MENU_TABLE = var.menu_table_name }
}
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/lambda/ingress/handler.py BreadBoss/modules/lambda/main.tf
git commit -m "fix(ingress): validación schema, precio desde menú, email en evento, timestamp ms, conexión global"
```

---

## Task 8: Idempotencia — helper compartido

Todos los consumers van a necesitar el mismo guard. Creamos un helper que cada handler importa.

**Files:**
- Create: `BreadBoss/modules/lambda/shared/idempotency.py`

- [ ] **Step 1: Crear el helper**

```python
# BreadBoss/modules/lambda/shared/idempotency.py
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
```

Nota: el helper asume que cada lambda tiene la env var `PROCESSED_TABLE`.

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/shared/
git commit -m "feat(lambda): helper de idempotencia compartido"
```

---

## Task 9: Fix `notifier` — email al cliente, idempotencia, logging

**Files:**
- Modify: `BreadBoss/modules/lambda/notifier/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo**

```python
# BreadBoss/modules/lambda/notifier/handler.py
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
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/notifier/handler.py
git commit -m "fix(notifier): email al cliente, idempotencia, logging estructurado"
```

---

## Task 10: Fix `stock-updater` — idempotencia, logging

**Files:**
- Modify: `BreadBoss/modules/lambda/stock-updater/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo**

```python
# BreadBoss/modules/lambda/stock-updater/handler.py
import json
import logging
import base64
import sys

import boto3

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
menu_table = dynamodb.Table("breadboss-menu")


def handler(event, context):
    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            items = payload["data"]["items"]
            order_id = payload["data"]["orderId"]

            if already_processed(order_id, "stock-updater"):
                continue

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
                    logger.warning(json.dumps({"handler": "stock-updater", "msg": "stock bajo", "itemId": item["itemId"], "stock": stock_restante}))

            logger.info(json.dumps({"orderId": order_id, "handler": "stock-updater", "msg": f"stock actualizado para {len(items)} items"}))

    return {"statusCode": 200}
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/stock-updater/handler.py
git commit -m "fix(stock-updater): idempotencia y logging estructurado"
```

---

## Task 11: Fix `kitchen-manager` — DynamoDB en transiciones, idempotencia, conexiones globales

**Files:**
- Modify: `BreadBoss/modules/lambda/kitchen-manager/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo**

```python
# BreadBoss/modules/lambda/kitchen-manager/handler.py
import json
import logging
import os
import sys
import base64
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key
from kafka import KafkaProducer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None
_producer = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


def get_producer():
    global _producer
    if _producer is None:
        tp = MSKAuthTokenProvider(region=os.environ["AWS_REGION_NAME"])
        _producer = KafkaProducer(
            bootstrap_servers=os.environ["MSK_BOOTSTRAP"].split(","),
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_oauth_token_provider=tp,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
    return _producer


def _update_dynamo_status(order_id, status):
    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        logger.warning(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "orderId no encontrado en DynamoDB"}))
        return
    item = items[0]
    orders_table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status, ":u": int(time.time() * 1000)},
    )


def handler(event, context):
    r = get_redis()
    producer = get_producer()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, "kitchen-manager"):
                continue

            now_iso = str(int(time.time() * 1000))

            r.hset(
                f"order:{order_id}",
                mapping={"status": "EN_PREPARACION", "updated_at": now_iso, "items": json.dumps(data["items"])},
            )
            r.expire(f"order:{order_id}", 7200)
            r.lpush("kitchen:queue", order_id)

            _update_dynamo_status(order_id, "EN_PREPARACION")

            producer.send(
                "orders.ready",
                key=order_id.encode(),
                value={
                    "eventType": "ORDER_READY",
                    "timestamp": int(time.time() * 1000),
                    "data": {
                        "orderId": order_id,
                        "customerId": data.get("customerId"),
                        "customerEmail": data.get("customerEmail", ""),
                        "total": data.get("total"),
                        "status": "LISTO",
                    },
                },
            )

            logger.info(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "EN_PREPARACION, ORDER_READY publicado"}))

    producer.flush()
    return {"statusCode": 200}
```

- [ ] **Step 2: Agregar `ORDERS_TABLE` a env vars de kitchen-manager en `lambda/main.tf`**

Modificar la entrada `kitchen-manager` en `local.functions`:

```hcl
kitchen-manager = {
  env_extras = {
    REDIS_HOST   = var.redis_host
    ORDERS_TABLE = var.orders_table_name
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/lambda/kitchen-manager/handler.py BreadBoss/modules/lambda/main.tf
git commit -m "fix(kitchen-manager): DynamoDB en transiciones, idempotencia, conexiones globales, logging"
```

---

## Task 12: Fix `delivery-tracker` — DynamoDB al asignar driver, idempotencia, conexión global

**Files:**
- Modify: `BreadBoss/modules/lambda/delivery-tracker/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo**

```python
# BreadBoss/modules/lambda/delivery-tracker/handler.py
import json
import logging
import os
import sys
import base64
import random
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DRIVERS = ["driver_01", "driver_02", "driver_03", "driver_04"]

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


def _update_dynamo_status(order_id, status, driver):
    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        logger.warning(json.dumps({"orderId": order_id, "handler": "delivery-tracker", "msg": "orderId no encontrado en DynamoDB"}))
        return
    item = items[0]
    orders_table.update_item(
        Key={"orderId": order_id, "timestamp": item["timestamp"]},
        UpdateExpression="SET #s = :status, driver = :driver, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":driver": driver,
            ":u": int(time.time() * 1000),
        },
    )


def handler(event, context):
    r = get_redis()

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, "delivery-tracker"):
                continue

            driver = random.choice(DRIVERS)
            now_iso = str(int(time.time() * 1000))

            r.hset(
                f"order:{order_id}",
                mapping={"status": "EN_CAMINO", "driver": driver, "updated_at": now_iso},
            )

            _update_dynamo_status(order_id, "EN_CAMINO", driver)

            logger.info(json.dumps({"orderId": order_id, "handler": "delivery-tracker", "msg": "EN_CAMINO", "driver": driver}))

    return {"statusCode": 200}
```

- [ ] **Step 2: Agregar `ORDERS_TABLE` a env vars de delivery-tracker en `lambda/main.tf`**

Modificar la entrada `delivery-tracker` en `local.functions`:

```hcl
delivery-tracker = {
  env_extras = {
    REDIS_HOST   = var.redis_host
    ORDERS_TABLE = var.orders_table_name
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/lambda/delivery-tracker/handler.py BreadBoss/modules/lambda/main.tf
git commit -m "fix(delivery-tracker): DynamoDB en asignación, idempotencia, conexión global, logging"
```

---

## Task 13: Fix `order-processor` — timestamp epoch ms, logging

**Files:**
- Modify: `BreadBoss/modules/lambda/order-processor/handler.py`

- [ ] **Step 1: Reemplazar el contenido completo**

```python
# BreadBoss/modules/lambda/order-processor/handler.py
import json
import logging
import base64
import time

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("breadboss-orders")


def handler(event, context):
    for topic, records in event["records"].items():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            created_at = int(time.time() * 1000)

            table.put_item(Item={
                "orderId":         order_id,
                "timestamp":       created_at,
                "channel":         data["channel"],
                "status":          data["status"],
                "customerId":      data["customerId"],
                "customerEmail":   data.get("customerEmail", ""),
                "items":           data["items"],
                "total":           str(data["total"]),
                "deliveryAddress": data["deliveryAddress"],
                "timestamps": {
                    "received": payload["timestamp"]
                },
            })

            logger.info(json.dumps({"orderId": order_id, "handler": "order-processor", "msg": "guardado en DynamoDB"}))

    return {"statusCode": 200}
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/order-processor/handler.py
git commit -m "fix(order-processor): timestamp epoch ms, customerEmail, logging estructurado"
```

---

## Task 14: Agregar `PROCESSED_TABLE` a todas las lambdas que usan idempotencia

**Files:**
- Modify: `BreadBoss/modules/lambda/main.tf`
- Modify: `BreadBoss/modules/lambda/variables.tf`
- Modify: `BreadBoss/main.tf`

- [ ] **Step 1: Agregar variable en `variables.tf`**

Agregar al final de `BreadBoss/modules/lambda/variables.tf`:

```hcl
variable "processed_table_name" { type = string }
```

- [ ] **Step 2: Agregar `PROCESSED_TABLE` a las env vars de consumers en `main.tf`**

Los consumers que usan el guard son: `notifier`, `stock-updater`, `kitchen-manager`, `delivery-tracker`. Actualizar cada entrada en `local.functions`:

```hcl
notifier = {
  env_extras = {
    SNS_TOPIC_ARN    = var.sns_topic_arn
    SES_SENDER       = var.ses_sender
    PROCESSED_TABLE  = var.processed_table_name
  }
}
stock-updater = {
  env_extras = {
    PROCESSED_TABLE = var.processed_table_name
  }
}
kitchen-manager = {
  env_extras = {
    REDIS_HOST       = var.redis_host
    ORDERS_TABLE     = var.orders_table_name
    PROCESSED_TABLE  = var.processed_table_name
  }
}
delivery-tracker = {
  env_extras = {
    REDIS_HOST       = var.redis_host
    ORDERS_TABLE     = var.orders_table_name
    PROCESSED_TABLE  = var.processed_table_name
  }
}
```

- [ ] **Step 3: Pasar la variable desde `BreadBoss/main.tf`**

En el bloque `module "lambda"`, agregar:

```hcl
processed_table_name = "${var.prefix}-processed"
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/lambda/main.tf BreadBoss/modules/lambda/variables.tf BreadBoss/main.tf
git commit -m "feat(lambda/tf): env var PROCESSED_TABLE en consumers con idempotencia"
```

---

## Task 15: Copiar `shared/idempotency.py` en el zip de cada consumer

El archivo `shared/idempotency.py` debe estar dentro del zip de cada lambda que lo usa. Actualizar `package.sh`.

**Files:**
- Modify: `BreadBoss/modules/lambda/package.sh`

- [ ] **Step 1: Reemplazar `package.sh`**

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Lambdas sin dependencias externas (empaquetadas por Terraform con archive_file):
# order-processor, stock-updater, notifier, order-finalizer, order-reader, menu-reader

# Lambdas con dependencias externas (requieren este script):
PACKAGED=("ingress" "kitchen-manager" "delivery-tracker")

# Lambdas que usan el helper de idempotencia (necesitan shared/idempotency.py en el zip)
NEEDS_SHARED=("stock-updater" "notifier" "kitchen-manager" "delivery-tracker")

for lambda in "${PACKAGED[@]}"; do
  echo "Empaquetando $lambda..."
  cd "$SCRIPT_DIR/$lambda"

  rm -rf package
  mkdir package

  pip3 install -r requirements.txt -t ./package --quiet

  # Copiar shared helper
  mkdir -p ./package/shared
  cp "$SCRIPT_DIR/shared/idempotency.py" ./package/shared/

  cd package
  zip -r "../${lambda}.zip" . --quiet
  cd ..

  zip "${lambda}.zip" handler.py --quiet

  rm -rf package
  echo "${lambda}.zip listo"
  cd "$SCRIPT_DIR"
done

echo ""
echo "Zips generados:"
ls -lh *//*.zip 2>/dev/null || ls */*.zip
```

Nota: `stock-updater` y `notifier` son "simple functions" empaquetadas por `archive_file` de Terraform — pero ahora necesitan el helper. Tenemos dos opciones:
- **Opción A (recomendada):** moverlos a `packaged_functions` y agregar un `requirements.txt` vacío.
- Opción B: usar `archive_file` con `source_dir` en vez de `source_file`.

Usamos Opción A por consistencia con el patrón existente.

- [ ] **Step 2: Crear `requirements.txt` vacío para `stock-updater` y `notifier`**

```bash
touch BreadBoss/modules/lambda/stock-updater/requirements.txt
touch BreadBoss/modules/lambda/notifier/requirements.txt
```

- [ ] **Step 3: Mover `stock-updater` y `notifier` a `packaged_functions` en `main.tf`**

Cambiar `local.simple_functions`:

```hcl
simple_functions = toset(["order-processor", "order-finalizer", "order-reader", "menu-reader"])
```

Cambiar `local.packaged_functions`:

```hcl
packaged_functions = toset(["ingress", "kitchen-manager", "delivery-tracker", "stock-updater", "notifier"])
```

(Solo es documentación/comentario — Terraform no usa `packaged_functions` como variable, la lógica es `NOT in simple_functions`.)

- [ ] **Step 4: Agregar `shared/idempotency.py` al zip de lambdas simples que lo necesitan**

`order-processor` no usa idempotencia. Los otros simples (`order-finalizer`, `order-reader`, `menu-reader`) tampoco. Ningún simple usa idempotencia. ✅ No se necesita cambio adicional para los simples.

- [ ] **Step 5: Actualizar la lista en `package.sh` para incluir stock-updater y notifier**

El script del Step 1 ya incluye solo `ingress`, `kitchen-manager`, `delivery-tracker`. `stock-updater` y `notifier` ahora deben aparecer en el loop también. Actualizar `PACKAGED`:

```bash
PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier")
```

Y el script final queda:

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier")

for lambda in "${PACKAGED[@]}"; do
  echo "Empaquetando $lambda..."
  cd "$SCRIPT_DIR/$lambda"

  rm -rf package
  mkdir package

  if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt -t ./package --quiet
  fi

  mkdir -p ./package/shared
  cp "$SCRIPT_DIR/shared/idempotency.py" ./package/shared/

  cd package
  zip -r "../${lambda}.zip" . --quiet
  cd ..

  zip "${lambda}.zip" handler.py --quiet

  rm -rf package
  echo "${lambda}.zip listo"
  cd "$SCRIPT_DIR"
done

echo ""
echo "Zips generados:"
find . -name "*.zip" | head -20
```

- [ ] **Step 6: Actualizar `local.simple_functions` en `main.tf`**

```hcl
simple_functions = toset(["order-processor", "order-finalizer", "order-reader", "menu-reader"])
```

- [ ] **Step 7: Commit**

```bash
git add BreadBoss/modules/lambda/package.sh \
        BreadBoss/modules/lambda/shared/ \
        BreadBoss/modules/lambda/stock-updater/requirements.txt \
        BreadBoss/modules/lambda/notifier/requirements.txt \
        BreadBoss/modules/lambda/main.tf
git commit -m "feat(lambda): shared idempotency helper, actualizar package.sh y simple_functions"
```

---

## Task 16: Verificación de terraform fmt y validación

- [ ] **Step 1: Formatear todos los archivos `.tf` modificados**

```bash
cd BreadBoss && terraform fmt -recursive
```

- [ ] **Step 2: Verificar que `terraform validate` pasa (requiere `terraform init` previo)**

```bash
terraform init -backend=false 2>/dev/null || echo "init requiere backend — skip"
terraform validate
```

Si `validate` falla por variables no definidas en tfvars, es esperado — los errores de tipo y referencias a recursos son los relevantes.

- [ ] **Step 3: Commit del fmt si hay cambios**

```bash
git add -u
git status
# Solo commitear si hay cambios
git diff --cached --quiet || git commit -m "style(tf): terraform fmt"
```

---

## Checklist final

- [ ] `dynamodb/main.tf` tiene tabla `breadboss-processed` con TTL
- [ ] `order-finalizer/handler.py` cierra pedido con `ENTREGADO` + `tiempo_entrega_min`
- [ ] `order-reader/handler.py` retorna pedido por ID
- [ ] `menu-reader/handler.py` retorna lista del menú
- [ ] `ingress/handler.py` valida schema, calcula precio desde menú, incluye `customerEmail`, usa epoch ms, conexión global
- [ ] `notifier/handler.py` envía al `customerEmail`, tiene guard de idempotencia
- [ ] `stock-updater/handler.py` tiene guard de idempotencia
- [ ] `kitchen-manager/handler.py` actualiza DynamoDB en transición, tiene guard de idempotencia
- [ ] `delivery-tracker/handler.py` actualiza DynamoDB al asignar driver, tiene guard de idempotencia
- [ ] `order-processor/handler.py` usa timestamp epoch ms, guarda `customerEmail`
- [ ] `lambda/main.tf` tiene las 3 nuevas lambdas registradas con env vars correctas
- [ ] `api_gateway/main.tf` tiene CORS, throttling y 3 rutas nuevas
- [ ] `shared/idempotency.py` copiado en el zip de cada consumer
- [ ] `package.sh` incluye las lambdas con dependencias
- [ ] `terraform fmt` pasa sin cambios
