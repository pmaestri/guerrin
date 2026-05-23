data "archive_file" "auditor" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/breadboss_auditor.zip"
}

resource "aws_cloudwatch_log_group" "auditor" {
  name              = "/aws/lambda/breadboss-auditor"
  retention_in_days = 14
}

resource "aws_lambda_function" "auditor" {
  function_name = "breadboss-auditor"
  role          = var.lambda_role_arn
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  timeout       = 60
  memory_size   = 128
  filename      = data.archive_file.auditor.output_path

  environment {
    variables = {
      OPENAI_API_KEY     = var.openai_api_key
      ORDERS_TABLE       = var.orders_table_name
      RESUMENES_TABLE    = var.resumenes_table_name
      METRICAS_TABLE     = var.metricas_table_name
      ENTREGA_UMBRAL_MIN = tostring(var.entrega_umbral_min)
      AWS_REGION_NAME    = var.aws_region
    }
  }

  depends_on = [aws_cloudwatch_log_group.auditor]

  tags = { Name = "breadboss-auditor" }
}

resource "aws_cloudwatch_event_rule" "daily_audit" {
  name                = "breadboss-daily-audit"
  description         = "Dispara el auditor de BreadBoss todos los días a las 23:59 UTC"
  schedule_expression = "cron(59 23 * * ? *)"
}

resource "aws_cloudwatch_event_target" "auditor" {
  rule      = aws_cloudwatch_event_rule.daily_audit.name
  target_id = "breadboss-auditor"
  arn       = aws_lambda_function.auditor.arn
  input     = jsonencode({})
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auditor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_audit.arn
}
