# SKELETON — not applied. See README.md.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.region
}

variable "region" { type = string }
variable "env" {
  type    = string
  default = "dev"
}
variable "service_name" {
  type    = string
  default = "readiness-api"
}
variable "image" {
  type    = string
  default = ""
}
variable "report_retention_days" {
  type    = number
  default = 90
}

locals {
  tags = { app = "readiness", env = var.env, managed_by = "terraform" }
}

resource "aws_ecr_repository" "images" {
  name                 = "readiness"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = local.tags
}

resource "aws_kms_key" "data" {
  description         = "readiness ${var.env} data"
  enable_key_rotation = true
  tags                = local.tags
}

resource "aws_s3_bucket" "uploads" {
  bucket = "readiness-uploads-${var.env}-${data.aws_caller_identity.me.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket" "reports" {
  bucket = "readiness-reports-${var.env}-${data.aws_caller_identity.me.account_id}"
  tags   = local.tags
}

data "aws_caller_identity" "me" {}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = { uploads = aws_s3_bucket.uploads.id, reports = aws_s3_bucket.reports.id }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = { uploads = aws_s3_bucket.uploads.id, reports = aws_s3_bucket.reports.id }
  bucket   = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "all" {
  for_each = { uploads = aws_s3_bucket.uploads.id, reports = aws_s3_bucket.reports.id }
  bucket   = each.value
  rule {
    id     = "expire"
    status = "Enabled"
    filter {}
    expiration { days = var.report_retention_days }
  }
}

resource "aws_secretsmanager_secret" "secrets" {
  for_each   = toset(["READINESS_API_TOKEN", "ANTHROPIC_API_KEY"])
  name       = "readiness/${var.env}/${each.value}"
  kms_key_id = aws_kms_key.data.arn
  tags       = local.tags
}

resource "aws_iam_role" "runtime" {
  name = "readiness-runtime-${var.env}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "tasks.apprunner.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "runtime" {
  name = "readiness-runtime"
  role = aws_iam_role.runtime.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:ListBucket"], Resource = [aws_s3_bucket.uploads.arn, "${aws_s3_bucket.uploads.arn}/*"] },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"], Resource = [aws_s3_bucket.reports.arn, "${aws_s3_bucket.reports.arn}/*"] },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [for s in aws_secretsmanager_secret.secrets : s.arn] },
      { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = [aws_kms_key.data.arn] },
    ]
  })
}

# App Runner service is left to a follow-up (INF-06): it needs an ECR access role and an image that exists.
