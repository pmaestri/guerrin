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

# D3: despliega el código real de ingress y order-processor.
# Se re-ejecuta automáticamente cuando cambia alguno de los handlers.
locals {
  lambdas_dir = "${path.root}/../lambdas"
  d3_functions = {
    ingress          = aws_lambda_function.this["ingress"].function_name
    order-processor  = aws_lambda_function.this["order-processor"].function_name
  }
}

resource "null_resource" "deploy_d3" {
  triggers = {
    ingress_hash         = filemd5("${local.lambdas_dir}/ingress/handler.py")
    order_processor_hash = filemd5("${local.lambdas_dir}/order-processor/handler.py")
  }

  provisioner "local-exec" {
    working_dir = local.lambdas_dir
    command     = <<-EOT
      bash package.sh
      aws lambda update-function-code \
        --function-name ${local.d3_functions["ingress"]} \
        --zip-file fileb://ingress/ingress.zip \
        --region ${var.aws_region} \
        --no-cli-pager
      aws lambda update-function-code \
        --function-name ${local.d3_functions["order-processor"]} \
        --zip-file fileb://order-processor/order-processor.zip \
        --region ${var.aws_region} \
        --no-cli-pager
    EOT
  }

  depends_on = [aws_lambda_function.this]
}
