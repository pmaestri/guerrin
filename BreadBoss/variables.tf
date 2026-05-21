variable "aws_region" {
  description = "Región AWS de despliegue"
  type        = string
  default     = "us-east-1"
}

variable "prefix" {
  description = "Prefijo para nombrar todos los recursos"
  type        = string
  default     = "breadboss"
}

variable "az_count" {
  description = "Cantidad de Availability Zones a usar"
  type        = number
  default     = 2
}

variable "cognito_test_user_email" {
  description = "Email del usuario de test en Cognito"
  type        = string
}

variable "cognito_test_user_password" {
  description = "Password del usuario de test en Cognito"
  type        = string
  sensitive   = true
}

variable "ses_sender_email" {
  description = "Email verificado en SES para enviar notificaciones"
  type        = string
}
