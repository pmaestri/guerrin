# BreadBoss IaC — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear la infraestructura completa de BreadBoss en Terraform con 11 módulos por servicio AWS, reproducible con un solo `terraform apply`.

**Architecture:** Módulos independientes por servicio (vpc, msk, dynamodb, elasticache, cognito, s3, iam, lambda, api_gateway, sns_ses, cloudwatch) compuestos en un root module. El módulo lambda usa `for_each` para las 6 funciones. El código Python de las Lambdas es un stub placeholder generado con `archive_file`.

**Tech Stack:** Terraform >= 1.6, AWS Provider ~> 5.0, Python 3.11 (stub), us-east-1.

---

## Mapa de archivos

```
BreadBoss/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── terraform.tfvars.example
└── modules/
    ├── vpc/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── msk/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── dynamodb/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── elasticache/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── cognito/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── s3/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── iam/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── lambda/
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── outputs.tf
    │   └── stub/
    │       └── handler.py
    ├── api_gateway/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── sns_ses/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── cloudwatch/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

---

## Task 1: Scaffolding del proyecto y configuración base

**Files:**
- Create: `BreadBoss/versions.tf`
- Create: `BreadBoss/variables.tf`
- Create: `BreadBoss/terraform.tfvars.example`

- [ ] **Step 1: Crear la carpeta raíz y estructura de módulos**

```bash
mkdir -p BreadBoss/modules/{vpc,msk,dynamodb,elasticache,cognito,s3,iam,lambda/stub,api_gateway,sns_ses,cloudwatch}
```

- [ ] **Step 2: Crear `versions.tf`**

```hcl
# BreadBoss/versions.tf
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
```

- [ ] **Step 3: Crear `variables.tf` del root module**

```hcl
# BreadBoss/variables.tf
variable "aws_region" {
  description = "Región AWS de despliegue"
  type        = string
  default     = "us-east-1"
}

variable "prefix" {
  description = "Prefijo para nombrar todos los recursos"
  type        = string
  default     = "breadboss"
}

variable "az_count" {
  description = "Cantidad de Availability Zones a usar"
  type        = number
  default     = 2
}

variable "cognito_test_user_email" {
  description = "Email del usuario de test en Cognito"
  type        = string
}

variable "cognito_test_user_password" {
  description = "Password del usuario de test en Cognito"
  type        = string
  sensitive   = true
}

variable "ses_sender_email" {
  description = "Email verificado en SES para enviar notificaciones"
  type        = string
}
```

- [ ] **Step 4: Crear `terraform.tfvars.example`**

```hcl
# BreadBoss/terraform.tfvars.example
# Copiá este archivo a terraform.tfvars y completá los valores
aws_region                 = "us-east-1"
prefix                     = "breadboss"
az_count                   = 2
cognito_test_user_email    = "test@breadboss.com"
cognito_test_user_password = "Test1234!"
ses_sender_email           = "noreply@breadboss.com"
```

- [ ] **Step 5: Crear stub de Lambda**

```bash
cat > BreadBoss/modules/lambda/stub/handler.py << 'EOF'
def handler(event, context):
    return {"statusCode": 200, "body": "stub"}
EOF
```

- [ ] **Step 6: Commit inicial**

```bash
git add BreadBoss/
git commit -m "feat: scaffolding inicial BreadBoss IaC"
```

---

## Task 2: Módulo VPC

**Files:**
- Create: `BreadBoss/modules/vpc/main.tf`
- Create: `BreadBoss/modules/vpc/variables.tf`
- Create: `BreadBoss/modules/vpc/outputs.tf`

- [ ] **Step 1: Crear `modules/vpc/variables.tf`**

```hcl
# BreadBoss/modules/vpc/variables.tf
variable "prefix" {
  type = string
}

variable "cidr_block" {
  type    = string
  default = "10.0.0.0/16"
}

variable "az_count" {
  type    = number
  default = 2
}

variable "aws_region" {
  type = string
}
```

- [ ] **Step 2: Crear `modules/vpc/main.tf`**

```hcl
# BreadBoss/modules/vpc/main.tf
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.prefix}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.prefix}-igw" }
}

resource "aws_subnet" "public" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = true
  tags = { Name = "${var.prefix}-public-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = { Name = "${var.prefix}-private-${count.index + 1}" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.prefix}-nat-eip" }
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "${var.prefix}-nat" }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.prefix}-rt-public" }

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.prefix}-rt-private" }

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
```

- [ ] **Step 3: Crear `modules/vpc/outputs.tf`**

```hcl
# BreadBoss/modules/vpc/outputs.tf
output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/vpc/
git commit -m "feat: módulo vpc"
```

---

## Task 3: Módulo IAM

**Files:**
- Create: `BreadBoss/modules/iam/main.tf`
- Create: `BreadBoss/modules/iam/variables.tf`
- Create: `BreadBoss/modules/iam/outputs.tf`

- [ ] **Step 1: Crear `modules/iam/variables.tf`**

```hcl
# BreadBoss/modules/iam/variables.tf
variable "prefix" {
  type = string
}
```

- [ ] **Step 2: Crear `modules/iam/main.tf`**

```hcl
# BreadBoss/modules/iam/main.tf
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

locals {
  managed_policies = [
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
    "arn:aws:iam::aws:policy/AmazonMSKFullAccess",
    "arn:aws:iam::aws:policy/AmazonElastiCacheFullAccess",
    "arn:aws:iam::aws:policy/AmazonSNSFullAccess",
    "arn:aws:iam::aws:policy/AmazonSESFullAccess",
    "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
    "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess",
  ]
}

resource "aws_iam_role_policy_attachment" "lambda" {
  for_each   = toset(local.managed_policies)
  role       = aws_iam_role.lambda.name
  policy_arn = each.value
}
```

- [ ] **Step 3: Crear `modules/iam/outputs.tf`**

```hcl
# BreadBoss/modules/iam/outputs.tf
output "lambda_role_arn" {
  value = aws_iam_role.lambda.arn
}
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/iam/
git commit -m "feat: módulo iam"
```

---

## Task 4: Módulos S3, Cognito y DynamoDB

**Files:**
- Create: `BreadBoss/modules/s3/main.tf`, `variables.tf`, `outputs.tf`
- Create: `BreadBoss/modules/cognito/main.tf`, `variables.tf`, `outputs.tf`
- Create: `BreadBoss/modules/dynamodb/main.tf`, `variables.tf`, `outputs.tf`

- [ ] **Step 1: Crear módulo S3**

```hcl
# BreadBoss/modules/s3/variables.tf
variable "prefix" { type = string }
```

```hcl
# BreadBoss/modules/s3/main.tf
resource "aws_s3_bucket" "assets" {
  bucket = "${var.prefix}-assets"
  tags   = { Name = "${var.prefix}-assets" }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

```hcl
# BreadBoss/modules/s3/outputs.tf
output "bucket_name" { value = aws_s3_bucket.assets.bucket }
output "bucket_arn"  { value = aws_s3_bucket.assets.arn }
```

- [ ] **Step 2: Crear módulo Cognito**

```hcl
# BreadBoss/modules/cognito/variables.tf
variable "prefix"            { type = string }
variable "test_user_email"   { type = string }
variable "test_user_password" {
  type      = string
  sensitive = true
}
```

```hcl
# BreadBoss/modules/cognito/main.tf
resource "aws_cognito_user_pool" "this" {
  name = "${var.prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  tags = { Name = "${var.prefix}-users" }
}

resource "aws_cognito_user_pool_client" "app" {
  name         = "${var.prefix}-app"
  user_pool_id = aws_cognito_user_pool.this.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}

resource "aws_cognito_user" "test" {
  user_pool_id = aws_cognito_user_pool.this.id
  username     = var.test_user_email

  attributes = {
    email          = var.test_user_email
    email_verified = "true"
  }

  password         = var.test_user_password
  message_action   = "SUPPRESS"
}
```

```hcl
# BreadBoss/modules/cognito/outputs.tf
output "user_pool_id"       { value = aws_cognito_user_pool.this.id }
output "user_pool_endpoint" { value = "https://${aws_cognito_user_pool.this.endpoint}" }
output "client_id"          { value = aws_cognito_user_pool_client.app.id }
```

- [ ] **Step 3: Crear módulo DynamoDB**

```hcl
# BreadBoss/modules/dynamodb/variables.tf
variable "prefix" { type = string }
```

```hcl
# BreadBoss/modules/dynamodb/main.tf
resource "aws_dynamodb_table" "orders" {
  name         = "${var.prefix}-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"
  range_key    = "timestamp"

  attribute {
    name = "orderId"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "N"
  }
  attribute {
    name = "channel"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "channel-index"
    hash_key        = "channel"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = { Name = "${var.prefix}-orders" }
}

resource "aws_dynamodb_table" "menu" {
  name         = "${var.prefix}-menu"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "itemId"

  attribute {
    name = "itemId"
    type = "S"
  }

  tags = { Name = "${var.prefix}-menu" }
}
```

```hcl
# BreadBoss/modules/dynamodb/outputs.tf
output "orders_table_name" { value = aws_dynamodb_table.orders.name }
output "orders_table_arn"  { value = aws_dynamodb_table.orders.arn }
output "menu_table_name"   { value = aws_dynamodb_table.menu.name }
output "menu_table_arn"    { value = aws_dynamodb_table.menu.arn }
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/s3/ BreadBoss/modules/cognito/ BreadBoss/modules/dynamodb/
git commit -m "feat: módulos s3, cognito y dynamodb"
```

---

## Task 5: Módulos MSK y ElastiCache

**Files:**
- Create: `BreadBoss/modules/msk/main.tf`, `variables.tf`, `outputs.tf`
- Create: `BreadBoss/modules/elasticache/main.tf`, `variables.tf`, `outputs.tf`

- [ ] **Step 1: Crear módulo MSK**

```hcl
# BreadBoss/modules/msk/variables.tf
variable "prefix"     { type = string }
variable "vpc_id"     { type = string }
variable "subnet_ids" { type = list(string) }
```

```hcl
# BreadBoss/modules/msk/main.tf
resource "aws_security_group" "msk" {
  name        = "${var.prefix}-msk-sg"
  description = "MSK Serverless access"
  vpc_id      = var.vpc_id

  ingress {
    description = "MSK IAM/TLS from VPC"
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-msk-sg" }
}

resource "aws_msk_serverless_cluster" "this" {
  cluster_name = "${var.prefix}-kafka"

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.msk.id]
  }

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }

  tags = { Name = "${var.prefix}-kafka" }
}
```

```hcl
# BreadBoss/modules/msk/outputs.tf
output "cluster_arn"              { value = aws_msk_serverless_cluster.this.arn }
output "bootstrap_brokers_sasl_iam" { value = aws_msk_serverless_cluster.this.bootstrap_brokers_sasl_iam }
output "security_group_id"        { value = aws_security_group.msk.id }
```

- [ ] **Step 2: Crear módulo ElastiCache**

```hcl
# BreadBoss/modules/elasticache/variables.tf
variable "prefix"     { type = string }
variable "vpc_id"     { type = string }
variable "subnet_ids" { type = list(string) }
```

```hcl
# BreadBoss/modules/elasticache/main.tf
resource "aws_security_group" "redis" {
  name        = "${var.prefix}-redis-sg"
  description = "Redis ElastiCache access"
  vpc_id      = var.vpc_id

  ingress {
    description = "Redis from VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-redis-sg" }
}

resource "aws_elasticache_serverless_cache" "this" {
  engine = "redis"
  name   = "${var.prefix}-cache"

  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.redis.id]

  cache_usage_limits {
    data_storage {
      maximum = 10
      unit    = "GB"
    }
    ecpu_per_second {
      maximum = 1000
    }
  }

  tags = { Name = "${var.prefix}-cache" }
}
```

```hcl
# BreadBoss/modules/elasticache/outputs.tf
output "redis_endpoint"        { value = aws_elasticache_serverless_cache.this.endpoint[0].address }
output "security_group_id"     { value = aws_security_group.redis.id }
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/msk/ BreadBoss/modules/elasticache/
git commit -m "feat: módulos msk y elasticache"
```

---

## Task 6: Módulo SNS/SES

**Files:**
- Create: `BreadBoss/modules/sns_ses/main.tf`, `variables.tf`, `outputs.tf`

- [ ] **Step 1: Crear módulo sns_ses**

```hcl
# BreadBoss/modules/sns_ses/variables.tf
variable "prefix"       { type = string }
variable "sender_email" { type = string }
```

```hcl
# BreadBoss/modules/sns_ses/main.tf
resource "aws_sns_topic" "notifications" {
  name = "${var.prefix}-notifications"
  tags = { Name = "${var.prefix}-notifications" }
}

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}
```

```hcl
# BreadBoss/modules/sns_ses/outputs.tf
output "sns_topic_arn" { value = aws_sns_topic.notifications.arn }
output "ses_sender"    { value = aws_ses_email_identity.sender.email }
```

- [ ] **Step 2: Commit**

```bash
git add BreadBoss/modules/sns_ses/
git commit -m "feat: módulo sns_ses"
```

---

## Task 7: Módulo Lambda

**Files:**
- Create: `BreadBoss/modules/lambda/main.tf`
- Create: `BreadBoss/modules/lambda/variables.tf`
- Create: `BreadBoss/modules/lambda/outputs.tf`

- [ ] **Step 1: Crear `modules/lambda/variables.tf`**

```hcl
# BreadBoss/modules/lambda/variables.tf
variable "prefix"          { type = string }
variable "vpc_id"          { type = string }
variable "subnet_ids"      { type = list(string) }
variable "lambda_role_arn" { type = string }
variable "msk_cluster_arn" { type = string }
variable "msk_bootstrap"   { type = string }
variable "redis_host"      { type = string }
variable "sns_topic_arn"   { type = string }
variable "ses_sender"      { type = string }
variable "aws_region"      { type = string }
```

- [ ] **Step 2: Crear `modules/lambda/main.tf`**

```hcl
# BreadBoss/modules/lambda/main.tf
data "archive_file" "stub" {
  type        = "zip"
  source_file = "${path.module}/stub/handler.py"
  output_path = "${path.module}/stub/handler.zip"
}

resource "aws_security_group" "lambda" {
  name        = "${var.prefix}-lambda-sg"
  description = "Lambda egress to VPC services"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-lambda-sg" }
}

locals {
  functions = {
    ingress = {
      env_extras = {}
    }
    order-processor = {
      env_extras = {}
    }
    kitchen-manager = {
      env_extras = { REDIS_HOST = var.redis_host }
    }
    stock-updater = {
      env_extras = {}
    }
    delivery-tracker = {
      env_extras = { REDIS_HOST = var.redis_host }
    }
    notifier = {
      env_extras = {
        SNS_TOPIC_ARN = var.sns_topic_arn
        SES_SENDER    = var.ses_sender
      }
    }
  }

  consumers = ["order-processor", "kitchen-manager", "stock-updater", "delivery-tracker", "notifier"]
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.functions
  name              = "/aws/lambda/${var.prefix}-${each.key}"
  retention_in_days = 14
}

resource "aws_lambda_function" "this" {
  for_each = local.functions

  function_name = "${var.prefix}-${each.key}"
  role          = var.lambda_role_arn
  runtime       = "python3.11"
  handler       = "handler.handler"
  timeout       = 30
  memory_size   = 256
  filename      = data.archive_file.stub.output_path

  tracing_config {
    mode = "PassThrough"
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(
      {
        MSK_BOOTSTRAP   = var.msk_bootstrap
        AWS_REGION_NAME = var.aws_region
      },
      each.value.env_extras
    )
  }

  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = { Name = "${var.prefix}-${each.key}" }
}

resource "aws_lambda_event_source_mapping" "msk" {
  for_each = toset(local.consumers)

  event_source_arn  = var.msk_cluster_arn
  function_name     = aws_lambda_function.this[each.key].arn
  topics            = ["pedidos"]
  starting_position = "LATEST"
  batch_size        = 10
}
```

- [ ] **Step 3: Crear `modules/lambda/outputs.tf`**

```hcl
# BreadBoss/modules/lambda/outputs.tf
output "ingress_function_arn" {
  value = aws_lambda_function.this["ingress"].arn
}

output "ingress_function_name" {
  value = aws_lambda_function.this["ingress"].name
}

output "all_function_names" {
  value = { for k, v in aws_lambda_function.this : k => v.function_name }
}

output "all_function_arns" {
  value = { for k, v in aws_lambda_function.this : k => v.arn }
}
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/lambda/
git commit -m "feat: módulo lambda con for_each y event source mappings MSK"
```

---

## Task 8: Módulo API Gateway

**Files:**
- Create: `BreadBoss/modules/api_gateway/main.tf`, `variables.tf`, `outputs.tf`

- [ ] **Step 1: Crear `modules/api_gateway/variables.tf`**

```hcl
# BreadBoss/modules/api_gateway/variables.tf
variable "prefix"              { type = string }
variable "lambda_arn"          { type = string }
variable "lambda_name"         { type = string }
variable "cognito_user_pool_id" { type = string }
variable "cognito_endpoint"    { type = string }
variable "cognito_client_id"   { type = string }
variable "aws_region"          { type = string }
```

- [ ] **Step 2: Crear `modules/api_gateway/main.tf`**

```hcl
# BreadBoss/modules/api_gateway/main.tf
resource "aws_apigatewayv2_api" "this" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"
  tags          = { Name = "${var.prefix}-api" }
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.this.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-auth"

  jwt_configuration {
    audience = [var.cognito_client_id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${var.cognito_user_pool_id}"
  }
}

resource "aws_apigatewayv2_integration" "ingress" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_orders" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /orders"
  target             = "integrations/${aws_apigatewayv2_integration.ingress.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
```

- [ ] **Step 3: Crear `modules/api_gateway/outputs.tf`**

```hcl
# BreadBoss/modules/api_gateway/outputs.tf
output "api_url" { value = aws_apigatewayv2_stage.default.invoke_url }
output "api_id"  { value = aws_apigatewayv2_api.this.id }
```

- [ ] **Step 4: Commit**

```bash
git add BreadBoss/modules/api_gateway/
git commit -m "feat: módulo api_gateway con Cognito JWT authorizer"
```

---

## Task 9: Módulo CloudWatch

**Files:**
- Create: `BreadBoss/modules/cloudwatch/main.tf`, `variables.tf`, `outputs.tf`

- [ ] **Step 1: Crear `modules/cloudwatch/variables.tf`**

```hcl
# BreadBoss/modules/cloudwatch/variables.tf
variable "prefix"         { type = string }
variable "function_names" { type = map(string) }
variable "sns_topic_arn"  { type = string }
variable "aws_region"     { type = string }
```

- [ ] **Step 2: Crear `modules/cloudwatch/main.tf`**

```hcl
# BreadBoss/modules/cloudwatch/main.tf
locals {
  fn_list = values(var.function_names)
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.prefix}-Operations"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "Lambda Invocations"
          period = 60
          stat   = "Sum"
          metrics = [
            for fn in local.fn_list : ["AWS/Lambda", "Invocations", "FunctionName", fn]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "Lambda Errors"
          period = 60
          stat   = "Sum"
          metrics = [
            for fn in local.fn_list : ["AWS/Lambda", "Errors", "FunctionName", fn]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "Lambda Duration (ms)"
          period = 60
          stat   = "Average"
          metrics = [
            for fn in local.fn_list : ["AWS/Lambda", "Duration", "FunctionName", fn]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "Pedidos Creados"
          period  = 60
          stat    = "Sum"
          metrics = [["BreadBoss", "OrdersCreated"]]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "DynamoDB ReadCapacity"
          period  = 60
          stat    = "Sum"
          metrics = [["AWS/DynamoDB", "ConsumedReadCapacityUnits"]]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.prefix}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Lambda errors > 1 in 5 minutes"
  alarm_actions       = [var.sns_topic_arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.prefix}-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 5000
  alarm_description   = "Lambda duration > 5000ms"
  alarm_actions       = [var.sns_topic_arn]
  treat_missing_data  = "notBreaching"
}
```

```hcl
# BreadBoss/modules/cloudwatch/outputs.tf
output "dashboard_name" { value = aws_cloudwatch_dashboard.main.dashboard_name }
```

- [ ] **Step 3: Commit**

```bash
git add BreadBoss/modules/cloudwatch/
git commit -m "feat: módulo cloudwatch con dashboard y alarmas"
```

---

## Task 10: Root module — composición final

**Files:**
- Create: `BreadBoss/main.tf`
- Create: `BreadBoss/outputs.tf`

- [ ] **Step 1: Crear `BreadBoss/main.tf`**

```hcl
# BreadBoss/main.tf
module "vpc" {
  source     = "./modules/vpc"
  prefix     = var.prefix
  aws_region = var.aws_region
  az_count   = var.az_count
}

module "iam" {
  source = "./modules/iam"
  prefix = var.prefix
}

module "s3" {
  source = "./modules/s3"
  prefix = var.prefix
}

module "cognito" {
  source              = "./modules/cognito"
  prefix              = var.prefix
  test_user_email     = var.cognito_test_user_email
  test_user_password  = var.cognito_test_user_password
}

module "dynamodb" {
  source = "./modules/dynamodb"
  prefix = var.prefix
}

module "sns_ses" {
  source       = "./modules/sns_ses"
  prefix       = var.prefix
  sender_email = var.ses_sender_email
}

module "msk" {
  source     = "./modules/msk"
  prefix     = var.prefix
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "elasticache" {
  source     = "./modules/elasticache"
  prefix     = var.prefix
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "lambda" {
  source          = "./modules/lambda"
  prefix          = var.prefix
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids
  lambda_role_arn = module.iam.lambda_role_arn
  msk_cluster_arn = module.msk.cluster_arn
  msk_bootstrap   = module.msk.bootstrap_brokers_sasl_iam
  redis_host      = module.elasticache.redis_endpoint
  sns_topic_arn   = module.sns_ses.sns_topic_arn
  ses_sender      = module.sns_ses.ses_sender
  aws_region      = var.aws_region
}

module "api_gateway" {
  source               = "./modules/api_gateway"
  prefix               = var.prefix
  lambda_arn           = module.lambda.ingress_function_arn
  lambda_name          = module.lambda.ingress_function_name
  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_endpoint     = module.cognito.user_pool_endpoint
  cognito_client_id    = module.cognito.client_id
  aws_region           = var.aws_region
}

module "cloudwatch" {
  source         = "./modules/cloudwatch"
  prefix         = var.prefix
  function_names = module.lambda.all_function_names
  sns_topic_arn  = module.sns_ses.sns_topic_arn
  aws_region     = var.aws_region
}
```

- [ ] **Step 2: Crear `BreadBoss/outputs.tf`**

```hcl
# BreadBoss/outputs.tf
output "api_invoke_url" {
  description = "URL del API Gateway — usá esta URL para hacer POST /orders"
  value       = module.api_gateway.api_url
}

output "msk_bootstrap_brokers" {
  description = "Bootstrap brokers del cluster MSK Serverless"
  value       = module.msk.bootstrap_brokers_sasl_iam
}

output "cognito_user_pool_id" {
  description = "ID del User Pool de Cognito"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "App Client ID de Cognito — necesario para obtener el JWT"
  value       = module.cognito.client_id
}

output "redis_endpoint" {
  description = "Endpoint del cluster Redis (ElastiCache Serverless)"
  value       = module.elasticache.redis_endpoint
}

output "cloudwatch_dashboard_url" {
  description = "URL directa al dashboard de CloudWatch"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home#dashboards:name=${module.cloudwatch.dashboard_name}"
}
```

- [ ] **Step 3: Verificar que el plan no tiene errores de sintaxis**

```bash
cd BreadBoss/
terraform init
terraform validate
```

Expected output:
```
Success! The configuration is valid.
```

- [ ] **Step 4: Verificar el plan completo (sin credenciales reales, usando `-var` para inputs requeridos)**

```bash
terraform plan \
  -var="cognito_test_user_email=test@breadboss.com" \
  -var="cognito_test_user_password=Test1234!" \
  -var="ses_sender_email=noreply@breadboss.com"
```

Expected: plan con ~50-60 resources a crear, sin errores.

- [ ] **Step 5: Commit final**

```bash
git add BreadBoss/main.tf BreadBoss/outputs.tf
git commit -m "feat: root module — composición completa de BreadBoss IaC"
```

---

## Verificación final

Una vez ejecutado `terraform apply` con credenciales AWS reales:

```bash
# 1. Ver todos los outputs
terraform output

# 2. Obtener JWT de Cognito
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id $(terraform output -raw cognito_client_id) \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters \
    USERNAME=$(terraform output -raw cognito_user_pool_id | cut -d_ -f1)@breadboss.com,PASSWORD=Test1234! \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# 3. Crear un pedido de prueba
curl -X POST "$(terraform output -raw api_invoke_url)/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "app",
    "items": [{"itemId":"burger_01","name":"Smash Burger","qty":1,"price":4500}],
    "deliveryAddress": {"street": "Av. Corrientes 1234", "lat": -34.6037, "lng": -58.3816}
  }'

# 4. Verificar DynamoDB
aws dynamodb scan --table-name breadboss-orders \
  --query 'Items[0].{id:orderId,status:status}'

# 5. Ver dashboard
echo "Dashboard: $(terraform output -raw cloudwatch_dashboard_url)"
```
