# ------------------------------------------------------------------------------
# main/outputs.tf
# Ningún output expone valores secretos: solo nombres e identificadores. Los
# valores de los secretos se leen desde Secret Manager (ver README).
# ------------------------------------------------------------------------------

output "vm_external_ip" {
  description = "IP externa estática de la VM."
  value       = google_compute_address.vm.address
}

output "airflow_url" {
  description = "URL pública de Airflow (HTTPS, dominio sslip.io que resuelve a la IP de la VM)."
  value       = "https://${local.airflow_host}"
}

output "airflow_host" {
  description = "Nombre de host de Airflow; el mismo valor llega a la VM como metadata `airflow-host`."
  value       = local.airflow_host
}

output "lake_bucket" {
  description = "Nombre del bucket del lake (Bronze vive en gs://<bucket>/bronze/)."
  value       = google_storage_bucket.lake.name
}

output "bigquery_datasets" {
  description = "Lista de datasets de BigQuery creados."
  value       = sort([for d in google_bigquery_dataset.this : d.dataset_id])
}

output "vm_service_account_email" {
  description = "Correo de la cuenta de servicio adjunta a la VM (sa-pipeline-vm)."
  value       = google_service_account.pipeline_vm.email
}

output "ssh_command" {
  description = "Comando para entrar a la VM por túnel IAP (el puerto 22 no está abierto a internet)."
  value       = "gcloud compute ssh ${google_compute_instance.pipeline.name} --zone ${var.zone} --tunnel-through-iap --project ${var.project_id}"
}

output "secret_names" {
  description = "Nombres (secret_id) de los secretos en Secret Manager."
  value       = sort([for s in google_secret_manager_secret.this : s.secret_id])
}

output "budget_name" {
  description = "Nombre del presupuesto de facturación (vacío si create_budget = false)."
  value       = var.create_budget ? google_billing_budget.monthly[0].name : ""
}
