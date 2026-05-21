resource "aws_security_group" "msk" {
  name        = "${var.prefix}-msk-sg"
  description = "MSK Serverless access"
  vpc_id      = var.vpc_id

  ingress {
    description = "MSK IAM/TLS from VPC"
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-msk-sg" }
}

resource "aws_msk_serverless_cluster" "this" {
  cluster_name = "${var.prefix}-kafka"

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.msk.id]
  }

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }

  tags = { Name = "${var.prefix}-kafka" }
}
