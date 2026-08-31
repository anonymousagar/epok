variable "gcp_project_id" {
  description = "Google Cloud Platform Project ID"
  type        = string
  default     = "epok-production"
}

variable "gcp_region" {
  description = "GCP Deployment Region"
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "Container image URI for Epok Cloud Run deployment"
  type        = string
  default     = "gcr.io/epok-production/epok-app:latest"
}

variable "db_password" {
  description = "Master password for PostgreSQL database"
  type        = string
  sensitive   = true
  default     = "EpokSuperSecurePass2026!"
}
