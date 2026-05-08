output "s3_bucket_name" {
  description = "The name of the S3 bucket for storing bird audio files"
  value       = aws_s3_bucket.audio_bucket.bucket
}

output "s3_bucket_arn" {
  description = "The ARN of the S3 bucket for IAM policies"
  value       = aws_s3_bucket.audio_bucket.arn
}

output "lambda_function_name" {
  description = "The name of the Lambda function for processing bird audio files"
  value       = aws_lambda_function.audio_classifier.function_name
}

output "s3_bucket_region" {
  description = "The region the S3 bucket is deployed in, needed for Presigned URLs"
  value       = aws_s3_bucket.audio_bucket.region
}