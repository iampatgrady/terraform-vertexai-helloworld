# main.tf
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    } 
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.1"
    }
  }
} 

variable "project_id" {
  type        = string
}

variable "region" {
  type        = string
  default     = "us-central1"
} 

variable "base_message_for_pipeline" {
  type        = string
  default     = "Default Hello from Terraform to KFP!"
}

provider "google" {
  project = var.project_id
  region  = var.region
} 

resource "google_project_service" "project_apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "storage-component.googleapis.com",
    "logging.googleapis.com",
    "iam.googleapis.com"
  ])
  project            = var.project_id
  service            = each.key 
  disable_on_destroy = false
}

resource "random_id" "unique_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "pipeline_root_bucket" {
  project = var.project_id
  name    = "tfhw3-kfp-root-${var.project_id}-${random_id.unique_suffix.hex}" # Line 60
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  depends_on = [google_project_service.project_apis]
}

resource "null_resource" "run_vertex_ai_pipeline_via_script" { # Line 70
  triggers = {
    run_id                       = random_id.unique_suffix.hex
    gcp_project_id               = var.project_id
    gcp_region                   = var.region
    pipeline_gcs_root_path       = google_storage_bucket.pipeline_root_bucket.url
    input_message_for_kfp        = var.base_message_for_pipeline
    helper_script_content_hash   = filebase64sha256("${path.module}/terraform_helper.py")
    kfp_components_py_hash       = filesha256("${path.module}/pipeline/components.py")
    kfp_pipeline_py_hash         = filesha256("${path.module}/pipeline/hello_pipeline.py") # Line 80
  }

  provisioner "local-exec" {
    command = <<-EOT
      python3 "${path.module}/terraform_helper.py" \
        --project_id "${self.triggers.gcp_project_id}" \
        --region "${self.triggers.gcp_region}" \
        --pipeline_root_gcs "${self.triggers.pipeline_gcs_root_path}" \
        --job_id_suffix "${self.triggers.run_id}" \
        --message_from_tf "${self.triggers.input_message_for_kfp}" \
        --output_file "${path.module}/tfhw3_pipeline_output.json" # Line 90
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "rm -f \"${path.module}/tfhw3_pipeline_output.json\""
  }

  depends_on = [google_storage_bucket.pipeline_root_bucket]
}

data "local_file" "pipeline_run_result" {
  filename = "${path.module}/tfhw3_pipeline_output.json"

  depends_on = [null_resource.run_vertex_ai_pipeline_via_script]
} 

output "vertex_ai_pipeline_output_message" {
  description = "Message from KFP component via helper script."
  value       = try(jsondecode(data.local_file.pipeline_run_result.content).message, "Error: Could not retrieve message.")
}

output "pipeline_artifacts_gcs_bucket" {
  description = "GCS bucket for Vertex AI pipeline artifacts."
  value       = google_storage_bucket.pipeline_root_bucket.url
}

resource "null_resource" "goodbye_message_on_destroy" { 
  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Goodbye, World!'"
  }
}