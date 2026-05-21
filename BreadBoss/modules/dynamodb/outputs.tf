output "orders_table_name" { value = aws_dynamodb_table.orders.name }
output "orders_table_arn"  { value = aws_dynamodb_table.orders.arn }
output "menu_table_name"   { value = aws_dynamodb_table.menu.name }
output "menu_table_arn"    { value = aws_dynamodb_table.menu.arn }
