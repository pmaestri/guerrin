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

  password       = var.test_user_password
  message_action = "SUPPRESS"
}
