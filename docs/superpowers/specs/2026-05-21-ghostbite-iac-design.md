# Bread Boss IaC — Diseño Técnico
**Fecha:** 2026-05-21  
**Herramienta:** Terraform  
**Contexto:** Trabajo práctico universitario  
**Alcance:** Solo infraestructura (sin código Lambda)

---

## Objetivo

Implementar como código (IaC) la infraestructura AWS de Bread Boss, una dark kitchen event-driven. El resultado es un conjunto de módulos Terraform que reproducen toda la arquitectura desde cero con un solo `terraform apply`.

---

## Arquitectura de referencia

Bread Boss recibe pedidos por API Gateway, los publica a un topic Kafka (MSK) y los procesa en paralelo con 5 funciones Lambda consumer. El estado se persiste en DynamoDB y Redis (ElastiCache). Las notificaciones se envían por SNS/SES. Todo el sistema vive dentro de una VPC privada y se observa con CloudWatch y X-Ray.

---

## Estructura de archivos

```
BreadBoss/
├── main.tf              # Composición: invoca todos los módulos
├── variables.tf         # Variables globales: prefix, region, az_count
├── outputs.tf           # Outputs: API URL, MSK bootstrap, etc.
├── terraform.tfvars     # Valores concretos (sin secrets)
├── versions.tf          # Provider AWS ~> 5.0, Terraform >= 1.6
│
└── modules/
    ├── vpc/
    ├── msk/
    ├── dynamodb/
    ├── elasticache/
    ├── cognito/
    ├── s3/
    ├── iam/
    ├── lambda/
    ├── api_gateway/
    ├── sns_ses/
    └── cloudwatch/
```

Cada módulo tiene: `main.tf`, `variables.tf`, `outputs.tf`.

---

## Módulos

### `vpc`
- Recursos: `aws_vpc`, `aws_subnet` (2 públicas + 2 privadas en 2 AZs), `aws_internet_gateway`, `aws_nat_gateway`, `aws_eip`, `aws_route_table`, `aws_route_table_association`
- CIDR VPC: `10.0.0.0/16`
- Outputs: `vpc_id`, `private_subnet_ids`, `public_subnet_ids`

### `msk`
- Recurso: `aws_msk_serverless_cluster`
- Autenticación: IAM
- Se ubica en las subnets privadas del módulo `vpc`
- Security group propio que permite tráfico desde las Lambdas en el puerto 9098 (MSK IAM/TLS)
- Outputs: `bootstrap_brokers_sasl_iam`

### `dynamodb`
- Tabla `breadboss-orders`: PK=`orderId` (String), SK=`timestamp` (Number), billing=ON_DEMAND
  - GSI 1: `channel-index` — PK=`channel`, SK=`timestamp`
  - GSI 2: `status-index` — PK=`status`, SK=`timestamp`
- Tabla `breadboss-menu`: PK=`itemId` (String), billing=ON_DEMAND
- Outputs: `orders_table_name`, `orders_table_arn`, `menu_table_name`, `menu_table_arn`

### `elasticache`
- Recurso: `aws_elasticache_serverless_cache` (Redis OSS)
- Subnet group en subnets privadas
- Security group propio, acceso desde Lambdas en puerto 6379
- Outputs: `redis_endpoint`

### `cognito`
- Recurso: `aws_cognito_user_pool` + `aws_cognito_user_pool_client`
- Sign-in: email
- Auth flows: `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`
- Usuario de test creado vía `aws_cognito_user` (password en variable, marcada como sensitive)
- Outputs: `user_pool_id`, `user_pool_endpoint`, `client_id`

### `s3`
- Recurso: `aws_s3_bucket` con nombre `breadboss-assets-${var.prefix}`
- Block public access habilitado
- Outputs: `bucket_name`, `bucket_arn`

### `iam`
- Recurso: `aws_iam_role` + `aws_iam_role_policy_attachment`
- Rol: `breadboss-lambda-role`, assume por `lambda.amazonaws.com`
- Políticas adjuntas:
  - `AmazonDynamoDBFullAccess`
  - `AmazonMSKFullAccess`
  - `AmazonElastiCacheFullAccess`
  - `AmazonSNSFullAccess`
  - `AmazonSESFullAccess`
  - `CloudWatchLogsFullAccess`
  - `AWSLambdaVPCAccessExecutionRole`
  - `AWSXRayDaemonWriteAccess`
- Outputs: `lambda_role_arn`

### `lambda`
- 6 funciones: `ingress`, `order-processor`, `kitchen-manager`, `stock-updater`, `delivery-tracker`, `notifier`
- Recurso: `aws_lambda_function` por cada una
- Runtime: Python 3.11
- Handler: `handler.handler`
- Timeout: 30s, Memory: 256 MB
- VPC config: subnets privadas + security group propio
- X-Ray tracing: `PassThrough` (habilitado)
- Código fuente: archivo `.zip` placeholder (`data "archive_file"` desde un `stub/handler.py` vacío)
- Variables de entorno (por función):
  - Todas: `MSK_BOOTSTRAP`, `AWS_REGION_NAME`
  - kitchen-manager, delivery-tracker: `REDIS_HOST`
  - notifier: `SNS_TOPIC_ARN`, `SES_SENDER`
- Event source mappings (`aws_lambda_event_source_mapping`):
  - Las 5 funciones consumer apuntan al topic `pedidos`, batch size 10, starting position `LATEST`
- Log groups: `aws_cloudwatch_log_group` por cada Lambda con retention 14 días
- Outputs: `ingress_function_arn`, `ingress_function_name`, mapa de todas las ARNs

### `api_gateway`
- Recurso: `aws_apigatewayv2_api` (HTTP API)
- JWT Authorizer con Cognito: `aws_apigatewayv2_authorizer`
- Ruta: `POST /orders` con autorización JWT
- Integración Lambda a `breadboss-ingress`: `aws_apigatewayv2_integration`
- Stage `$default` con auto-deploy
- Permission Lambda: `aws_lambda_permission` para que API GW invoque la función
- Outputs: `api_url`, `api_id`

### `sns_ses`
- Recurso: `aws_sns_topic` — nombre `breadboss-notifications`
- Recurso: `aws_ses_email_identity` — email configurable vía variable
- Outputs: `sns_topic_arn`, `ses_sender`

### `cloudwatch`
- `aws_cloudwatch_dashboard` — breadboss-Operations con widgets:
  - Lambda Invocations (todas las funciones)
  - Lambda Errors (todas)
  - Lambda Duration (todas)
  - Custom metric `BreadBoss/OrdersCreated`
  - DynamoDB ConsumedReadCapacityUnits
- `aws_cloudwatch_metric_alarm` × 2:
  - Lambda Errors > 1 en 5 min → SNS notification
  - Lambda Duration > 5000ms → SNS notification
- Outputs: `dashboard_name`

---

## Composición en `main.tf`

```hcl
module "vpc"        { ... }
module "iam"        { ... }
module "s3"         { ... }
module "cognito"    { ... }
module "dynamodb"   { ... }
module "msk"        { source = "...", vpc_id = module.vpc.vpc_id, subnet_ids = module.vpc.private_subnet_ids }
module "elasticache"{ ... vpc_id, subnet_ids }
module "sns_ses"    { ... }
module "lambda"     { ..., msk_bootstrap = module.msk.bootstrap_brokers_sasl_iam, redis_host = module.elasticache.redis_endpoint, ... }
module "api_gateway"{ ..., lambda_arn = module.lambda.ingress_function_arn, cognito_* = module.cognito.* }
module "cloudwatch" { ..., lambda_names = module.lambda.all_function_names }
```

---

## Variables globales (`variables.tf`)

| Variable                     | Default       | Descripción                   |
| ---------------------------- | ------------- | ----------------------------- |
| `aws_region`                 | `us-east-1`   | Región de despliegue          |
| `prefix`                     | `breadboss`   | Prefijo de todos los recursos |
| `az_count`                   | `2`           | Cantidad de AZs               |
| `cognito_test_user_email`    | —             | Email del usuario de test     |
| `cognito_test_user_password` | — (sensitive) | Password temporal             |
| `ses_sender_email`           | —             | Email verificado en SES       |

---

## Outputs globales (`outputs.tf`)

- `api_invoke_url` — URL del API Gateway para hacer curl
- `msk_bootstrap_brokers` — Para configurar las Lambdas manualmente si se necesita
- `cognito_user_pool_id` / `cognito_client_id` — Para obtener el JWT de test
- `redis_endpoint` — Para debug de ElastiCache
- `cloudwatch_dashboard_url` — Link directo al dashboard

---

## Decisiones de diseño

| Decisión | Razón |
|---|---|
| MSK Serverless en vez de MSK Provisioned | Sin gestión de brokers, ideal para TP |
| ElastiCache Serverless | Misma razón, evita elegir tipo de instancia |
| Políticas FullAccess en IAM | Simplicidad para TP; en prod se usaría least-privilege (mencionado en docs) |
| Backend local (no S3) | Sin infraestructura extra para el TP |
| Código Lambda como placeholder | El TP evalúa la infra, no el código Python |
| Un solo módulo `lambda` con for_each | Evita duplicar 6 módulos casi idénticos |

---

## Qué NO incluye

- Código Python de las Lambdas (solo stub placeholder)
- CI/CD (GitHub Actions, CodePipeline)
- Multi-environment (dev/staging/prod)
- Remote state backend (S3 + DynamoDB lock)
- WebSocket API (queda como diseño en documentación)
- WAF / Shield

---

## Orden de apply

Terraform resuelve el grafo automáticamente, pero el orden lógico es:

1. `vpc` → base de red
2. `iam`, `s3`, `cognito`, `dynamodb`, `sns_ses` → recursos independientes
3. `msk`, `elasticache` → necesitan VPC
4. `lambda` → necesita VPC, IAM, MSK, ElastiCache, DynamoDB, SNS/SES
5. `api_gateway` → necesita Lambda y Cognito
6. `cloudwatch` → necesita Lambda names

---

## Cómo usar

```bash
cd breadboss/
terraform init
cp terraform.tfvars.example terraform.tfvars  # completar emails
terraform plan
terraform apply

# Obtener JWT para test
aws cognito-idp initiate-auth \
  --client-id $(terraform output -raw cognito_client_id) \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@breadboss.com,PASSWORD=Test1234!

# Crear pedido
curl -X POST $(terraform output -raw api_invoke_url)/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel":"app","items":[...],"deliveryAddress":{...}}'
```
