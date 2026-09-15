# ------------------------------------------------------------------------------
# main/storage.tf
# Bucket del lake: gs://<project_id>-lake. Bronze vive en bronze/<fuente>/ingest_date=YYYY-MM-DD/.
#
# Costo aprox.: ~0.02 USD/GB/mes en clase STANDARD (us-central1). Con ~200 MB de
# datos generados ≈ 0.01 USD/mes. Operaciones de clase A/B: centavos.
#
# Decisiones:
#   - Sin versionado: Bronze es inmutable por diseño (se acumula sin duplicarse);
#     versionar solo duplicaría almacenamiento.
#   - force_destroy = true: proyecto académico; `terraform destroy` borra los datos.
#   - soft_delete_policy = 0: desactiva la retención de objetos borrados (7 días por
#     defecto) para no pagar almacenamiento de datos que se regeneran.
#   - public_access_prevention = enforced: nunca público.
#   - IAM del bucket (objectAdmin para la SA de la VM) está en iam.tf.
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "lake" {
  name     = "${var.project_id}-lake"
  project  = var.project_id
  location = var.region

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = false
  }

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  # Limpia cargas multiparte incompletas (no cuestan mucho, pero no aportan nada).
  lifecycle_rule {
    action {
      type = "AbortIncompleteMultipartUpload"
    }
    condition {
      age = 7
    }
  }

  # Opcional: mover bronze/ a NEARLINE tras N días (desactivado con 0).
  dynamic "lifecycle_rule" {
    for_each = var.lake_bronze_nearline_days > 0 ? [1] : []
    content {
      action {
        type          = "SetStorageClass"
        storage_class = "NEARLINE"
      }
      condition {
        age            = var.lake_bronze_nearline_days
        matches_prefix = ["bronze/"]
      }
    }
  }

  labels = var.labels
}

# "Carpeta" lógica bronze/. GCS no tiene carpetas reales: un objeto cuyo nombre
# termina en "/" hace que la consola y las herramientas la muestren como tal.
# Costo: 0 USD (objeto de 1 byte).
resource "google_storage_bucket_object" "bronze_folder" {
  name    = "bronze/"
  bucket  = google_storage_bucket.lake.name
  content = " "
}
