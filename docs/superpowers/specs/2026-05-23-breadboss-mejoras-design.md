# BreadBoss — Mejoras prioritarias

**Fecha:** 2026-05-23  
**Rama:** worktree-feature+breadboss-mejoras  
**Scope:** Trabajo universitario — prioriza corrección funcional sobre hardening de producción.

---

## Resumen

Implementación de las mejoras críticas y altas identificadas en `PLAN_MEJORA.md`. El sistema actualmente tiene 3 bugs que rompen el ciclo de negocio (C1, C2, C3) y varios problemas de calidad. Este spec cubre los cambios necesarios para que el sistema cumpla su ciclo completo de forma correcta.

**Skipped intencionalmente:** DLQ (A2), IAM por función (A1), tests unitarios (M6), Secrets Manager (A5), X-Ray profundo (M8).

---

## Componentes nuevos

### Lambda `order-finalizer`

- **Trigger:** Kafka topic `orders.delivered`
- **Acción:** Lee `orderId` del evento, calcula `tiempo_entrega_min` como diferencia entre `createdAt` y timestamp actual, escribe en DynamoDB `status=ENTREGADO` + `tiempo_entrega_min` + `updatedAt`.
- **Idempotencia:** Si el pedido ya está en `ENTREGADO`, retorna sin modificar.
- **Path:** `BreadBoss/modules/lambda/order-finalizer/`

### Lambda `order-reader`

- **Trigger:** API Gateway `GET /orders/{id}`
- **Acción:** Lee de DynamoDB por `orderId`. Si no existe → 404. Si existe → 200 con el item.
- **Path:** `BreadBoss/modules/lambda/order-reader/`

### Lambda `menu-reader`

- **Trigger:** API Gateway `GET /menu`
- **Acción:** Scan de tabla `breadboss-menu`, retorna lista de items.
- **Path:** `BreadBoss/modules/lambda/menu-reader/`

### Tabla DynamoDB `breadboss-processed`

- **PK:** `orderId` (S)
- **SK:** `consumer` (S) — nombre del lambda (e.g. `stock-updater`, `notifier`)
- **TTL:** `expiresAt` — 24h desde creación (evita crecimiento indefinido)
- **Uso:** Guard de idempotencia en todos los consumers.

---

## Cambios en lambdas existentes

### `ingress/handler.py`

1. **Validación de schema:** Verificar que `items` sea lista no vacía, cada item tenga `itemId` (string), `qty` (int > 0). Usar validación manual (sin deps extras).
2. **Precio desde backend:** Lookup en `breadboss-menu` por cada `itemId`. Si no existe → 400. Calcular `total` con precio del menú, no el del cliente.
3. **Email en evento:** Extraer `email` de los claims del JWT (campo `email` en el payload decodificado — Cognito lo incluye por defecto). Agregar al evento `ORDER_CREATED`.
4. **Timestamp unificado:** Usar `int(time.time() * 1000)` (epoch ms) para `createdAt`.
5. **Conexión Kafka:** Mover `KafkaProducer` a scope de módulo con lazy init.
6. **Logging:** Reemplazar `print()` con `logging`.

### `notifier/handler.py`

1. **Email destino:** Leer `email` del evento. Si no está presente → log warning + skip (compatibilidad con eventos viejos).
2. **Idempotencia:** Guard con tabla `breadboss-processed` antes de enviar.
3. **Logging:** Reemplazar `print()`.

### `stock-updater/handler.py`

1. **Idempotencia:** Guard con tabla `breadboss-processed` antes de decrementar stock.
2. **Logging:** Reemplazar `print()`.

### `kitchen-manager/handler.py`

1. **DynamoDB update:** Además de escribir en Redis, actualizar `status=EN_PREPARACION` en DynamoDB al recibir `ORDER_CREATED`, y `status=EN_PREPARACION` → `status=LISTO` al publicar `ORDER_READY`.
2. **Idempotencia:** Guard antes de procesar.
3. **Conexiones:** Mover Redis client y KafkaProducer a scope de módulo.
4. **Logging:** Reemplazar `print()`.

### `delivery-tracker/handler.py`

1. **DynamoDB update:** Actualizar `status=EN_CAMINO` en DynamoDB al asignar repartidor.
2. **Idempotencia:** Guard antes de procesar.
3. **Conexión Redis:** Mover a scope de módulo.
4. **Logging:** Reemplazar `print()`.

### `order-processor/handler.py`

1. **Timestamp:** Usar epoch ms para `createdAt`.
2. **Logging:** Reemplazar `print()`.

---

## Infraestructura (Terraform)

### API Gateway

- **CORS:** Agregar `cors_configuration` con `allow_origins=["*"]`, `allow_methods=["GET","POST","OPTIONS"]`, `allow_headers=["authorization","content-type"]`.
- **Rate limiting:** `default_route_settings` con `throttling_burst_limit=100`, `throttling_rate_limit=50`.
- **Rutas nuevas:** `GET /orders/{orderId}` → `order-reader`, `GET /menu` → `menu-reader`, `POST /orders/{orderId}/deliver` → trigger de `order-finalizer` vía Kafka.

### DynamoDB

- Nueva tabla `breadboss-processed` con TTL habilitado.

### Lambda `main.tf`

- Agregar las 3 nuevas lambdas (`order-finalizer`, `order-reader`, `menu-reader`).
- `order-finalizer` con event source mapping al topic `orders.delivered`.

---

## Data flow completo (post-mejoras)

```
Cliente → POST /orders
  → ingress: valida schema, calcula total con precio menú, extrae email del JWT
  → Kafka: ORDER_CREATED {orderId, items, total, customerId, email, createdAt(ms)}

ORDER_CREATED → fan-out:
  → order-processor: guarda en DynamoDB (status=RECIBIDO, epoch ms)
  → stock-updater: decrementa stock (con guard idempotencia)
  → kitchen-manager: actualiza DynamoDB status=EN_PREPARACION + Redis + publica ORDER_READY

ORDER_READY → fan-out:
  → delivery-tracker: asigna driver, actualiza DynamoDB status=EN_CAMINO + Redis
  → notifier: envía email al cliente (con guard idempotencia)

Operador → POST /orders/{id}/deliver
  → publica a orders.delivered
  → order-finalizer: DynamoDB status=ENTREGADO + tiempo_entrega_min

Cliente → GET /orders/{id} → order-reader → DynamoDB
Cliente → GET /menu → menu-reader → DynamoDB breadboss-menu
```

---

## Timestamps

Estándar unificado: **Unix epoch milisegundos** (`int(time.time() * 1000)`). Compatible con el seed existente. Todos los campos `createdAt`, `updatedAt`, `deliveredAt` en este formato.

---

## Logging

Formato estructurado en todos los handlers:

```python
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Uso:
logger.info(json.dumps({"orderId": order_id, "handler": "notifier", "msg": "email sent"}))
```

---

## Archivos que se crean / modifican

**Nuevos:**
- `BreadBoss/modules/lambda/order-finalizer/handler.py`
- `BreadBoss/modules/lambda/order-reader/handler.py`
- `BreadBoss/modules/lambda/menu-reader/handler.py`

**Modificados:**
- `BreadBoss/modules/lambda/ingress/handler.py`
- `BreadBoss/modules/lambda/notifier/handler.py`
- `BreadBoss/modules/lambda/stock-updater/handler.py`
- `BreadBoss/modules/lambda/kitchen-manager/handler.py`
- `BreadBoss/modules/lambda/delivery-tracker/handler.py`
- `BreadBoss/modules/lambda/order-processor/handler.py`
- `BreadBoss/modules/lambda/main.tf` — nuevas lambdas + event source mapping
- `BreadBoss/modules/dynamodb/main.tf` — tabla breadboss-processed
- `BreadBoss/modules/api_gateway/main.tf` — CORS, throttling, rutas nuevas
