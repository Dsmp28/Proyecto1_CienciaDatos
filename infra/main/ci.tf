# ------------------------------------------------------------------------------
# main/ci.tf · Identidad para GitHub Actions (extra: `dbt test` en cada push).
#
# Sin llaves JSON (restricción del proyecto): GitHub Actions obtiene un token OIDC
# y lo intercambia por credenciales de la cuenta de servicio `sa-ci-dbt` mediante
# Workload Identity Federation. Solo el repositorio `var.github_repo` puede hacerlo
# (condición de atributo sobre `assertion.repository`).
#
# Permisos mínimos de `sa-ci-dbt`: lanzar consultas (jobUser), leer todos los
# datasets (dataViewer) y escribir SOLO en `ops` (dbt guarda los fallos de las
# pruebas con `store_failures` en ese dataset).
#
# Todo queda detrás de `var.github_repo != ""`: no se crea nada hasta que exista
# el repositorio remoto. Costo: 0 USD.
# ------------------------------------------------------------------------------

locals {
  ci_habilitado = var.github_repo != ""
}

resource "google_iam_workload_identity_pool" "github" {
  count = local.ci_habilitado ? 1 : 0

  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "Federación de identidad para el CI del repositorio ${var.github_repo}."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = local.ci_habilitado ? 1 : 0

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
  }
  # Solo este repositorio y su propietario pueden intercambiar tokens (un fork tiene otro `repository`).
  attribute_condition = "assertion.repository == \"${var.github_repo}\" && assertion.repository_owner == \"${split("/", var.github_repo)[0]}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci_dbt" {
  count = local.ci_habilitado ? 1 : 0

  project      = var.project_id
  account_id   = "sa-ci-dbt"
  display_name = "SA de GitHub Actions (dbt test)"
  description  = "Ejecuta `dbt test` desde CI. Solo lectura de datos; escribe únicamente en ops (store_failures)."
}

# Solo las ejecuciones sobre la rama main (push) pueden actuar como la SA; las pull requests
# ejecutan únicamente el trabajo sin nube.
resource "google_service_account_iam_member" "ci_wif_user" {
  count = local.ci_habilitado ? 1 : 0

  service_account_id = google_service_account.ci_dbt[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.ref/refs/heads/main"
}

resource "google_project_iam_member" "ci_job_user" {
  count = local.ci_habilitado ? 1 : 0

  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.ci_dbt[0].member
}

resource "google_bigquery_dataset_iam_member" "ci_data_viewer" {
  for_each = local.ci_habilitado ? { for k, v in google_bigquery_dataset.this : k => v if k != "ops_secrets" } : {}

  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.ci_dbt[0].member
}

# Las tablas externas de Bronze leen objetos de GCS: la SA de CI necesita listar/leer el lake (solo lectura).
resource "google_storage_bucket_iam_member" "ci_lake_viewer" {
  count = local.ci_habilitado ? 1 : 0

  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.ci_dbt[0].member
}

resource "google_bigquery_dataset_iam_member" "ci_ops_editor" {
  count = local.ci_habilitado ? 1 : 0

  project    = var.project_id
  dataset_id = google_bigquery_dataset.this["ops"].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.ci_dbt[0].member
}

output "ci_workload_identity_provider" {
  description = "Valor para el secreto/variable GCP_WIF_PROVIDER de GitHub Actions (vacío si CI no está habilitado)."
  value       = local.ci_habilitado ? google_iam_workload_identity_pool_provider.github[0].name : ""
}

output "ci_service_account_email" {
  description = "Valor para GCP_CI_SERVICE_ACCOUNT de GitHub Actions (vacío si CI no está habilitado)."
  value       = local.ci_habilitado ? google_service_account.ci_dbt[0].email : ""
}
