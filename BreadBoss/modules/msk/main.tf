resource "aws_security_group" "msk" {
  name        = "${var.prefix}-msk-sg"
  description = "MSK Serverless access"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.prefix}-msk-sg" }
}

# Lambda ESM poller ENIs use the MSK SG (not Lambda SG), so the MSK SG
# must allow inbound from itself on 9098 for the poller to reach the cluster.
resource "aws_vpc_security_group_ingress_rule" "msk_self" {
  security_group_id            = aws_security_group.msk.id
  referenced_security_group_id = aws_security_group.msk.id
  ip_protocol                  = "tcp"
  from_port                    = 9098
  to_port                      = 9098
  description                  = "MSK ESM poller self-access"
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
