# Plan de mejora — BreadBoss

Análisis integral del sistema (event-driven con Kafka + Lambdas) y plan priorizado de mejoras.

**Snapshot del repo:** `main` @ 2026-05-23 — post fixes de `stock-updater` (tabla) y `auditor` (default).

---

## Resumen ejecutivo

El sistema implementa correctamente el **pattern event-driven** (fan-out via Kafka, consumers independientes), pero la implementación tiene **3 problemas críticos** que rompen funcionalidad de negocio y **5 problemas altos** de seguridad/calidad. El resto son optimizaciones.

**Lo más urgente:**
1. **El cliente nunca recibe notificaciones** (`notifier` se manda mails a sí mismo).
2. **El ciclo de vida del pedido nunca se cierra** (siempre queda en `RECIBIDO` en DynamoDB).
3. **Los consumers no son idempotentes** — un mensaje reentregado por Kafka duplica el efecto (stock decrementado 2 veces, mails repetidos).

Si se solucionan estos 3, el sistema cumple el ciclo de negocio básico.

---

## Hallazgos por severidad

### 🔴 Críticos — rompen funcionalidad

#### C1. El flujo nunca llega a `ENTREGADO` / `FINALIZADA`

**Síntoma:** El último estado que setea algún handler es `EN_CAMINO` en Redis (delivery-tracker). En DynamoDB el pedido queda en `RECIBIDO` para siempre.

**Causas:**
- `order-processor` escribe el pedido con `status=RECIBIDO` y nadie más toca la tabla.
- Las transiciones `EN_PREPARACION` / `EN_CAMINO` se guardan **solo en Redis**, y Redis tiene `TTL=7200s` (`kitchen-manager:43`) → a las 2h desaparecen.
- No existen los eventos `ORDER_PICKED_UP` ni `ORDER_DELIVERED`. Tampoco existe ningún trigger externo (UI de cocina, app del repartidor) que dispare el cierre.
- `kitchen-manager` publica `ORDER_READY` instantáneamente al recibir `ORDER_CREATED` — no modela tiempo de cocción.

**Impacto:**
- El dashboard que lee de DynamoDB ve todos los pedidos como `RECIBIDO`.
- El GSI `status-index` de DynamoDB está totalmente desperdiciado.
- El **auditor espera datos terminales** (`status: "entregado"`, `tiempo_entrega_min`) — los obtiene del seed, pero los pedidos reales nunca los van a tener.

**Fix sugerido:**
- Agregar lambda `order-finalizer` que consuma un topic `orders.delivered` y actualice DynamoDB con `status=ENTREGADO` + `tiempo_entrega_min`.
- Exponer `POST /orders/{id}/deliver` (o trigger externo) que dispare ese evento.
- Hacer que `kitchen-manager` y `delivery-tracker` **también actualicen DynamoDB** en cada transición, no solo Redis.

---

#### C2. El cliente nunca recibe las notificaciones

**Síntoma:** El email se envía siempre a `SES_SENDER` (la propia cuenta de envío), no al cliente.

`notifier/handler.py:52-58`:
```python
ses.send_email(
    Source=SES_SENDER,
    Destination={"ToAddresses": [SES_SENDER]},  # ← se envía a sí mismo
    ...
)
```

El SNS publish tampoco tiene endpoint del cliente — solo publica al topic, así que solo lo recibe quien esté suscripto al topic (típicamente nadie en runtime real).

**Causa raíz:** el evento `ORDER_CREATED` no incluye email/teléfono del cliente. Solo trae `customerId` (el `sub` del JWT de Cognito).

**Fix sugerido (cualquiera sirve):**
- Que `ingress` extraiga `email` del JWT y lo agregue al evento.
- Que `notifier` llame a `cognito-idp:AdminGetUser` para resolver email a partir del `sub`.
- Tener tabla `breadboss-users` con `customerId → {email, phone}`.

---

#### C3. Los consumers no son idempotentes

**Síntoma:** Kafka + Lambda garantiza **at-least-once delivery**. Si un mensaje se reentrega (cold start con timeout parcial, reintentos por error transient), los efectos se duplican:

| Consumer | Efecto de duplicación |
|---|---|
| `stock-updater` | Decrementa stock 2 veces ❌ |
| `kitchen-manager` | Publica `ORDER_READY` 2 veces → cascada hacia delivery-tracker y notifier ❌ |
| `notifier` | Envía 2 emails al cliente ❌ |
| `order-processor` | Sobreescribe el mismo item (idempotente por accidente) ✅ |
| `delivery-tracker` | Reasigna driver random (cambia driver) ❌ |

**Fix sugerido:** clave de idempotencia por `orderId` + `consumer` en una tabla Dynamo o Redis con TTL corto. Antes de procesar, `PutItem` con `ConditionExpression "attribute_not_exists"` — si falla, skip.

---

### 🟠 Altos — seguridad y calidad

#### A1. IAM roles con `*FullAccess` para todos los lambdas

`iam/main.tf:16-25` adjunta `AmazonDynamoDBFullAccess`, `AmazonMSKFullAccess`, `AmazonSNSFullAccess`, `AmazonSESFullAccess`, `AmazonElastiCacheFullAccess` a **un único rol compartido por todas las funciones**.

**Impacto:** violación severa de least-privilege. Si un lambda se compromete (ej. inyección via item malformado), el atacante tiene acceso completo a todas las tablas de la cuenta — no solo de BreadBoss.

**Fix:** un rol por función con políticas inline scoped al recurso específico. Ej. `order-processor` solo `dynamodb:PutItem` sobre `breadboss-orders`.

---

#### A2. Sin DLQ ni control de reintentos

Los `aws_lambda_event_source_mapping` (`lambda/main.tf:121-139`) no tienen:
- `destination_config` (DLQ on failure)
- `maximum_retry_attempts`
- `maximum_record_age_in_seconds`

**Impacto:** si un mensaje falla, Lambda reintenta hasta que expire por retención del topic (7 días default). Después se pierde silenciosamente — sin alerta, sin trazabilidad.

**Fix:** agregar SQS como DLQ + `function_response_types = ["ReportBatchItemFailures"]` para que solo se reintente el item fallido, no el batch entero.

---

#### A3. Validación insuficiente en `ingress`

`ingress/handler.py:24-29`:
```python
for field in ['items', 'deliveryAddress']:
    if field not in body:
        return 400
```

No valida:
- Que `items` sea lista no vacía.
- Que cada item tenga `itemId` / `qty` / `price` válidos y tipos correctos.
- Que `itemId` exista en el menú real.
- Que `qty > 0`.
- Que `deliveryAddress` no sea string vacío.
- Que el `price` corresponda al del menú (ver M11).

**Fix:** schema de validación (jsonschema, pydantic) + lookup contra `breadboss-menu` antes de publicar el evento.

---

#### A4. Conexiones recreadas en cada invocación

- `ingress.handler:48` — crea `KafkaProducer` por cada invocación (handshake SASL + IAM token signing son caros).
- `kitchen-manager.handler:26-27` — crea Redis client + Kafka producer cada vez.
- `delivery-tracker.handler:17` — crea Redis client cada vez.

**Impacto:** latencia agregada de 200ms–1s por invocación warm (más en cold start). Multiplicado por volumen pico (5× según README) = problema de throughput.

**Fix:** mover inicialización a scope de módulo (top-level). Lambda mantiene la conexión warm en invocaciones consecutivas.

```python
# top-level
_producer = None

def get_producer():
    global _producer
    if _producer is None:
        _producer = KafkaProducer(...)
    return _producer
```

---

#### A5. Secretos en plaintext en estado Terraform

- `cognito/main.tf:37`: `password = var.test_user_password` → queda en `terraform.tfstate` como plaintext.
- `auditor/main.tf:23`: `OPENAI_API_KEY = var.openai_api_key` → en env var de Lambda (visible con `lambda:GetFunction`) y en `terraform.tfstate`.

**Impacto:** quien lea el state (S3, archivo local, backup) tiene credenciales. State no debería contener secretos.

**Fix:**
- OpenAI key → AWS Secrets Manager + `data "aws_secretsmanager_secret_version"` en runtime, o leer desde dentro del lambda.
- Cognito test user → crear post-deploy con `aws cognito-idp admin-create-user` (script o null_resource), no hardcoded.

---

### 🟡 Medios — mejorables

#### M1. DynamoDB nunca refleja transiciones (cubierto por C1)

#### M2. Redis TTL de 2h pierde estado del pedido (cubierto por C1)

#### M3. Timestamps inconsistentes

Mezcla de unidades en el mismo dominio:

| Lugar | Formato | Tipo |
|---|---|---|
| `ingress` evento | `2026-05-23T12:34:56.789Z` | ISO 8601 string |
| `order-processor` → Dynamo | `int(time.time())` | Unix epoch segundos |
| `kitchen-manager` → Redis | `datetime.utcnow().isoformat()` | ISO 8601 string |
| `delivery-tracker` → Redis | idem | ISO 8601 string |
| `seed.py` → Dynamo | `int(dt.timestamp() * 1000)` | Unix epoch **milisegundos** |

El schema de Dynamo (`hash_key=orderId, range_key=timestamp(N)`) admite ambos números, pero comparaciones temporales entre seed (ms) y datos reales (s) van a estar mal escaladas en cualquier query por rango.

**Fix:** estandarizar a Unix epoch ms en todos lados (compatible con seed) o ISO 8601 (si Dynamo schema lo permite).

---

#### M4. Sin CORS en API Gateway

`api_gateway/main.tf:1-5` no define `cors_configuration` en `aws_apigatewayv2_api`. El browser va a bloquear los POST desde el front cuando esté en otro origen.

**Fix:** agregar `cors_configuration { allow_origins = ["*"], allow_methods = ["POST"], allow_headers = ["authorization", "content-type"] }` (acotar `allow_origins` en prod).

---

#### M5. Faltan endpoints `GET /orders/{id}` y `GET /menu`

El front no puede:
- Mostrar el catálogo (debería traerlo del menú, no hardcodearlo).
- Hacer tracking del estado del pedido post-creación.

**Fix:** agregar 2 lambdas (`menu-reader`, `order-reader`) + routes en API Gateway. El `order-reader` debería leer de Dynamo (estado terminal) y/o Redis (estado en vuelo).

---

#### M6. Cero tests

No hay unit tests de handlers ni tests de integración (LocalStack, moto). Toda validación depende de deploy real → ciclo de feedback caro.

**Fix:** unit tests con `pytest` + `moto` para mocks de boto3 y Kafka. CI básico en GitHub Actions.

---

#### M7. `print()` en vez de logger estructurado

Todos los handlers usan `print()`. Pierde nivel (INFO/WARN/ERROR), structured logging y correlation IDs. CloudWatch lo ingesta como texto plano.

**Fix:** `import logging; logger = logging.getLogger(); logger.setLevel(logging.INFO)` + JSON serialization. Permite filtrar en CloudWatch Insights por `orderId`.

---

#### M8. X-Ray activo pero sin instrumentación

`lambda/main.tf:97`: `tracing_config { mode = "Active" }` está prendido, pero ningún handler usa `aws_xray_sdk` para crear segments. Solo vas a ver el span outer de Lambda, no las llamadas a Dynamo/Kafka/Redis adentro.

**Fix:** `from aws_xray_sdk.core import patch_all; patch_all()` al inicio de cada handler.

---

#### M9. CloudWatch alarmas con threshold demasiado bajo

`cloudwatch/main.tf:78`: alarm a `>1 error en 5 min`. Va a dispararse con cualquier cold start fallido o reintento normal de Kafka. Bajo signal-to-noise.

**Fix:** subir threshold a >5–10 errores o usar percentil. Separar alarmas por función crítica vs no crítica.

---

#### M10. Total del pedido se calcula con precio del cliente

`ingress/handler.py:43`:
```python
'total': sum(i['price'] * i['qty'] for i in body['items'])
```

Recalcula sobre el `price` que mandó el cliente — no contra el precio real del menú. **El cliente puede mandar `price: 0`** y se acepta.

**Fix:** lookup en `breadboss-menu` y calcular `total` con el `price` real del backend. Rechazar el pedido si los `itemId` no existen.

---

#### M11. Sin rate limiting

API Gateway no tiene throttling configurado. Cualquiera con un JWT puede hacer 10k pedidos/segundo (hasta el límite de cuenta de AWS).

**Fix:** `default_route_settings { throttling_burst_limit = 100, throttling_rate_limit = 50 }` en el stage.

---

#### M12. `kitchen-manager` publica `ORDER_READY` instantáneamente

No modela tiempo de cocción. Hoy el pedido pasa de `RECIBIDO` a `EN_CAMINO` en <5 segundos. En realidad debería haber:
- Un trigger externo (UI de cocina marca "listo").
- O un Step Function con delay simulado.
- O un cron que procesa `kitchen:queue` con throughput limitado.

**Fix:** depende de C1 y de si querés simular o conectar UI real.

---

#### M13. Auditor sin tracing y sin alarmas dedicadas

`auditor/main.tf` no setea `tracing_config { mode = "Active" }` ni está incluido en las alarmas/dashboard de CloudWatch. Si falla el batch nocturno, no hay alerta.

---

### 🟢 Bajos — cosmética / optimización

#### B1. Naming inconsistente de tablas

`breadboss-orders`, `breadboss-menu` con guion vs `breadboss_resumenes`, `breadboss_metricas` con underscore. Las últimas dos están hardcodeadas en `dynamodb/main.tf:53,65` sin usar el `prefix`.

**Fix:** uniformizar (preferible guion) y usar `${var.prefix}`.

---

#### B2. Inconsistencia `AWS_REGION` vs `AWS_REGION_NAME`

`ingress` usa la env var reservada del runtime, `kitchen-manager` usa la custom seteada por Terraform. Ambos funcionan pero confunde.

**Fix:** estandarizar a `AWS_REGION_NAME` en todos (Lambda no deja sobrescribir `AWS_REGION` con Terraform).

---

#### B3. Lambdas en VPC innecesariamente

`order-processor`, `stock-updater`, `notifier` solo hablan con servicios públicos de AWS (Dynamo, SNS, SES) — no necesitan estar en VPC. Estarlo agrega 1–5s de cold start por la ENI.

**Fix:** mover esas 3 fuera del VPC config. Ahorrás cold starts y costo de NAT gateway.

---

#### B4. `package.sh` no limpia builds anteriores

Acumula zips viejos entre builds.

**Fix:** agregar `rm -rf build/` al inicio.

---

#### B5. Sin tags de versión/commit en lambdas

Difícil trackear qué deploy corre en producción.

**Fix:** `tags = { Version = var.git_sha }` pasado desde CI.

---

#### B6. NAT Gateway único (single AZ)

`vpc/main.tf:42`: un solo NAT gateway en la AZ pública 0. Si esa AZ cae, las lambdas en la AZ privada 2 pierden internet → fallan llamadas a SNS/SES/DynamoDB (sin VPC endpoints).

**Fix:** NAT por AZ o agregar VPC endpoints para Dynamo/Kafka/SNS/SES.

---

## Plan de mejora priorizado

Ordenado por **valor / esfuerzo**. Si solo hacés los primeros 5, el sistema queda funcional y seguro para demo/producción mínima.

| # | Acción | Severidad | Esfuerzo | Impacto |
|---|---|---|---|---|
| 1 | **Cerrar el ciclo de vida** (C1): agregar `order-finalizer` + actualizar Dynamo en cada transición + endpoint `POST /orders/{id}/deliver`. | 🔴 | 4–6 h | Alto |
| 2 | **Notificaciones al cliente** (C2): incluir email del JWT en el evento + SES enviar al cliente. | 🔴 | 1–2 h | Alto |
| 3 | **Idempotencia** (C3): tabla `breadboss-processed` con `(orderId, consumer)` y `ConditionExpression`. | 🔴 | 3–4 h | Alto |
| 4 | **Validación + total backend** (A3 + M10): jsonschema + lookup menú. Cierra agujero económico. | 🟠 | 2 h | Alto |
| 5 | **DLQ + retry limit** (A2): SQS DLQ + `ReportBatchItemFailures`. | 🟠 | 2 h | Alto |
| 6 | **GET /orders/{id} + GET /menu** (M5): habilita el front realista. | 🟡 | 3 h | Alto |
| 7 | **IAM least-privilege** (A1): rol por función. | 🟠 | 4 h | Medio |
| 8 | **CORS + rate limiting** (M4 + M11): producción-ready API. | 🟡 | 1 h | Medio |
| 9 | **Reutilizar conexiones** (A4): mover init a scope global. | 🟠 | 1 h | Medio (latencia) |
| 10 | **Secrets Manager** (A5): OpenAI key + cognito password. | 🟠 | 2 h | Medio |
| 11 | **Logger estructurado + X-Ray** (M7 + M8): observabilidad real. | 🟡 | 2 h | Medio |
| 12 | **Tests unitarios con moto** (M6): habilita iteración rápida. | 🟡 | 6–8 h | Alto (largo plazo) |
| 13 | **Estandarizar timestamps** (M3): consistencia. | 🟡 | 1 h | Bajo |
| 14 | **Lambdas fuera de VPC** (B3): ahorro cold start + costo. | 🟢 | 1 h | Bajo |
| 15 | Resto de B1–B6 | 🟢 | 1–2 h c/u | Bajo |

**Esfuerzo total estimado para items 1–5 (lo crítico):** ~12–17 h.

---

## Apéndice A — Detalle de la discusión sobre ciclo de vida

(Conservado de la conversación previa porque enmarca por qué C1 es crítico, no solo "feature pendiente".)

### Por qué quedó así

Probablemente porque el diseño asumió eventos externos que nunca se implementaron:

- **Kitchen UI** → un operador marca "listo" → dispara `ORDER_READY` (hoy lo dispara `kitchen-manager` instantáneamente al recibir el pedido).
- **Driver app** → repartidor marca "retirado" y después "entregado" → dispara `ORDER_DELIVERED`.

Sin esos triggers externos, el flujo no tiene cómo cerrarse. El README lista 8 pasos terminando en *"se registra la entrega"* pero esa última parte no existe en código.

### Opciones para cerrarlo

| Opción | Esfuerzo | Para qué sirve |
|---|---|---|
| **A.** Lambda `order-finalizer` + endpoint `POST /orders/{id}/deliver` que dispara `orders.delivered`. | Bajo | Cierra el ciclo realista, alimenta al auditor con datos buenos. |
| **B.** Que `kitchen-manager` y `delivery-tracker` también escriban en DynamoDB + cron que cierra pedidos viejos. | Medio | Trazabilidad completa pero sigue siendo simulado. |
| **C.** Script/cron que tome pedidos `RECIBIDO` viejos y los marque `ENTREGADO` con `tiempo_entrega_min` random. | Mínimo | Solo para que el dashboard muestre datos realistas en una demo. |

---

## Apéndice B — Lo que SÍ está bien hecho

Para no perder de vista las cosas correctas:

- ✅ **Pattern event-driven implementado correctamente**: fan-out con Kafka, consumers independientes, segundo fan-out con `orders.ready`.
- ✅ **MSK Serverless con SASL/IAM**: auth nativa AWS, sin gestionar Kerberos/SCRAM.
- ✅ **API Gateway HTTP API + Cognito JWT authorizer**: standard, sin auth custom.
- ✅ **DynamoDB con GSI por canal/status/fecha**: schema bien pensado para queries del dashboard (aunque el `status-index` esté infrautilizado por C1).
- ✅ **Lambda con archive_file vs script externo**: separación correcta entre simples y empaquetadas con deps.
- ✅ **CloudWatch dashboard + alarmas pre-creadas**: observabilidad básica out-of-the-box.
- ✅ **Auditor con cron diario via EventBridge**: pattern correcto para batch jobs.
- ✅ **VPC con subnets públicas/privadas + NAT**: networking ortodoxo.
- ✅ **Gitignore correcto para tfvars y tfstate**: secretos no se commiten.
