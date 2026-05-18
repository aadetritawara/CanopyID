output "s3_bucket_name" {
  description = "The name of the S3 bucket for storing bird audio files"
  value       = aws_s3_bucket.audio_bucket.bucket
}

output "s3_bucket_arn" {
  description = "The ARN of the S3 bucket for IAM policies"
  value       = aws_s3_bucket.audio_bucket.arn
}

output "rds_endpoint" {
  description = "The endpoint of the RDS instance for database connections"
  value       = aws_db_instance.bird_db.endpoint
}

output "rds_name" {
  description = "The name of the RDS database"
  value       = aws_db_instance.bird_db.db_name
}

output "lambda_function_name" {
  description = "The name of the Lambda function for processing bird audio files"
  value       = aws_lambda_function.audio_classifier.function_name
}

output "s3_bucket_region" {
  description = "The region the S3 bucket is deployed in, needed for Presigned URLs"
  value       = aws_s3_bucket.audio_bucket.region
}

output "ecr_repository_url" {
  description = "The URL of the ECR repository for the Lambda function container image"
  value       = aws_ecr_repository.birdnet_repo.repository_url
}

output "ec2_public_dns" {
  description = "The public DNS of the EC2 instance"
  value       = aws_instance.backend_ec2.public_dns
}