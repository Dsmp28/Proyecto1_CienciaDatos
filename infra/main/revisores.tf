# ------------------------------------------------------------------------------
# main/revisores.tf · Cuentas revisoras (catedrático, evaluadores): solo lectura.
#
# Principio: pueden ver TODO lo que contiene el proyecto, no pueden cambiar nada y
# no reciben nada fuera del proyecto (ningún binding en la organización ni en la
# cuenta de facturación). Se evita `roles/viewer` porque incluye lectura de objetos
# en todos los buckets, y el bucket de estado de Terraform guarda contraseñas y la
# sal HMAC; en su lugar se conceden roles granulares:
#   - BigQuery: dataViewer en cada dataset salvo `ops_secrets` + jobUser (consultar).
#   - Lake: objectViewer solo en el bucket del lake (Bronze).
#   - Compute, IAM, Secret Manager (metadatos, no valores), Logging, Monitoring,
#     APIs habilitadas y navegación del proyecto: roles *viewer*.
# Costo: 0 USD. Las consultas del revisor se facturan al proyecto (nivel gratuito).
# ------------------------------------------------------------------------------

variable "reviewer_emails" {
  description = "Cuentas de Google con acceso de solo lectura a todo el proyecto (p. ej. el catedrático). Vacío = sin revisores."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for e in var.reviewer_emails : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", e))])
    error_message = "Cada elemento de reviewer_emails debe ser un correo válido."
  }
}

locals {
  revisores = toset(var.reviewer_emails)

  # Roles de solo lectura a nivel de proyecto (ninguno permite escribir ni leer secretos/estado).
  roles_revisor_proyecto = toset([
    "roles/browser",                         # ver el proyecto en la consola
    "roles/serviceusage.serviceUsageViewer", # APIs habilitadas
    "roles/compute.viewer",                  # VM, red, firewall (sin SSH)
    "roles/iam.securityReviewer",            # políticas IAM y cuentas de servicio
    "roles/secretmanager.viewer",            # nombres y versiones de secretos, NO sus valores
    "roles/logging.viewer",                  # bitácoras
    "roles/monitoring.viewer",               # métricas y presupuesto (canal de alertas)
    "roles/bigquery.jobUser",                # ejecutar consultas (los datos se controlan por dataset)
    "roles/bigquery.resourceViewer",         # ver jobs y reservas
  ])

  revisor_bindings = {
    for par in setproduct(local.revisores, local.roles_revisor_proyecto) :
    "${par[0]}|${par[1]}" => { email = par[0], role = par[1] }
  }

  revisor_datasets = {
    for par in setproduct(local.revisores, [for k, v in google_bigquery_dataset.this : k if k != "ops_secrets"]) :
    "${par[0]}|${par[1]}" => { email = par[0], dataset = par[1] }
  }
}

resource "google_project_iam_member" "revisor_proyecto" {
  for_each = local.revisor_bindings

  project = var.project_id
  role    = each.value.role
  member  = "user:${each.value.email}"
}

resource "google_bigquery_dataset_iam_member" "revisor_datasets" {
  for_each = local.revisor_datasets

  project    = var.project_id
  dataset_id = google_bigquery_dataset.this[each.value.dataset].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "user:${each.value.email}"
}

resource "google_storage_bucket_iam_member" "revisor_lake" {
  for_each = local.revisores

  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectViewer"
  member = "user:${each.value}"
}

output "revisores" {
  description = "Cuentas con acceso de solo lectura al proyecto."
  value       = var.reviewer_emails
}
