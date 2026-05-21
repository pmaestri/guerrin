output "redis_endpoint" {
  value = aws_elasticache_serverless_cache.this.endpoint[0].address
}

output "security_group_id" {
  value = aws_security_group.redis.id
}
