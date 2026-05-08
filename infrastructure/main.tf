provider "aws" {
  region = "us-east-1"
}

# S3 bucket to store bird audio files
resource "aws_s3_bucket" "audio_bucket" {
  bucket = "canopy-id-bucket" 

  force_destroy = true

  tags = {
    Name        = "CanopyID Bird Audio Upload Bucket"
  }
}

# CORS configuration for the S3 bucket to allow cross-origin requests from the frontend
resource "aws_s3_bucket_cors_configuration" "audio_bucket_cors" {
  bucket = aws_s3_bucket.audio_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = ["*"] # TODO: Restrict this to the domain when deployed
    max_age_seconds = 3000
  }
}

# IAM role for lambda function to access S3 bucket
resource "aws_iam_role" "lambda_s3_access_role" {
  name = "lambda_s3_access_role"
    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
        {
            Action = "sts:AssumeRole"
            Effect = "Allow"
            Principal = {
                Service = "lambda.amazonaws.com"
            }
        }
        ]
    })
}

# IAM policy to give Lambda permission to write CloudWatch logs
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_s3_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM policy to give Lambda permission to read from the S3 bucket
resource "aws_iam_role_policy_attachment" "lambda_s3_read" {
  role       = aws_iam_role.lambda_s3_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}

# Zip up the Lambda function code (lambda_handler.py) to be uploaded to AWS Lambda
data "archive_file" "lambda_function_zip" {
  type        = "zip"
  source_file = "lambda_handler.py"
  output_path = "audio_processor.zip"
}

# Lambda function to process bird audio files uploaded to S3
resource "aws_lambda_function" "audio_classifier" {
  filename      = data.archive_file.lambda_function_zip.output_path
  function_name = "canopy-id-audio_classifier"
  role          = aws_iam_role.lambda_s3_access_role.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.12"
  
  timeout       = 60   
  memory_size   = 1024 

  source_code_hash = data.archive_file.lambda_function_zip.output_base64sha256
}

# Give S3 permission to invoke this Lambda function when a new audio file is uploaded
resource "aws_lambda_permission" "allow_s3_to_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.audio_classifier.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.audio_bucket.arn
}

# Tell the S3 bucket to send the notification
resource "aws_s3_bucket_notification" "bucket_trigger" {
  bucket = aws_s3_bucket.audio_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.audio_classifier.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_invoke]
}