resource "aws_security_group" "redis" {
  name        = "${var.prefix}-redis-sg"
  description = "Redis ElastiCache access"
  vpc_id      = var.vpc_id

  ingress {
    description = "Redis from VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-redis-sg" }
}

resource "aws_elasticache_serverless_cache" "this" {
  engine = "redis"
  name   = "${var.prefix}-cache"

  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.redis.id]

  cache_usage_limits {
    data_storage {
      maximum = 10
      unit    = "GB"
    }
    ecpu_per_second {
      maximum = 1000
    }
  }

  tags = { Name = "${var.prefix}-cache" }
}
