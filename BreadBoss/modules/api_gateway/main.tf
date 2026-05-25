resource "aws_apigatewayv2_api" "this" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
  }

  tags = { Name = "${var.prefix}-api" }
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

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- order-finalizer ---
resource "aws_apigatewayv2_integration" "order_finalizer" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_finalizer_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "deliver_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /orders/{orderId}/deliver"
  target             = "integrations/${aws_apigatewayv2_integration.order_finalizer.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_finalizer" {
  statement_id  = "AllowAPIGatewayInvokeOrderFinalizer"
  action        = "lambda:InvokeFunction"
  function_name = var.order_finalizer_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- order-reader ---
resource "aws_apigatewayv2_integration" "order_reader" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_reader_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /orders/{orderId}"
  target             = "integrations/${aws_apigatewayv2_integration.order_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_reader" {
  statement_id  = "AllowAPIGatewayInvokeOrderReader"
  action        = "lambda:InvokeFunction"
  function_name = var.order_reader_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- menu-reader ---
resource "aws_apigatewayv2_integration" "menu_reader" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.menu_reader_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_menu" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /menu"
  target             = "integrations/${aws_apigatewayv2_integration.menu_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "menu_reader" {
  statement_id  = "AllowAPIGatewayInvokeMenuReader"
  action        = "lambda:InvokeFunction"
  function_name = var.menu_reader_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- order-ready (POST /orders/{orderId}/ready) ---
resource "aws_apigatewayv2_integration" "order_ready" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.order_ready_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ready_order" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /orders/{orderId}/ready"
  target             = "integrations/${aws_apigatewayv2_integration.order_ready.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_lambda_permission" "order_ready" {
  statement_id  = "AllowAPIGatewayInvokeOrderReady"
  action        = "lambda:InvokeFunction"
  function_name = var.order_ready_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# --- GET /orders (lista por status, mismo Lambda que GET /orders/{orderId}) ---
resource "aws_apigatewayv2_route" "list_orders" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "GET /orders"
  target             = "integrations/${aws_apigatewayv2_integration.order_reader.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}
