# ------------------------------------------------------------------------------
# main/iam.tf
# Cuentas de servicio y bindings de mínimo privilegio. Sin roles primitivos
# (owner/editor/viewer) y sin llaves JSON: la VM se autentica con la cuenta de
# servicio adjunta y el usuario con ADC/OAuth.
#
# Costo: 0 USD (IAM no se cobra).
#
# Resumen de accesos:
#   sa-pipeline-vm  → objectAdmin SOLO en el bucket del lake
#                   → bigquery.jobUser en el proyecto (poder lanzar jobs)
#                   → bigquery.dataEditor en CADA dataset (incluido ops_secrets)
#                   → secretmanager.secretAccessor en CADA secreto
#                   → logging.logWriter + monitoring.metricWriter (agente de ops)
#   tableau_user    → bigquery.dataViewer SOLO en gold + bigquery.jobUser (opcional)
#   auditor         → bigquery.dataViewer SOLO en silver (opcional)
#   ops_secrets     → solo sa-pipeline-vm (dataEditor) y el propietario del proyecto
# ------------------------------------------------------------------------------

# --- Cuenta de servicio de la VM -------------------------------------------------------------
resource "google_service_account" "pipeline_vm" {
  project      = var.project_id
  account_id   = "sa-pipeline-vm"
  display_name = "SA de la VM del pipeline (Airflow, Kafka, dbt)"
  description  = "Cuenta adjunta a la VM. Acceso al lake, a los datasets de BigQuery y a los secretos; sin llaves JSON."
}

# Roles a nivel de PROYECTO (los mínimos que no pueden acotarse a un recurso).
resource "google_project_iam_member" "vm_project_roles" {
  for_each = toset([
    "roles/bigquery.jobUser",       # crear jobs de carga/consulta (los datos se controlan por dataset)
    "roles/logging.logWriter",      # enviar logs de la VM a Cloud Logging
    "roles/monitoring.metricWriter" # enviar métricas del agente de ops
  ])

  project = var.project_id
  role    = each.value
  member  = google_service_account.pipeline_vm.member
}

# Bucket del lake: binding a nivel de BUCKET, no de proyecto.
resource "google_storage_bucket_iam_member" "vm_lake_object_admin" {
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.pipeline_vm.member
}

# Datasets: dataEditor en cada uno (staging, silver, quarantine, gold, features,
# ops, ops_secrets). Es el único principal con acceso a ops_secrets además del
# propietario del proyecto.
resource "google_bigquery_dataset_iam_member" "vm_data_editor" {
  for_each = google_bigquery_dataset.this

  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline_vm.member
}

# Secretos: accessor por SECRETO, no a nivel de proyecto.
resource "google_secret_manager_secret_iam_member" "vm_secret_accessor" {
  for_each = google_secret_manager_secret.this

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.pipeline_vm.member
}

# --- Tableau Desktop (usuario humano por OAuth) ---------------------------------------------
# No se crea una SA "sa-tableau-reader": Tableau se conecta con la cuenta de Google
# del usuario, así que se le da acceso de lectura SOLO a gold y permiso de lanzar
# consultas en el proyecto. Opcional: vacío = sin bindings.
resource "google_bigquery_dataset_iam_member" "tableau_gold_viewer" {
  count = var.tableau_user_email != "" ? 1 : 0

  project    = var.project_id
  dataset_id = google_bigquery_dataset.this["gold"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "user:${var.tableau_user_email}"
}

resource "google_project_iam_member" "tableau_job_user" {
  count = var.tableau_user_email != "" ? 1 : 0

  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "user:${var.tableau_user_email}"
}

# --- Auditor de fraude (opcional) -------------------------------------------------------------
# Ve silver (con la llave nativa de usuario, sin seudonimizar). Sin jobUser en el
# proyecto: puede consultar desde su propio proyecto de facturación o se le añade
# aparte si hace falta.
resource "google_bigquery_dataset_iam_member" "auditor_silver_viewer" {
  count = var.auditor_email != "" ? 1 : 0

  project    = var.project_id
  dataset_id = google_bigquery_dataset.this["silver"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "user:${var.auditor_email}"
}
