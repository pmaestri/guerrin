output "orders_table_name" { value = aws_dynamodb_table.orders.name }
output "orders_table_arn" { value = aws_dynamodb_table.orders.arn }
output "menu_table_name" { value = aws_dynamodb_table.menu.name }
output "menu_table_arn" { value = aws_dynamodb_table.menu.arn }
output "resumenes_table_name" { value = aws_dynamodb_table.resumenes.name }
output "resumenes_table_arn" { value = aws_dynamodb_table.resumenes.arn }
output "metricas_table_name" { value = aws_dynamodb_table.metricas.name }
output "metricas_table_arn" { value = aws_dynamodb_table.metricas.arn }
