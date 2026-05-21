output "sns_topic_arn" { value = aws_sns_topic.notifications.arn }
output "ses_sender"    { value = aws_ses_email_identity.sender.email }
