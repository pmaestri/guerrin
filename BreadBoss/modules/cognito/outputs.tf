output "user_pool_id"       { value = aws_cognito_user_pool.this.id }
output "user_pool_endpoint" { value = "https://${aws_cognito_user_pool.this.endpoint}" }
output "client_id"          { value = aws_cognito_user_pool_client.app.id }
