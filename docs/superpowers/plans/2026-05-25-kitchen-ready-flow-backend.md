# Kitchen Ready Flow — Backend Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Romper el auto-transition `EN_PREPARACION → EN_CAMINO` introduciendo un endpoint manual `POST /orders/{id}/ready` para que la pantalla de cocina (que se construirá en un plan posterior) marque pedidos como listos, y exponer `GET /orders?status=...` para listar pedidos pendientes de cocina.

**Architecture:** Se modifica `kitchen-manager` para que solo ponga el pedido en `EN_PREPARACION` (deja de publicar `ORDER_READY`). Se agrega una nueva Lambda `order-ready` detrás de `POST /orders/{orderId}/ready` que publica `ORDER_READY` a Kafka (dispara `delivery-tracker` + `notifier` como hoy). Se extiende `order-reader` para soportar listado por `status` en `GET /orders`. Todo el trabajo se hace en una rama nueva `feature/kitchen-ready-flow`.

**Tech Stack:** Python 3.11 Lambdas, Terraform (AWS Provider), API Gateway HTTP API + JWT (Cognito), MSK (Kafka), DynamoDB, Redis (ElastiCache), `confluent-kafka`, `aws-msk-iam-sasl-signer`.

---

## File Structure

**Files a crear:**
- `BreadBoss/modules/lambda/order-ready/handler.py` — Lambda detrás de `POST /orders/{orderId}/ready`. Valida estado actual en DynamoDB, publica `ORDER_READY` a Kafka topic `orders.ready`.
- `BreadBoss/modules/lambda/order-ready/requirements.txt` — `confluent-kafka` + `aws-msk-iam-sasl-signer-python`.

**Files a modificar:**
- `BreadBoss/modules/lambda/kitchen-manager/handler.py` — eliminar el `producer.produce("orders.ready", ...)`. El consumer solo deja `EN_PREPARACION` en Redis + DynamoDB.
- `BreadBoss/modules/lambda/kitchen-manager/requirements.txt` — eliminar `confluent-kafka` y `aws-msk-iam-sasl-signer-python` (ya no producen).
- `BreadBoss/modules/lambda/order-reader/handler.py` — soportar `GET /orders?status=XXX` (sin `pathParameters.orderId`) usando `Scan` con `FilterExpression`.
- `BreadBoss/modules/lambda/main.tf` — agregar `order-ready` a `packaged_functions`, su `env_extras`, y su `lambda_permission` para Kafka publishing está cubierto por el role compartido.
- `BreadBoss/modules/lambda/outputs.tf` — exponer `order_ready_arn` y `order_ready_name`.
- `BreadBoss/modules/lambda/package.sh` — agregar `order-ready` al array `PACKAGED`.
- `BreadBoss/modules/api_gateway/variables.tf` — variables `order_ready_arn` y `order_ready_name`.
- `BreadBoss/modules/api_gateway/main.tf` — nueva integration + ruta `POST /orders/{orderId}/ready` + permission, y nueva ruta `GET /orders` que apunta a `order-reader`.
- `BreadBoss/main.tf` — pasar `order_ready_arn` y `order_ready_name` al módulo `api_gateway`.
- `TEST_E2E.md` — agregar paso para `POST /orders/{id}/ready` y `GET /orders?status=EN_PREPARACION`.

---

## Task 1: Crear rama de feature

**Files:** N/A (operación git)

- [ ] **Step 1: Verificar working tree limpio**

Run: `git status`
Expected: `nothing to commit, working tree clean` en branch `main`.

- [ ] **Step 2: Crear y cambiar a la rama nueva**

Run: `git checkout -b feature/kitchen-ready-flow`
Expected: `Switched to a new branch 'feature/kitchen-ready-flow'`.

---

## Task 2: Modificar `kitchen-manager` — eliminar publicación de `ORDER_READY`

**Files:**
- Modify: `BreadBoss/modules/lambda/kitchen-manager/handler.py`
- Modify: `BreadBoss/modules/lambda/kitchen-manager/requirements.txt`

- [ ] **Step 1: Editar `handler.py` — eliminar Kafka producer y la publicación**

Reemplazar el contenido completo de `BreadBoss/modules/lambda/kitchen-manager/handler.py` por:

```python
import json
import logging
import os
import sys
import base64
import time

import boto3
import redis
from boto3.dynamodb.conditions import Key

sys.path.insert(0, "/var/task/shared")
from idempotency import already_processed  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ.get("ORDERS_TABLE", "breadboss-orders"))

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=os.environ["REDIS_HOST"], port=6379, ssl=True)
    return _redis


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

    for records in event["records"].values():
        for record in records:
            payload = json.loads(base64.b64decode(record["value"]).decode())
            data = payload["data"]
            order_id = data["orderId"]

            if already_processed(order_id, "kitchen-manager"):
                continue

            now_ms = int(time.time() * 1000)

            r.hset(
                f"order:{order_id}",
                mapping={"status": "EN_PREPARACION", "updated_at": str(now_ms), "items": json.dumps(data["items"])},
            )
            r.expire(f"order:{order_id}", 7200)
            r.lpush("kitchen:queue", order_id)

            _update_dynamo_status(order_id, "EN_PREPARACION")

            logger.info(json.dumps({"orderId": order_id, "handler": "kitchen-manager", "msg": "EN_PREPARACION — esperando confirmacion manual"}))

    return {"statusCode": 200}
```

- [ ] **Step 2: Editar `requirements.txt` — quitar deps de Kafka**

Reemplazar el contenido completo de `BreadBoss/modules/lambda/kitchen-manager/requirements.txt` por:

```
redis
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/lambda/kitchen-manager/handler.py BreadBoss/modules/lambda/kitchen-manager/requirements.txt
git commit -m "refactor(kitchen-manager): drop auto-publish of ORDER_READY"
```

---

## Task 3: Crear lambda `order-ready`

**Files:**
- Create: `BreadBoss/modules/lambda/order-ready/handler.py`
- Create: `BreadBoss/modules/lambda/order-ready/requirements.txt`

- [ ] **Step 1: Crear `handler.py`**

Contenido completo de `BreadBoss/modules/lambda/order-ready/handler.py`:

```python
import json
import logging
import os
import time

import boto3
import certifi
from boto3.dynamodb.conditions import Key
from confluent_kafka import Producer
from aws_msk_iam_sasl_signer.MSKAuthTokenProvider import generate_auth_token

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])

_producer = None


def _oauth_cb(oauth_config):
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    token, expiry_ms = generate_auth_token(region)
    return token, expiry_ms / 1000


def get_producer():
    global _producer
    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": os.environ["MSK_BOOTSTRAP"],
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "OAUTHBEARER",
            "oauth_cb": _oauth_cb,
            "ssl.ca.location": certifi.where(),
            "message.timeout.ms": "45000",
        })
    return _producer


def handler(event, context):
    order_id = event["pathParameters"]["orderId"]

    resp = orders_table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}

    item = items[0]
    current_status = item.get("status")

    if current_status in ("EN_CAMINO", "ENTREGADO"):
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"orderId": order_id, "status": current_status, "message": "Ya estaba marcado"}),
        }

    if current_status != "EN_PREPARACION":
        return {
            "statusCode": 409,
            "body": json.dumps({"error": f"El pedido esta en estado '{current_status}', solo se puede marcar listo desde EN_PREPARACION"}),
        }

    now_ms = int(time.time() * 1000)
    customer_id = item.get("customerId")
    customer_email = item.get("customerEmail", "")
    total = item.get("total")

    delivery_errors = []

    def _delivery_cb(err, msg):
        if err:
            delivery_errors.append(str(err))
            logger.error(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": f"delivery error: {err}"}))

    producer = get_producer()
    producer.produce(
        "orders.ready",
        key=order_id.encode(),
        value=json.dumps({
            "eventType": "ORDER_READY",
            "timestamp": now_ms,
            "data": {
                "orderId": order_id,
                "customerId": customer_id,
                "customerEmail": customer_email,
                "total": str(total) if total is not None else None,
                "status": "LISTO",
            },
        }).encode(),
        callback=_delivery_cb,
    )
    remaining = producer.flush(timeout=20)
    producer.poll(0)
    if remaining > 0 or delivery_errors:
        logger.error(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": f"fallo al publicar ORDER_READY, remaining={remaining}, errors={delivery_errors}"}))
        return {"statusCode": 500, "body": json.dumps({"error": "Error publicando evento"})}

    logger.info(json.dumps({"orderId": order_id, "handler": "order-ready", "msg": "ORDER_READY publicado"}))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"orderId": order_id, "status": "LISTO", "message": "Pedido marcado como listo"}),
    }
```

- [ ] **Step 2: Crear `requirements.txt`**

Contenido completo de `BreadBoss/modules/lambda/order-ready/requirements.txt`:

```
confluent-kafka
aws-msk-iam-sasl-signer-python
certifi
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/lambda/order-ready/handler.py BreadBoss/modules/lambda/order-ready/requirements.txt
git commit -m "feat(order-ready): nueva lambda que publica ORDER_READY manualmente"
```

---

## Task 4: Extender `order-reader` para listar pedidos por `status`

**Files:**
- Modify: `BreadBoss/modules/lambda/order-reader/handler.py`

- [ ] **Step 1: Reemplazar `handler.py`**

Contenido completo de `BreadBoss/modules/lambda/order-reader/handler.py`:

```python
import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def _get_one(order_id):
    resp = table.query(
        KeyConditionExpression=Key("orderId").eq(order_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode": 404, "body": json.dumps({"error": "Pedido no encontrado"})}
    item = json.loads(json.dumps(items[0], default=str))
    logger.info(json.dumps({"orderId": order_id, "handler": "order-reader", "msg": "found"}))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(item),
    }


def _list_by_status(status):
    resp = table.scan(FilterExpression=Attr("status").eq(status))
    raw = resp.get("Items", [])
    items = json.loads(json.dumps(raw, default=str))
    logger.info(json.dumps({"handler": "order-reader", "msg": "list", "status": status, "count": len(items)}))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"items": items, "count": len(items)}),
    }


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("orderId")
    if order_id:
        return _get_one(order_id)

    qs = event.get("queryStringParameters") or {}
    status = qs.get("status")
    if not status:
        return {"statusCode": 400, "body": json.dumps({"error": "Falta query param 'status'"})}
    return _list_by_status(status)
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/lambda/order-reader/handler.py
git commit -m "feat(order-reader): soporta GET /orders?status=XXX"
```

---

## Task 5: Registrar `order-ready` en el módulo Terraform de Lambdas

**Files:**
- Modify: `BreadBoss/modules/lambda/main.tf`
- Modify: `BreadBoss/modules/lambda/outputs.tf`
- Modify: `BreadBoss/modules/lambda/package.sh`

- [ ] **Step 1: Editar `main.tf` — agregar `order-ready` a `packaged_functions` y `functions`**

En `BreadBoss/modules/lambda/main.tf`, reemplazar el bloque `locals` (líneas 1–62) por:

```hcl
locals {
  lambdas_dir = path.module

  # Lambdas sin dependencias externas: boto3 ya viene en el runtime de Lambda.
  # Terraform empaqueta el .py directamente con archive_file.
  simple_functions = toset(["order-processor", "order-finalizer", "order-reader", "menu-reader"])

  # Lambdas con dependencias externas (kafka, redis): requieren pip install previo.
  # El zip se construye con package.sh y Terraform lo referencia ya construido.
  packaged_functions = toset(["ingress", "kitchen-manager", "delivery-tracker", "stock-updater", "notifier", "order-ready"])

  functions = {
    ingress = {
      env_extras = { MENU_TABLE = var.menu_table_name }
    }
    order-processor = {
      env_extras = { ORDERS_TABLE = var.orders_table_name }
    }
    kitchen-manager = {
      env_extras = {
        REDIS_HOST      = var.redis_host
        ORDERS_TABLE    = var.orders_table_name
        PROCESSED_TABLE = var.processed_table_name
      }
    }
    stock-updater = {
      env_extras = {
        MENU_TABLE      = var.menu_table_name
        PROCESSED_TABLE = var.processed_table_name
      }
    }
    delivery-tracker = {
      env_extras = {
        REDIS_HOST      = var.redis_host
        ORDERS_TABLE    = var.orders_table_name
        PROCESSED_TABLE = var.processed_table_name
      }
    }
    notifier = {
      env_extras = {
        SNS_TOPIC_ARN   = var.sns_topic_arn
        SES_SENDER      = var.ses_sender
        PROCESSED_TABLE = var.processed_table_name
      }
    }
    order-finalizer = {
      env_extras = { ORDERS_TABLE = var.orders_table_name }
    }
    order-reader = {
      env_extras = { ORDERS_TABLE = var.orders_table_name }
    }
    menu-reader = {
      env_extras = { MENU_TABLE = var.menu_table_name }
    }
    order-ready = {
      env_extras = { ORDERS_TABLE = var.orders_table_name }
    }
  }

  # Consumers del topic "pedidos" (ORDER_CREATED)
  consumers_orders_created = ["order-processor", "kitchen-manager", "stock-updater", "notifier"]

  # Consumers del topic "orders.ready" (ORDER_READY — publicado por order-ready via API)
  consumers_orders_ready = ["delivery-tracker", "notifier"]
}
```

- [ ] **Step 2: Editar `outputs.tf` — exponer `order_ready_arn` y `order_ready_name`**

Agregar al final de `BreadBoss/modules/lambda/outputs.tf`:

```hcl
output "order_ready_arn" { value = aws_lambda_function.this["order-ready"].arn }
output "order_ready_name" { value = aws_lambda_function.this["order-ready"].function_name }
```

- [ ] **Step 3: Editar `package.sh` — agregar `order-ready` al array `PACKAGED`**

Cambiar la línea de `PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier")` por:

```bash
PACKAGED=("ingress" "kitchen-manager" "delivery-tracker" "stock-updater" "notifier" "order-ready")
```

- [ ] **Step 4: Ejecutar `package.sh` para generar los zips actualizados**

Run: `cd BreadBoss/modules/lambda && bash package.sh && cd -`
Expected: imprime `order-ready.zip listo` y `kitchen-manager.zip listo` (este último ya sin Kafka deps).

- [ ] **Step 5: Validar Terraform**

Run: `cd BreadBoss && terraform validate && cd -`
Expected: `Success! The configuration is valid.`

- [ ] **Step 6: Commit**

```bash
git add BreadBoss/modules/lambda/main.tf BreadBoss/modules/lambda/outputs.tf BreadBoss/modules/lambda/package.sh BreadBoss/modules/lambda/order-ready/order-ready.zip BreadBoss/modules/lambda/kitchen-manager/kitchen-manager.zip
git commit -m "infra(lambda): registrar order-ready y reempaquetar kitchen-manager"
```

---

## Task 6: Wiring en API Gateway — nuevas rutas `POST /orders/{orderId}/ready` y `GET /orders`

**Files:**
- Modify: `BreadBoss/modules/api_gateway/variables.tf`
- Modify: `BreadBoss/modules/api_gateway/main.tf`
- Modify: `BreadBoss/main.tf`

- [ ] **Step 1: Agregar variables nuevas en `variables.tf`**

Agregar al final de `BreadBoss/modules/api_gateway/variables.tf`:

```hcl
variable "order_ready_arn" { type = string }
variable "order_ready_name" { type = string }
```

- [ ] **Step 2: Agregar integration + ruta + permission en `api_gateway/main.tf`**

Agregar al final de `BreadBoss/modules/api_gateway/main.tf`:

```hcl
# --- order-ready (POST /orders/{orderId}/ready) ---
resource "aws_apigatewayv2_integration" "order_ready" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_ready_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ready_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /orders/{orderId}/ready"
  target             = "integrations/${aws_apigatewayv2_integration.order_ready.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_ready" {
  statement_id  = "AllowAPIGatewayInvokeOrderReady"
  action        = "lambda:InvokeFunction"
  function_name = var.order_ready_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- GET /orders (lista por status, mismo Lambda que GET /orders/{orderId}) ---
resource "aws_apigatewayv2_route" "list_orders" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /orders"
  target             = "integrations/${aws_apigatewayv2_integration.order_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}
```

- [ ] **Step 3: Pasar las nuevas variables desde `BreadBoss/main.tf`**

En `BreadBoss/main.tf`, en el bloque `module "api_gateway"` (al final del bloque, antes del `}` de cierre), agregar:

```hcl
  order_ready_arn      = module.lambda.order_ready_arn
  order_ready_name     = module.lambda.order_ready_name
```

- [ ] **Step 4: Validar Terraform**

Run: `cd BreadBoss && terraform validate && cd -`
Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Planear cambios (sin aplicar)**

Run: `cd BreadBoss && terraform plan -out=/tmp/breadboss.tfplan && cd -`
Expected: el plan debe mostrar — crear `aws_lambda_function.this["order-ready"]`, `aws_apigatewayv2_integration.order_ready`, `aws_apigatewayv2_route.ready_order`, `aws_apigatewayv2_route.list_orders`, `aws_lambda_permission.order_ready`, `aws_cloudwatch_log_group.lambda["order-ready"]`; modificar `aws_lambda_function.this["kitchen-manager"]` (cambio de hash del zip). Ningún recurso para destruir excepto los esperados.

- [ ] **Step 6: Aplicar el plan**

Run: `cd BreadBoss && terraform apply /tmp/breadboss.tfplan && cd -`
Expected: `Apply complete!` sin errores.

- [ ] **Step 7: Commit**

```bash
git add BreadBoss/modules/api_gateway/variables.tf BreadBoss/modules/api_gateway/main.tf BreadBoss/main.tf
git commit -m "infra(api): rutas POST /orders/{id}/ready y GET /orders"
```

---

## Task 7: Probar el flujo end-to-end contra AWS

**Files:** N/A (smoke tests)

- [ ] **Step 1: Obtener token JWT (asumiendo que ya hay un usuario Cognito de test)**

Seguir el `Paso 2` de `TEST_E2E.md` para extraer `ID_TOKEN`. Guardar `API_URL` desde `terraform output`.

- [ ] **Step 2: Crear un pedido**

Run:
```bash
curl -s -X POST "$API_URL/orders" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deliveryAddress":"Calle Test 123","items":[{"itemId":"empanada-carne","qty":2}]}'
```
Expected: `201` + JSON con `orderId` y `status: "RECIBIDO"`. Guardar el `orderId` en `ORDER_ID`.

- [ ] **Step 3: Esperar ~5 s y verificar que el pedido quedó en `EN_PREPARACION` (sin avanzar solo)**

Run:
```bash
sleep 5 && curl -s "$API_URL/orders/$ORDER_ID" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: JSON con `"status": "EN_PREPARACION"`. **No** debe estar en `EN_CAMINO` (eso confirma que `kitchen-manager` ya no publica `ORDER_READY` solo).

- [ ] **Step 4: Listar pedidos `EN_PREPARACION` (endpoint para la futura UI de cocina)**

Run:
```bash
curl -s "$API_URL/orders?status=EN_PREPARACION" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: JSON `{"items":[...], "count": N}` que incluye el `orderId` de Step 2.

- [ ] **Step 5: Marcar pedido como listo (acción manual de cocina)**

Run:
```bash
curl -s -X POST "$API_URL/orders/$ORDER_ID/ready" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: `200` + JSON `{"orderId":"...","status":"LISTO","message":"Pedido marcado como listo"}`.

- [ ] **Step 6: Verificar que el pedido avanzó a `EN_CAMINO`**

Run:
```bash
sleep 5 && curl -s "$API_URL/orders/$ORDER_ID" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: JSON con `"status": "EN_CAMINO"`.

- [ ] **Step 7: Reintentar `/ready` (idempotencia)**

Run:
```bash
curl -s -X POST "$API_URL/orders/$ORDER_ID/ready" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: `200` con `{"status":"EN_CAMINO","message":"Ya estaba marcado"}` (no error, no doble publicación).

- [ ] **Step 8: Cerrar el pedido**

Run:
```bash
curl -s -X POST "$API_URL/orders/$ORDER_ID/deliver" -H "Authorization: Bearer $ID_TOKEN"
```
Expected: `200` con `"status":"ENTREGADO"` y `tiempo_entrega_min`.

---

## Task 8: Actualizar documentación de testing

**Files:**
- Modify: `TEST_E2E.md`

- [ ] **Step 1: Actualizar el diagrama de flujo y agregar pasos para `/ready` y listado**

En `TEST_E2E.md`:
1. En el diagrama del "Flujo del sistema (actualizado)" reemplazar la sección de `kitchen-manager` para que indique que solo publica `EN_PREPARACION` (sin `ORDER_READY`), y agregar un nodo `POST /orders/{id}/ready → order-ready → publica ORDER_READY` antes de la rama `delivery-tracker / notifier`.
2. Agregar en "Cosas a saber antes de testear" un punto 4 que diga: "**El paso `EN_PREPARACION → EN_CAMINO` ahora es manual.** Hay que llamar `POST /orders/{id}/ready` (simulando el admin de cocina) — antes era automático."
3. Agregar al checklist los nuevos pasos:
   - `Paso 6k` — `GET /orders?status=EN_PREPARACION` devuelve el pedido recién creado.
   - `Paso 6l` — `POST /orders/{id}/ready` responde `200` con `status: LISTO`.
   - `Paso 6m` — `GET /orders/{id}` retorna `status: EN_CAMINO` tras unos segundos.
   - `Paso 6n` — Segunda llamada a `/ready` devuelve `Ya estaba marcado` (idempotencia OK).

- [ ] **Step 2: Commit**

```bash
git add TEST_E2E.md
git commit -m "docs(test-e2e): documentar flujo manual EN_PREPARACION → EN_CAMINO"
```

---

## Task 9: Cierre

**Files:** N/A

- [ ] **Step 1: Push a remoto**

Run: `git push -u origin feature/kitchen-ready-flow`
Expected: rama subida; no abrir PR aún (se hará tras el plan de frontend).

- [ ] **Step 2: Resumen al usuario**

Confirmar que el backend está deployado, los smoke tests pasan, y proponer arrancar el plan del frontend (menú, tracking, pantalla de cocina).
