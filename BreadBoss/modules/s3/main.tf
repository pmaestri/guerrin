data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "assets" {
  bucket = "${var.prefix}-assets-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "${var.prefix}-assets" }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
