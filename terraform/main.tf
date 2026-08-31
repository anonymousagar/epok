terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# 1. IAM Service Account for Epok Services
resource "google_service_account" "epok_sa" {
  account_id   = "epok-app-sa"
  display_name = "Epok Autonomous Swarm Service Account"
}

# 2. Cloud SQL Instance (PostgreSQL 15 for Temporal Backend)
resource "google_sql_database_instance" "epok_db" {
  name             = "epok-db-instance"
  database_version = "POSTGRES_15"
  region           = var.gcp_region

  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled = true
    }
  }
  deletion_protection = false
}

resource "google_sql_database" "temporal_db" {
  name     = "temporal"
  instance = google_sql_database_instance.epok_db.name
}

resource "google_sql_user" "epok_db_user" {
  name     = "epok"
  instance = google_sql_database_instance.epok_db.name
  password = var.db_password
}

# 3. Secret Manager Secrets
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "GEMINI_API_KEY"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "github_token" {
  secret_id = "GITHUB_TOKEN"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "slack_bot_token" {
  secret_id = "SLACK_BOT_TOKEN"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "linear_api_key" {
  secret_id = "LINEAR_API_KEY"
  replication {
    auto {}
  }
}

# 4. Cloud Run Service (FastAPI Webhook Gateway)
resource "google_cloud_run_v2_service" "epok_gateway" {
  name     = "epok-gateway"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.epok_sa.email

    containers {
      image = var.container_image

      env {
        name  = "MODE"
        value = "api"
      }
      env {
        name  = "TEMPORAL_HOST"
        value = "localhost:7233"
      }
      env {
        name  = "EPOK_TASK_QUEUE"
        value = "epok-task-queue"
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }
  }
}

# Allow unauthenticated invocation for incoming Webhook APIs
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.epok_gateway.location
  name     = google_cloud_run_v2_service.epok_gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
