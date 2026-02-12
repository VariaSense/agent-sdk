variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "archive_bucket_name" {
  type        = string
  description = "S3 bucket for run archives and privacy exports"
}
