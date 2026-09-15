# ------------------------------------------------------------------------------
# bootstrap/main.tf
# Arranque del proyecto: habilita las APIs y crea el bucket de estado remoto.
#
# Se aplica UNA sola vez, con estado local, antes de `infra/main`.
# Autenticación: ADC (`gcloud auth application-default login`). Nunca llaves JSON.
# ------------------------------------------------------------------------------

# --- APIs -----------------------------------------------------------------------
# Costo: 0 USD. Habilitar una API no cobra nada; se paga por el uso de cada servicio.
# `disable_on_destroy = false`: al destruir el bootstrap NO se deshabilitan las
# APIs, porque otros recursos (los de main/) dependen de ellas.
resource "google_project_service" "apis" {
  for_each = var.apis

  project = var.project_id
  service = each.value

  disable_on_destroy         = false
  disable_dependent_services = false

  timeouts {
    create = "30m"
    update = "30m"
  }
}

# --- Bucket de estado de Terraform ------------------------------------------------
# Nombre: "<project_id>-tfstate". Este nombre DEBE coincidir con el que está
# escrito en infra/main/backend.tf (el bloque backend no admite variables).
#
# Costo aprox.: < 0.01 USD/mes (el estado pesa unos pocos KB; clase STANDARD
# en us-central1 cuesta 0.020 USD/GB/mes + operaciones mínimas).
#
# Seguridad:
#   - Versionado: permite recuperar un estado anterior ante un error humano.
#   - Acceso uniforme + prevención de acceso público: el estado contiene valores
#     sensibles (contraseñas generadas con random_password, Fernet key y sal HMAC),
#     por eso este bucket es privado.
#   - prevent_destroy + force_destroy=false: Terraform se niega a borrarlo.
resource "google_storage_bucket" "tfstate" {
  name     = "${var.project_id}-tfstate"
  project  = var.project_id
  location = var.region

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  # Conserva solo las 10 versiones no vigentes más recientes del estado para
  # que el versionado no crezca sin límite.
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 10
      with_state         = "ARCHIVED"
    }
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}
