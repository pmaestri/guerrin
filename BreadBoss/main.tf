module "vpc" {
  source     = "./modules/vpc"
  prefix     = var.prefix
  aws_region = var.aws_region
  az_count   = var.az_count
}

module "iam" {
  source = "./modules/iam"
  prefix = var.prefix
}

module "s3" {
  source = "./modules/s3"
  prefix = var.prefix
}

module "cognito" {
  source             = "./modules/cognito"
  prefix             = var.prefix
  test_user_email    = var.cognito_test_user_email
  test_user_password = var.cognito_test_user_password
}

module "dynamodb" {
  source = "./modules/dynamodb"
  prefix = var.prefix
}

module "sns_ses" {
  source       = "./modules/sns_ses"
  prefix       = var.prefix
  sender_email = var.ses_sender_email
}

module "msk" {
  source     = "./modules/msk"
  prefix     = var.prefix
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "elasticache" {
  source     = "./modules/elasticache"
  prefix     = var.prefix
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "lambda" {
  source               = "./modules/lambda"
  prefix               = var.prefix
  vpc_id               = module.vpc.vpc_id
  subnet_ids           = module.vpc.private_subnet_ids
  lambda_role_arn      = module.iam.lambda_role_arn
  msk_cluster_arn      = module.msk.cluster_arn
  msk_bootstrap        = module.msk.bootstrap_brokers_sasl_iam
  msk_sg_id            = module.msk.security_group_id
  redis_host           = module.elasticache.redis_endpoint
  sns_topic_arn        = module.sns_ses.sns_topic_arn
  ses_sender           = module.sns_ses.ses_sender
  aws_region           = var.aws_region
  orders_table_name    = "${var.prefix}-orders"
  menu_table_name      = "${var.prefix}-menu"
  processed_table_name = "${var.prefix}-processed"
}

module "api_gateway" {
  source               = "./modules/api_gateway"
  prefix               = var.prefix
  lambda_arn           = module.lambda.ingress_function_arn
  lambda_name          = module.lambda.ingress_function_name
  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_endpoint     = module.cognito.user_pool_endpoint
  cognito_client_id    = module.cognito.client_id
  aws_region           = var.aws_region
  order_finalizer_arn  = module.lambda.order_finalizer_arn
  order_finalizer_name = module.lambda.order_finalizer_name
  order_reader_arn     = module.lambda.order_reader_arn
  order_reader_name    = module.lambda.order_reader_name
  menu_reader_arn      = module.lambda.menu_reader_arn
  menu_reader_name     = module.lambda.menu_reader_name
  order_ready_arn      = module.lambda.order_ready_arn
  order_ready_name     = module.lambda.order_ready_name
}

module "cloudwatch" {
  source         = "./modules/cloudwatch"
  prefix         = var.prefix
  function_names = module.lambda.all_function_names
  sns_topic_arn  = module.sns_ses.sns_topic_arn
  aws_region     = var.aws_region
}

module "auditor" {
  source               = "./modules/auditor"
  lambda_role_arn      = module.iam.lambda_role_arn
  orders_table_name    = module.dynamodb.orders_table_name
  resumenes_table_name = module.dynamodb.resumenes_table_name
  metricas_table_name  = module.dynamodb.metricas_table_name
  openai_api_key       = var.openai_api_key
  aws_region           = var.aws_region
}
