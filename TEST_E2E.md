# Test end-to-end — BreadBoss

Guía para probar el flujo completo del sistema event-driven, desde la creación de un pedido hasta verificar todos los consumers.

---

## Flujo del sistema

```
POST /orders
   │
   ▼
API Gateway (JWT Cognito)
   │
   ▼
Lambda ingress  ──► publica ORDER_CREATED en Kafka topic "pedidos"
                                │
                                ▼ fan-out paralelo
        ┌─────────────────┬─────┴─────────┬────────────────┐
        ▼                 ▼               ▼                ▼
 order-processor   kitchen-manager   stock-updater     notifier
 (DynamoDB         (Redis            (DynamoDB         (SNS + SES)
  orders:           EN_PREPARACION    menu:             "Pedido OK"
  RECIBIDO)         + publica         decrementa
                    ORDER_READY)      stock)
                          │
                          ▼
              Kafka topic "orders.ready"
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       delivery-tracker         notifier
       (Redis EN_CAMINO         (SNS + SES
        + asigna driver)         "Pedido en camino")
```

---

## ⚠️ Cosas a saber antes de testear

1. **El flujo nunca llega a `ENTREGADO`/`FINALIZADA` solo.** El último estado que setea algún handler es `EN_CAMINO` en Redis (delivery-tracker). En DynamoDB el pedido queda en `RECIBIDO` para siempre — no existe lambda que lo cierre. Hay que forzarlo a mano (ver Paso 5).
2. **stock-updater bug**: arreglado (apuntaba a `ghostbite-menu` en vez de `breadboss-menu`). Requiere `make plan && make apply` para desplegar.

---

## Paso 0 — Extraer valores de Terraform

```bash
cd /Users/agustin/Documents/Projects/guerrin/BreadBoss

export AWS_REGION=us-east-1
export API_URL=$(terraform output -raw api_invoke_url)
export USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
export CLIENT_ID=$(terraform output -raw cognito_client_id)
export EMAIL="lanciramiro9@gmail.com"
export PASS="Test1234!"

echo "API_URL=$API_URL"
echo "CLIENT_ID=$CLIENT_ID"
echo "USER_POOL_ID=$USER_POOL_ID"
```

---

## Paso 1 — (opcional) Seed del menú

Carga 14 items en `breadboss-menu` y 30 pedidos históricos en `breadboss-orders`. Necesario si querés que `stock-updater` tenga items reales que decrementar.

```bash
python3 ../seed.py
```

---

## Paso 2 — Obtener JWT de Cognito

### Opción A — AWS CLI (más simple)

```bash
export ID_TOKEN=$(aws cognito-idp initiate-auth \
  --region "$AWS_REGION" \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters "USERNAME=$EMAIL,PASSWORD=$PASS" \
  --query 'AuthenticationResult.IdToken' \
  --output text)

echo "$ID_TOKEN" | head -c 60; echo "..."
```

### Opción B — curl puro contra Cognito

```bash
export ID_TOKEN=$(curl -s -X POST "https://cognito-idp.$AWS_REGION.amazonaws.com/" \
  -H "Content-Type: application/x-amz-json-1.1" \
  -H "X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth" \
  -d "{
    \"AuthFlow\": \"USER_PASSWORD_AUTH\",
    \"ClientId\": \"$CLIENT_ID\",
    \"AuthParameters\": {
      \"USERNAME\": \"$EMAIL\",
      \"PASSWORD\": \"$PASS\"
    }
  }" | jq -r '.AuthenticationResult.IdToken')

echo "$ID_TOKEN" | head -c 60; echo "..."
```

Si devuelve `null` o `NEW_PASSWORD_REQUIRED`, ver troubleshooting al final.

---

## Paso 3 — Crear pedido (POST /orders)

```bash
curl -i -X POST "$API_URL/orders" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "app_mobile",
    "deliveryAddress": "Av Corrientes 1234, CABA",
    "items": [
      {"itemId": "b01", "name": "Smash Burger Clasica", "qty": 1, "price": 4500},
      {"itemId": "d01", "name": "Coca Cola 500ml",      "qty": 1, "price": 1500}
    ]
  }'
```

**Respuesta esperada:** `HTTP/2 201` + body `{"orderId":"<uuid>","status":"RECIBIDO","message":"Pedido recibido!"}`.

Guardalo:

```bash
export ORDER_ID="<el uuid devuelto>"
```

---

## Paso 4 — Verificar fan-out en la consola AWS

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

### Qué buscar en los logs

| Lambda | Mensaje esperado |
|---|---|
| ingress | invocación + 201 |
| order-processor | `Order <uuid> saved to DynamoDB` |
| kitchen-manager | `Order <uuid> → EN_PREPARACION, ORDER_READY publicado` |
| stock-updater | `Order <uuid> → stock actualizado para N items` |
| notifier (1ª invocación) | `Order <uuid> → notificación enviada (ORDER_CREATED)` |
| delivery-tracker | `Order <uuid> → EN_CAMINO, asignado a driver_0X` |
| notifier (2ª invocación) | `Order <uuid> → notificación enviada (ORDER_READY)` |

En DynamoDB `breadboss-orders` el item nuevo aparece con `status: RECIBIDO`.

En `breadboss-menu` el stock de los items pedidos debe haber bajado en la cantidad pedida.

---

## Paso 5 — Forzar estado `ENTREGADO` manualmente

Ningún lambda cierra el pedido, así que lo actualizamos a mano:

```bash
TS=$(aws dynamodb query \
  --table-name breadboss-orders \
  --key-condition-expression "orderId = :oid" \
  --expression-attribute-values "{\":oid\":{\"S\":\"$ORDER_ID\"}}" \
  --projection-expression "#ts" \
  --expression-attribute-names '{"#ts":"timestamp"}' \
  --query 'Items[0].#ts.N' --output text)

aws dynamodb update-item \
  --table-name breadboss-orders \
  --key "{\"orderId\":{\"S\":\"$ORDER_ID\"},\"timestamp\":{\"N\":\"$TS\"}}" \
  --update-expression "SET #s = :v" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":v":{"S":"ENTREGADO"}}'
```

Refrescá el item en la consola DynamoDB — debe figurar `status: ENTREGADO`.

---

## Troubleshooting

| Síntoma | Causa probable / solución |
|---|---|
| `curl` POST devuelve 401/403 | Token venció (~1 h) o falta `Authorization: Bearer ...`. Reintentar Paso 2. |
| `curl` POST devuelve 502/timeout | Cold start de ingress con VPC + IAM auth a MSK (10–20 s la primera vez). Reintentar. |
| Pedido no aparece en DynamoDB | Revisar logs `order-processor`. Si no se invocó, el event source mapping Kafka no consume — verificar en consola Lambda → función → Triggers. |
| `InitiateAuth` falla con `NotAuthorizedException` | La pass del user quedó "temporal". Forzar como permanente: `aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --username "$EMAIL" --password "$PASS" --permanent` |
| `stock-updater` sigue con `ResourceNotFoundException` | El fix no se desplegó. Correr `make plan && make apply` en `BreadBoss/`. |

---

## Endpoints y recursos (referencia rápida)

- **API Gateway**: `$(terraform output -raw api_invoke_url)/orders` (POST, JWT)
- **Cognito user pool**: `$(terraform output -raw cognito_user_pool_id)`
- **Cognito app client**: `$(terraform output -raw cognito_client_id)`
- **MSK topics**: `pedidos`, `orders.ready`
- **DynamoDB tables**: `breadboss-orders`, `breadboss-menu`, `breadboss_resumenes`, `breadboss_metricas`
- **Redis (ElastiCache Serverless)**: `$(terraform output -raw redis_endpoint)` — solo accesible desde VPC
- **CloudWatch dashboard**: `$(terraform output -raw cloudwatch_dashboard_url)`
