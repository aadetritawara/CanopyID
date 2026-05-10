variable "db_username" {
  description = "The username for the RDS PostgreSQL instance"
  type        = string
}

variable "db_password" {
  description = "The password for the RDS PostgreSQL instance"
  type        = string
  sensitive   = true
}

variable "my_ip" {
  description = "Your current IP address for SSH access to EC2 (format: x.x.x.x/32)"
  type        = string
}

variable "engine_version" {
  description = "The version of PostgreSQL to use for RDS"
  type        = string
}

variable "ssh_key_name" {
  description = "The name of the existing AWS Key Pair to use for SSH access to EC2"
  type        = string
}

variable "ami_id" {
  description = "The AMI ID for the EC2 instance (e.g., Amazon Linux 2023)"
  type        = string
}