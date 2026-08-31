output "cloud_run_url" {
  description = "Public URL of Epok Cloud Run Webhook Gateway"
  value       = google_cloud_run_v2_service.epok_gateway.uri
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL Instance connection name"
  value       = google_sql_database_instance.epok_db.connection_name
}

output "webhook_linear_endpoint" {
  description = "Linear Webhook Ingestion Endpoint"
  value       = "${google_cloud_run_v2_service.epok_gateway.uri}/webhooks/linear"
}

output "webhook_github_endpoint" {
  description = "GitHub Actions Webhook Ingestion Endpoint"
  value       = "${google_cloud_run_v2_service.epok_gateway.uri}/webhooks/github"
}

output "webhook_slack_endpoint" {
  description = "Slack Interactive Actions Webhook Endpoint"
  value       = "${google_cloud_run_v2_service.epok_gateway.uri}/webhooks/slack"
}
