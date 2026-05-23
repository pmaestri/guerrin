locals {
  lambdas_dir = "${path.module}"

  # Lambdas sin dependencias externas: boto3 ya viene en el runtime de Lambda.
  # Terraform empaqueta el .py directamente con archive_file.
  simple_functions = toset(["order-processor", "order-finalizer", "order-reader", "menu-reader"])

  # Lambdas con dependencias externas (kafka, redis): requieren pip install previo.
  # El zip se construye con package.sh y Terraform lo referencia ya construido.
  packaged_functions = toset(["ingress", "kitchen-manager", "delivery-tracker", "stock-updater", "notifier"])

  functions = {
    ingress = {
      env_extras = { MENU_TABLE = var.menu_table_name }
    }
    order-processor = {
      env_extras = {}
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
  }

  # Consumers del topic "pedidos" (ORDER_CREATED)
  consumers_orders_created = ["order-processor", "kitchen-manager", "stock-updater", "notifier"]

  # Consumers del topic "orders.ready" (ORDER_READY — publicado por kitchen-manager)
  consumers_orders_ready = ["delivery-tracker", "notifier"]
}

# Zips para lambdas simples: Terraform los genera a partir del .py
data "archive_file" "simple" {
  for_each = local.simple_functions

  type        = "zip"
  source_file = "${local.lambdas_dir}/${each.key}/handler.py"
  output_path = "${local.lambdas_dir}/${each.key}/${each.key}.zip"
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

  # Lambdas simples usan el zip generado por archive_file.
  # Lambdas con dependencias referencian el zip pre-construido por package.sh.
  filename = contains(tolist(local.simple_functions), each.key) ? (
    data.archive_file.simple[each.key].output_path
  ) : (
    "${local.lambdas_dir}/${each.key}/${each.key}.zip"
  )

  source_code_hash = contains(tolist(local.simple_functions), each.key) ? (
    data.archive_file.simple[each.key].output_base64sha256
  ) : (
    filebase64sha256("${local.lambdas_dir}/${each.key}/${each.key}.zip")
  )

  tracing_config {
    mode = "Active"
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

resource "aws_lambda_event_source_mapping" "orders_created" {
  for_each = toset(local.consumers_orders_created)

  event_source_arn  = var.msk_cluster_arn
  function_name     = aws_lambda_function.this[each.key].arn
  topics            = ["pedidos"]
  starting_position = "LATEST"
  batch_size        = 10
}

resource "aws_lambda_event_source_mapping" "orders_ready" {
  for_each = toset(local.consumers_orders_ready)

  event_source_arn  = var.msk_cluster_arn
  function_name     = aws_lambda_function.this[each.key].arn
  topics            = ["orders.ready"]
  starting_position = "LATEST"
  batch_size        = 10
}
