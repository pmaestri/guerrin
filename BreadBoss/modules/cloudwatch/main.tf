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
