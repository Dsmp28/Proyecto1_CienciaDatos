# ------------------------------------------------------------------------------
# bootstrap/outputs.tf
# ------------------------------------------------------------------------------

output "state_bucket" {
  description = "Nombre del bucket de estado. Debe coincidir con `bucket` en infra/main/backend.tf."
  value       = google_storage_bucket.tfstate.name
}

output "state_bucket_url" {
  description = "URL gs:// del bucket de estado."
  value       = google_storage_bucket.tfstate.url
}

output "enabled_apis" {
  description = "APIs habilitadas en el proyecto."
  value       = sort([for s in google_project_service.apis : s.service])
}
