# Test end-to-end — BreadBoss

Guía para probar el flujo completo del sistema event-driven, desde la creación de un pedido hasta cerrarlo como entregado.

---

## Flujo del sistema (actualizado)

```
POST /orders
   │
   ▼
API Gateway (JWT Cognito) — CORS + throttling 50 req/s
   │
   ▼
Lambda ingress  ──► valida schema + precio desde DynamoDB breadboss-menu
                ──► publica ORDER_CREATED en Kafka topic "pedidos"
                ──► incluye customerEmail (del JWT) en el evento
                                │
                                ▼ fan-out paralelo
        ┌─────────────────┬─────┴─────────┬────────────────┐
        ▼                 ▼               ▼                ▼
 order-processor   kitchen-manager   stock-updater     notifier
 (DynamoDB         (Redis            (DynamoDB         (SES →
  orders:           EN_PREPARACION    menu:             customerEmail
  RECIBIDO +        + DynamoDB        decrementa        "Pedido OK")
  customerEmail)    EN_PREPARACION    stock)
                    — espera
                    confirmación)
                          │
                          ▼
POST /orders/{id}/ready  ← acción manual del admin de cocina
                          │
                          ▼
              order-ready Lambda
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
 valida          publica         actualiza
 EN_PREPARACION  ORDER_READY     DynamoDB
 en DynamoDB     en Kafka        → EN_CAMINO
                 "orders.ready"
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       delivery-tracker         notifier
       (Redis EN_CAMINO         (SES →
        + DynamoDB EN_CAMINO     customerEmail
        + asigna driver)         "Pedido en camino")

POST /orders/{id}/deliver
   │
   ▼
order-finalizer  ──► DynamoDB status = ENTREGADO + tiempo_entrega_min
```

Todos los consumers usan idempotencia via tabla `breadboss-processed` (TTL 24h).

---

## ⚠️ Cosas a saber antes de testear

1. **Cerrar el pedido requiere llamar `POST /orders/{id}/deliver`** — ya no hace falta tocar DynamoDB a mano. Ver Paso 5.
2. **Los precios se validan contra el menú** — los `itemId` del body deben existir en `breadboss-menu`. Si la tabla está vacía, corrér el seed primero (Paso 1).
3. **El email del JWT se propaga** — el notifier envía SES al email del usuario Cognito, no a un email fijo.
4. **El paso `EN_PREPARACION → EN_CAMINO` ahora es manual.** Hay que llamar `POST /orders/{id}/ready` (simulando el admin de cocina) antes de que el pedido avance — antes este paso era automático (kitchen-manager publicaba ORDER_READY solo).

---

## Checklist de pruebas

- [x] **Paso 0** — Extraer valores de Terraform
- [x] **Paso 1** — Seed del menú ejecutado
- [x] **Paso 2** — JWT obtenido correctamente
- [x] **Paso 3** — `GET /menu` responde con items
- [x] **Paso 4** — `POST /orders` responde `201` con `orderId`
- [x] **Paso 5** — `GET /orders/{id}` retorna el pedido con `status: RECIBIDO`
- [x] **Paso 6a** — Log ingress muestra `status=201`
- [x] **Paso 6b** — Log order-processor muestra `action=saved`
- [x] **Paso 6c** — Log kitchen-manager muestra `action=en_preparacion` + `action=order_ready_published`
- [x] **Paso 6d** — Log stock-updater muestra `action=stock_updated`
- [x] **Paso 6e** — Log notifier (1ª vez) muestra `event_type=ORDER_CREATED action=email_sent`
- [x] **Paso 6f** — Log delivery-tracker muestra `action=en_camino`
- [x] **Paso 6g** — Log notifier (2ª vez) muestra `event_type=ORDER_READY action=email_sent`
- [x] **Paso 6h** — DynamoDB `breadboss-orders` tiene el item con `customerEmail`
- [x] **Paso 6i** — DynamoDB `breadboss-menu` bajó el stock de los items pedidos
- [x] **Paso 6j** — DynamoDB `breadboss-processed` tiene entradas por cada consumer
- [x] **Paso 6k** — `GET /orders?status=EN_PREPARACION` devuelve el pedido recién creado
- [x] **Paso 6l** — `POST /orders/{id}/ready` responde `200` con `status: LISTO`
- [x] **Paso 6m** — `GET /orders/{id}` retorna `status: EN_CAMINO` tras unos segundos
- [x] **Paso 6n** — Segunda llamada a `/ready` devuelve `{"message": "Ya estaba marcado"}` (idempotencia OK)
- [x] **Paso 7** — `POST /orders/{id}/deliver` responde con `status: ENTREGADO` y `tiempo_entrega_min`
- [x] **Paso 8** — Segunda llamada a `/deliver` devuelve el mismo resultado (idempotencia OK)

---

## Paso 0 — Extraer valores de Terraform (terminal)

Estos valores los necesitás para configurar las variables de entorno en Postman.

```bash
cd /Users/agustin/Documents/Projects/guerrin/BreadBoss
terraform output -raw api_invoke_url
terraform output -raw cognito_client_id
terraform output -raw cognito_user_pool_id
```

Copiar los valores y cargarlos en Postman como variables de entorno:

| Variable       | Valor                            |
| -------------- | -------------------------------- |
| `API_URL`      | output de `api_invoke_url`       |
| `CLIENT_ID`    | output de `cognito_client_id`    |
| `USER_POOL_ID` | output de `cognito_user_pool_id` |
| `AWS_REGION`   | `us-east-1`                      |
| `EMAIL`        | `lanciramiro9@gmail.com`         |
| `PASS`         | `Test1234!`                      |
| `ID_TOKEN`     | _(se completa en Paso 2)_        |
| `ORDER_ID`     | _(se completa en Paso 4)_        |

---

## Paso 1 — (opcional) Seed del menú (terminal)

Carga 14 items en `breadboss-menu` y 30 pedidos históricos en `breadboss-orders`. **Necesario** para que ingress valide precios y stock-updater tenga items reales.

```bash
python3 /Users/agustin/Documents/Projects/guerrin/seed.py
```

---

## Paso 2 — Obtener JWT de Cognito

Pegá este curl en Postman (Import → Raw Text). La respuesta devuelve `AuthenticationResult.IdToken` — copiarlo a la variable `ID_TOKEN`.

```curl
curl --location 'https://cognito-idp.{{AWS_REGION}}.amazonaws.com/' \
--header 'Content-Type: application/x-amz-json-1.1' \
--header 'X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth' \
--data '{
    "AuthFlow": "USER_PASSWORD_AUTH",
    "ClientId": "{{CLIENT_ID}}",
    "AuthParameters": {
        "USERNAME": "{{EMAIL}}",
        "PASSWORD": "{{PASS}}"
    }
}'
```

**Respuesta esperada:** JSON con `AuthenticationResult.IdToken`. Copiar ese valor a la variable `ID_TOKEN` en Postman.

Si devuelve `NEW_PASSWORD_REQUIRED`, ver troubleshooting al final.

---

## Paso 3 — Consultar el menú disponible

```curl
curl --location '{{API_URL}}/menu' \
--header 'Authorization: Bearer {{ID_TOKEN}}'
```

**Respuesta esperada:** array de items con `itemId`, `name`, `price`, `stock`. Usá los `itemId` reales del menú en el Paso 4.

---

## Paso 4 — Crear pedido

Los precios en el body son ignorados — ingress los sobreescribe desde DynamoDB. Usá `itemId` que existan en el menú (del Paso 3).

```curl
curl --location '{{API_URL}}/orders' \
--header 'Authorization: Bearer {{ID_TOKEN}}' \
--header 'Content-Type: application/json' \
--data '{
    "channel": "app_mobile",
    "deliveryAddress": "Av Corrientes 1234, CABA",
    "items": [
        {"itemId": "b01", "name": "Smash Burger Clasica", "qty": 1, "price": 0},
        {"itemId": "d01", "name": "Coca Cola 500ml", "qty": 1, "price": 0}
    ]
}'
```

**Respuesta esperada:** `201` + body:
```json
{"orderId": "<uuid>", "status": "RECIBIDO", "message": "Pedido recibido!"}
```

Copiar el `orderId` devuelto a la variable `ORDER_ID` en Postman.

---

## Paso 5 — Consultar estado del pedido

Esperar 5–10 segundos para que los consumers procesen el evento.

```curl
curl --location '{{API_URL}}/orders/{{ORDER_ID}}' \
--header 'Authorization: Bearer {{ID_TOKEN}}'
```

**Respuesta esperada:**
```json
{
  "orderId": "<uuid>",
  "status": "RECIBIDO",
  "customerEmail": "lanciramiro9@gmail.com",
  "channel": "app_mobile",
  "deliveryAddress": "Av Corrientes 1234, CABA",
  "items": [...],
  "timestamp": 1234567890123
}
```

---

## Paso 6 — Verificar fan-out en la consola AWS

A los 5–10 segundos del POST, Kafka dispara los 4 consumers. Abrí cada link y refrescá los **log streams** más recientes:

| Servicio | URL consola |
|---|---|
| Log ingress | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-ingress |
| Log order-processor | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-order-processor |
| Log kitchen-manager | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-kitchen-manager |
| Log stock-updater | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-stock-updater |
| Log notifier | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-notifier |
| Log delivery-tracker | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fbreadboss-delivery-tracker |
| DynamoDB `breadboss-orders` | https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=breadboss-orders |
| DynamoDB `breadboss-menu` | https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=breadboss-menu |
| DynamoDB `breadboss-processed` | https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=breadboss-processed |

### Qué buscar en los logs

| Lambda | Mensaje esperado |
|---|---|
| ingress | `order_id=<uuid> status=201` |
| order-processor | `order_id=<uuid> action=saved status=RECIBIDO` |
| kitchen-manager | `order_id=<uuid> action=en_preparacion` + `action=order_ready_published` |
| stock-updater | `order_id=<uuid> action=stock_updated items_updated=2` |
| notifier (1ª vez) | `order_id=<uuid> event_type=ORDER_CREATED action=email_sent` |
| delivery-tracker | `order_id=<uuid> action=en_camino driver=driver_0X` |
| notifier (2ª vez) | `order_id=<uuid> event_type=ORDER_READY action=email_sent` |

**En DynamoDB `breadboss-orders`:** el item tiene `status: RECIBIDO` y `customerEmail` guardado.

**En DynamoDB `breadboss-menu`:** el stock de los items pedidos bajó en la cantidad pedida.

**En DynamoDB `breadboss-processed`:** aparecen entradas `(orderId, consumer)` por cada consumer que procesó el pedido.

---

## Paso 7 — Cerrar pedido como entregado

```curl
curl --location --request POST '{{API_URL}}/orders/{{ORDER_ID}}/deliver' \
--header 'Authorization: Bearer {{ID_TOKEN}}'
```

**Respuesta esperada:**
```json
{
  "orderId": "<uuid>",
  "status": "ENTREGADO",
  "tiempo_entrega_min": 12
}
```

Verificar con el curl del Paso 5 que el status cambió a `ENTREGADO`.

---

## Paso 8 — Verificar idempotencia (opcional)

Repetir el curl del Paso 7 con el mismo `ORDER_ID`. Debe devolver el mismo resultado sin errores ni duplicados.

También podés repetir el Paso 4 con el mismo body — cada llamada genera un `orderId` nuevo (UUID), por lo que no hay colisión a nivel de pedidos.

---

## Troubleshooting

| Síntoma | Causa probable / solución |
|---|---|
| `POST /orders` devuelve 400 con `item not found` | El `itemId` no existe en `breadboss-menu`. Corrér seed (Paso 1) y verificar con `GET /menu`. |
| `POST /orders` devuelve 401/403 | Token venció (~1 h). Reintentar Paso 2. |
| `POST /orders` devuelve 502/timeout | Cold start de ingress con VPC + MSK (~10–20 s la primera vez). Reintentar. |
| `GET /orders/{id}` devuelve 404 | El order-processor aún no procesó el evento. Esperar 5–10 s y reintentar. |
| Pedido no aparece en DynamoDB | Revisar logs `order-processor`. Si no se invocó, verificar Lambda → función → Triggers (event source mapping Kafka). |
| stock-updater no actualiza stock | Revisar logs `stock-updater`. Si hay `already_processed`, el consumer ya corrió para ese pedido (idempotencia activa). |
| `InitiateAuth` falla con `NotAuthorizedException` | Password temporal. Forzar permanente: `aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --username "$EMAIL" --password "$PASS" --permanent` |
| `POST /orders/{id}/deliver` devuelve 404 | El `ORDER_ID` no existe. Verificar que el Paso 4 fue exitoso. |

---

## Endpoints completos (referencia rápida para Postman)

| Método | Endpoint | Auth | Body |
|---|---|---|---|
| `GET` | `{{API_URL}}/menu` | Bearer JWT | — |
| `POST` | `{{API_URL}}/orders` | Bearer JWT | JSON con `channel`, `deliveryAddress`, `items[]` |
| `GET` | `{{API_URL}}/orders/{{ORDER_ID}}` | Bearer JWT | — |
| `POST` | `{{API_URL}}/orders/{{ORDER_ID}}/deliver` | Bearer JWT | — |

### Variables de entorno para Postman

```
API_URL       = <terraform output -raw api_invoke_url>
ID_TOKEN      = <obtenido en Paso 2>
ORDER_ID      = <devuelto por POST /orders>
```

---

## Recursos AWS (referencia)

- **API Gateway**: `$(terraform output -raw api_invoke_url)`
- **Cognito user pool**: `$(terraform output -raw cognito_user_pool_id)`
- **Cognito app client**: `$(terraform output -raw cognito_client_id)`
- **MSK topics**: `pedidos`, `orders.ready`
- **DynamoDB tables**: `breadboss-orders`, `breadboss-menu`, `breadboss-processed`, `breadboss_resumenes`, `breadboss_metricas`
- **Redis (ElastiCache Serverless)**: `$(terraform output -raw redis_endpoint)` — solo accesible desde VPC
- **CloudWatch dashboard**: `$(terraform output -raw cloudwatch_dashboard_url)`
