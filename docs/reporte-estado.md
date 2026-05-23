# BreadBoss / GhostBite — Reporte de Estado

## Qué es el sistema

**GhostBite** es una dark kitchen (cocina sin local físico) que recibe pedidos por múltiples canales (app, WhatsApp, Rappi, etc.) y los procesa de forma automática usando una arquitectura **event-driven** sobre AWS.

**BreadBoss** es el nombre del proyecto de infraestructura (IaC con Terraform) que despliega todo el sistema.

---

## Infraestructura desplegada (módulos Terraform)

| Módulo | Servicio AWS | Qué hace |
|---|---|---|
| `vpc` | VPC + Subnets + NAT GW | Red privada para MSK y ElastiCache |
| `iam` | IAM Role | Permisos para todas las Lambdas |
| `cognito` | Cognito User Pool | Autenticación de usuarios con JWT |
| `msk` | Amazon MSK Serverless | Bus de eventos Kafka |
| `dynamodb` | DynamoDB | Tablas de pedidos, menú, resúmenes y métricas |
| `elasticache` | ElastiCache Redis | Estado en tiempo real de cada pedido |
| `s3` | S3 | Assets estáticos y backups |
| `sns_ses` | SNS + SES | Notificaciones push y emails |
| `api_gateway` | API Gateway HTTP | Punto de entrada REST con Cognito authorizer |
| `lambda` | Lambda (x6) | Funciones de procesamiento |
| `cloudwatch` | CloudWatch | Dashboard, alarmas y logs |
| `auditor` | Lambda + EventBridge | Agente de IA que analiza métricas diarias |

---

## Tablas DynamoDB

| Tabla | Clave | Uso |
|---|---|---|
| `breadboss-orders` | `orderId` + `timestamp` | Todos los pedidos |
| `breadboss-menu` | `itemId` | Stock del menú |
| `breadboss_resumenes` | `fecha` | Resúmenes generados por el auditor IA |
| `breadboss_metricas` | `fecha` | Métricas calculadas por el auditor IA |

`breadboss-orders` tiene 3 GSIs: `channel-index`, `status-index`, `fecha-index`.

---

## Lambdas — Funciones y responsabilidades

| Función | Trigger | Qué hace |
|---|---|---|
| `breadboss-ingress` | API Gateway POST /orders | Valida el pedido, genera orderId, publica `ORDER_CREATED` al topic `pedidos` |
| `breadboss-order-processor` | MSK topic `pedidos` | Persiste el pedido completo en DynamoDB |
| `breadboss-kitchen-manager` | MSK topic `pedidos` | Pone el pedido en Redis como `EN_PREPARACION`, lo agrega a la cola de cocina, y publica `ORDER_READY` al topic `orders.ready` |
| `breadboss-stock-updater` | MSK topic `pedidos` | Descuenta stock de cada item en DynamoDB |
| `breadboss-delivery-tracker` | MSK topic `orders.ready` | Asigna repartidor y actualiza Redis a `EN_CAMINO` |
| `breadboss-notifier` | MSK topics `pedidos` y `orders.ready` | Envía notificación por SNS y email por SES según el tipo de evento |
| `breadboss-auditor` | EventBridge (diario 23:59 UTC) | Lee pedidos del día, calcula métricas, llama a OpenAI y guarda resumen en DynamoDB |

---

## Flujo de un pedido — Diseño corregido

El cambio principal respecto al diseño original fue separar el flujo en **dos fans-out** para respetar la dependencia lógica entre estados.

### Diseño original (incorrecto)
Todos los consumers escuchaban el mismo topic `pedidos` y se ejecutaban en paralelo, incluyendo `delivery-tracker` que asignaba repartidor al mismo tiempo que `kitchen-manager` ponía el pedido en preparación. Esto generaba una **race condition** en Redis: el estado final dependía de qué Lambda terminaba último.

### Diseño corregido — Dos fans-out

```
Cliente
  │
  └─▶ POST /orders
        │
        ▼
   [Cognito]  valida JWT
        │
        ▼
   [API Gateway]
        │
        ▼
   [Lambda Ingress]
        │
        └─▶ topic: pedidos  (ORDER_CREATED)
                │
                ├─▶ [order-processor]  → DynamoDB (persiste pedido)
                ├─▶ [stock-updater]    → DynamoDB (descuenta stock)
                ├─▶ [notifier]         → SNS + SES ("pedido recibido")
                └─▶ [kitchen-manager]  → Redis EN_PREPARACION
                                              │
                                              └─▶ topic: orders.ready  (ORDER_READY)
                                                        │
                                                        ├─▶ [delivery-tracker] → Redis EN_CAMINO
                                                        └─▶ [notifier]         → SNS + SES ("en camino")
```

### Estados del pedido en Redis

```
RECIBIDO → EN_PREPARACION → EN_CAMINO → ENTREGADO
```

Cada transición es disparada por el consumer correcto en el momento correcto. El repartidor se asigna **después** de que la cocina confirmó, no simultáneamente.

---

## Observabilidad

- **X-Ray**: habilitado en todas las Lambdas (`mode = "Active"`) — permite tracing distribuido end-to-end
- **CloudWatch Logs**: grupo por Lambda, retención 14 días
- **Dashboard** `breadboss-Operations`: invocaciones, errores y duración de todas las Lambdas + pedidos creados + DynamoDB read capacity
- **Alarmas**:
  - Lambda errors > 1 en 5 minutos → notifica por SNS
  - Lambda duration > 5000ms → notifica por SNS

---

## Estructura del repositorio

```
BreadBoss/
├── Makefile                  ← comandos para build + deploy
├── main.tf                   ← composición de módulos
├── variables.tf
├── outputs.tf
├── versions.tf               ← provider AWS con profile terraform-admin
├── terraform.tfvars          ← valores reales (no subir al repo)
├── terraform.tfvars.example  ← plantilla con placeholders
└── modules/
    ├── vpc/
    ├── iam/
    ├── cognito/
    ├── msk/
    ├── dynamodb/
    ├── elasticache/
    ├── s3/
    ├── sns_ses/
    ├── api_gateway/
    ├── cloudwatch/
    ├── auditor/
    │   ├── main.tf
    │   └── lambda_function.py
    └── lambda/
        ├── main.tf
        ├── package.sh
        ├── ingress/
        ├── order-processor/
        ├── kitchen-manager/
        ├── stock-updater/
        ├── delivery-tracker/
        └── notifier/
```

---

## Comandos de uso

```bash
# Desde BreadBoss/
make plan     # empaqueta lambdas + terraform plan (guarda tfplan)
make apply    # terraform apply usando el tfplan generado
make destroy  # destruye toda la infraestructura
make package  # solo empaqueta las lambdas con dependencias externas
```

---

## Estado actual y qué falta

### Listo
- Toda la infraestructura definida en Terraform con state activo
- Las 6 Lambdas con su código real en `BreadBoss/modules/lambda/`
- Agente auditor IA en `BreadBoss/modules/auditor/`
- Flujo corregido con dos topics Kafka (`pedidos` y `orders.ready`)
- X-Ray, CloudWatch Dashboard y Alarmas
- ADRs (4 archivos en `docs/adr/`)
- Diagramas C4 contexto y contenedores
- `seed.py` con 14 items de menú y 30 pedidos realistas (últimos 3 días)
- Makefile con flujo `make plan` → `make apply`
- **`make apply`** — aplicar los cambios del último plan (nuevos event source mappings, nuevas lambdas)


### Pendiente
- **Diagrama de secuencia** reflejando el flujo corregido con dos fans-out
- **README completo** con tabla de servicios, análisis de costos y lecciones aprendidas
- **Test E2E**: POST → Kafka → DynamoDB → Redis → Notificación
- **Análisis de costos** (`docs/cost-analysis.md`)
