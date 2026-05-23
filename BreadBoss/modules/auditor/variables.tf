variable "lambda_role_arn" {
  type = string
}

variable "orders_table_name" {
  type = string
}

variable "resumenes_table_name" {
  type = string
}

variable "metricas_table_name" {
  type = string
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "aws_region" {
  type = string
}

variable "entrega_umbral_min" {
  type    = number
  default = 45
}
