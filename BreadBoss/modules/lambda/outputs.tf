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

output "order_finalizer_arn" { value = aws_lambda_function.this["order-finalizer"].arn }
output "order_finalizer_name" { value = aws_lambda_function.this["order-finalizer"].function_name }
output "order_reader_arn" { value = aws_lambda_function.this["order-reader"].arn }
output "order_reader_name" { value = aws_lambda_function.this["order-reader"].function_name }
output "menu_reader_arn" { value = aws_lambda_function.this["menu-reader"].arn }
output "menu_reader_name" { value = aws_lambda_function.this["menu-reader"].function_name }
output "order_ready_arn" { value = aws_lambda_function.this["order-ready"].arn }
output "order_ready_name" { value = aws_lambda_function.this["order-ready"].function_name }
