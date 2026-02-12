terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "agent_sdk_archives" {
  bucket = var.archive_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "agent_sdk_archives" {
  bucket = aws_s3_bucket.agent_sdk_archives.id
  versioning_configuration {
    status = "Enabled"
  }
}
