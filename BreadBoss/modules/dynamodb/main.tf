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
  attribute {
    name = "fecha"
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

  global_secondary_index {
    name            = "fecha-index"
    hash_key        = "fecha"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = { Name = "${var.prefix}-orders" }
}

resource "aws_dynamodb_table" "resumenes" {
  name         = "breadboss_resumenes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "fecha"

  attribute {
    name = "fecha"
    type = "S"
  }

  tags = { Name = "breadboss_resumenes" }
}

resource "aws_dynamodb_table" "metricas" {
  name         = "breadboss_metricas"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "fecha"

  attribute {
    name = "fecha"
    type = "S"
  }

  tags = { Name = "breadboss_metricas" }
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

resource "aws_dynamodb_table" "processed" {
  name         = "${var.prefix}-processed"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"
  range_key    = "consumer"

  attribute {
    name = "orderId"
    type = "S"
  }
  attribute {
    name = "consumer"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  tags = { Name = "${var.prefix}-processed" }
}

output "processed_table_name" {
  value = aws_dynamodb_table.processed.name
}
