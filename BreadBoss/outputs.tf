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
