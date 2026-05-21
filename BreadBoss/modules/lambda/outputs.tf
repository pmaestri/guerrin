output "ingress_function_arn" {
  value = aws_lambda_function.this["ingress"].arn
}

output "ingress_function_name" {
  value = aws_lambda_function.this["ingress"].function_name
}

output "all_function_names" {
  value = { for k, v in aws_lambda_function.this : k => v.function_name }
}

output "all_function_arns" {
  value = { for k, v in aws_lambda_function.this : k => v.arn }
}
