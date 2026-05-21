resource "aws_sns_topic" "notifications" {
  name = "${var.prefix}-notifications"
  tags = { Name = "${var.prefix}-notifications" }
}

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}
