provider "aws" {
  region = "us-east-1"
}

# ==========================================
# VPC and Networking Resources
# ==========================================

# Create a VPC for EC2, RDS, and Lambda to run in
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "canopy-vpc" }
}

# Create a public subnet for the EC2 instance with public IP
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "us-east-1a"
  tags                    = { Name = "canopy-public-subnet" }
}

# Create a private subnet for RDS and Lambda with no public IPs
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1a"
  tags              = { Name = "canopy-private-subnet" }
}

# Create another private subnet for high availability of RDS and Lambda
resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "us-east-1b"
  tags              = { Name = "canopy-private-subnet-2" }
}

# Internet Gateway for Public Subnet
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}

# Public Route Table (Routes internet traffic to IGW)
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

# Associate the public subnet with the public route table
resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public_rt.id
}

# Private Route Table
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.main.id
}

# Associate the private subnet with the private route table
resource "aws_route_table_association" "private_assoc" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private_rt.id
}

# Associate the second private subnet with the private route table
resource "aws_route_table_association" "private_2_assoc" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private_rt.id
}

# S3 Gateway Endpoint for the private subnet to access S3 without going through the internet
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.us-east-1.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_rt.id]
}


# ===========================================
# Security Groups
# ===========================================

# Get the prefix list for S3 to allow Lambda to access S3 without hardcoding IPs
data "aws_prefix_list" "s3" {
  name = "com.amazonaws.us-east-1.s3"
}

# Lambda Security Group
resource "aws_security_group" "lambda_sg" {
  name        = "lambda-sg"
  description = "Security Group for CanopyID Lambda"
  vpc_id      = aws_vpc.main.id
}

# EC2 Security Group
resource "aws_security_group" "ec2_sg" {
  name        = "ec2-sg"
  description = "Security Group for FastAPI and Redis"
  vpc_id      = aws_vpc.main.id
}

# RDS Security Group
resource "aws_security_group" "rds_sg" {
  name        = "rds-sg"
  description = "Security Group for PostgreSQL"
  vpc_id      = aws_vpc.main.id
}

# ==========================================
# Security Group Rules
# ==========================================

# Allow SSH to EC2 from my IP only for secure access
resource "aws_security_group_rule" "allow_ssh_to_ec2" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = [var.my_ip]
  security_group_id = aws_security_group.ec2_sg.id
}

# Allow EC2 outbound HTTP traffic to anywhere (for API calls, updates, etc.)
resource "aws_security_group_rule" "allow_ec2_outbound_http" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ec2_sg.id
}

# Allow EC2 inbound HTTP traffic from anywhere
resource "aws_security_group_rule" "allow_ec2_inbound_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ec2_sg.id
}

# Lambda outbound to S3
resource "aws_security_group_rule" "lambda_outbound_s3" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_prefix_list.s3.id]
  security_group_id = aws_security_group.lambda_sg.id
}

# Lambda outbound to RDS
resource "aws_security_group_rule" "lambda_to_rds" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.lambda_sg.id
  source_security_group_id = aws_security_group.rds_sg.id
}

# Lambda outbound to Redis on EC2
resource "aws_security_group_rule" "lambda_to_redis" {
  type                     = "egress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.lambda_sg.id
  source_security_group_id = aws_security_group.ec2_sg.id
}

# EC2 Redis inbound from Lambda
resource "aws_security_group_rule" "redis_from_lambda" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ec2_sg.id
  source_security_group_id = aws_security_group.lambda_sg.id
}

# RDS inbound from EC2
resource "aws_security_group_rule" "rds_from_ec2" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id
  source_security_group_id = aws_security_group.ec2_sg.id
}

# RDS inbound from Lambda
resource "aws_security_group_rule" "rds_from_lambda" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id
  source_security_group_id = aws_security_group.lambda_sg.id
}

# ==========================================
# RDS and EC2 Resources
# ==========================================

# DB Subnet Group (Forces RDS to live in the private subnet)
resource "aws_db_subnet_group" "main" {
  name       = "canopy-db-subnet-group"
  subnet_ids = [aws_subnet.private.id, aws_subnet.private_2.id]
}

# RDS PostgreSQL instance for storing bird classification results and job metadata
resource "aws_db_instance" "bird_db" {
  identifier             = "canopy-db"
  db_name                = "bird_db"
  instance_class         = "db.t3.micro"
  engine                 = "postgres"
  engine_version         = var.engine_version
  allocated_storage      = 20
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  skip_final_snapshot = true
  publicly_accessible = false
}

# EC2 instance to host the FastAPI backend and Redis
resource "aws_instance" "backend_ec2" {
  ami                    = var.ami_id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  key_name = var.ssh_key_name

  tags = { Name = "canopy-backend" }
}

# ===========================================
# S3 Bucket
# ===========================================

# S3 bucket to store bird audio files
resource "aws_s3_bucket" "audio_bucket" {
  bucket = "canopy-id-bucket"

  force_destroy = true

  tags = {
    Name = "CanopyID Bird Audio Upload Bucket"
  }
}

# CORS configuration for the S3 bucket to allow cross-origin requests from the frontend
resource "aws_s3_bucket_cors_configuration" "audio_bucket_cors" {
  bucket = aws_s3_bucket.audio_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = [aws_instance.backend_ec2.public_dns]
    max_age_seconds = 3000
  }
}

# Block all public access to the S3 bucket for security
resource "aws_s3_bucket_public_access_block" "audio_bucket_access" {
  bucket                  = aws_s3_bucket.audio_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Give S3 permission to invoke Lambda function when a new audio file is uploaded
resource "aws_lambda_permission" "allow_s3_to_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.audio_classifier.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.audio_bucket.arn
}

# Tell the S3 bucket to send a notification to the Lambda function whenever a new audio file is uploaded
resource "aws_s3_bucket_notification" "bucket_trigger" {
  bucket = aws_s3_bucket.audio_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.audio_classifier.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_invoke]
}

# ==========================================
# Lambda and ECR Resources
# ==========================================

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

# IAM policy to allow Lambda to live in the VPC and access resources in the private subnet
resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_s3_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ECR repository to store the Lambda function container image
resource "aws_ecr_repository" "birdnet_repo" {
  name                 = "birdnet-processor"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Lambda function to process bird audio files uploaded to S3
resource "aws_lambda_function" "audio_classifier" {
  function_name = "canopy-id-audio_classifier"
  role          = aws_iam_role.lambda_s3_access_role.arn

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.birdnet_repo.repository_url}:latest"

  environment {
    variables = {
      DATABASE_URL = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.bird_db.endpoint}/postgres"
      DB_PASSWORD  = var.db_password
      REDIS_HOST   = aws_instance.backend_ec2.private_ip
    }
  }

  timeout     = 60
  memory_size = 1024

  vpc_config {
    subnet_ids         = [aws_subnet.private.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda_sg.id]
  }
}
