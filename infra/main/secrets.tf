# ------------------------------------------------------------------------------
# main/secrets.tf
# Secretos en Secret Manager.
#
# Costo aprox.: 0.06 USD por versión activa y por ubicación de réplica al mes.
# 4 secretos × 1 réplica (var.region) = 0.24 USD/mes. Accesos: 0.03 USD por cada
# 10 000 operaciones (la VM lee los secretos solo al arrancar) ≈ 0 USD.
#
# Regla del proyecto: Terraform crea los CONTENEDORES de los secretos. Como
# excepción aceptada, las cuatro primeras versiones se GENERAN aquí con el
# proveedor random (contraseñas de Airflow, Fernet key y sal HMAC) y se guardan
# como versión 1. Nadie tiene que inventar ni copiar un secreto a mano.
#
# ADVERTENCIA: los valores generados quedan en el ESTADO de Terraform (en texto
# claro). Por eso el bucket de estado es privado, con acceso uniforme, prevención
# de acceso público y versionado (ver bootstrap/main.tf). Quien pueda leer el
# estado puede leer estos secretos; no compartas el bucket.
#
# Rotación: `terraform taint`/`-replace` del recurso random correspondiente crea
# una versión nueva; la VM toma la versión "latest" en el siguiente arranque.
# ------------------------------------------------------------------------------

# --- Contenedores -----------------------------------------------------------------------
resource "google_secret_manager_secret" "this" {
  for_each = local.secrets

  project   = var.project_id
  secret_id = each.key

  annotations = {
    descripcion = each.value
  }

  # Réplica única en la región del proyecto (una sola ubicación facturable).
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  # Proyecto académico: `terraform destroy` puede borrar los secretos.
  deletion_protection = false

  labels = var.labels
}

# --- Valores generados -----------------------------------------------------------------------
# Contraseñas de 24 caracteres. Se restringen los caracteres especiales a un
# conjunto seguro para shells, docker-compose y .env (sin comillas, $, \, !, #, espacios).
resource "random_password" "airflow_admin" {
  length           = 24
  special          = true
  override_special = "-_.+=@%^*"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 1
}

resource "random_password" "airflow_viewer" {
  length           = 24
  special          = true
  override_special = "-_.+=@%^*"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 1
}

# Fernet key: Airflow exige 32 bytes aleatorios en base64 URL-SAFE. random_bytes
# entrega base64 estándar (+ y /), así que se convierte a la variante URL-safe
# (- y _) para cumplir estrictamente con la especificación de Fernet.
resource "random_bytes" "airflow_fernet" {
  length = 32
}

# Sal HMAC de 32 bytes, guardada en base64. Se usa random_bytes (y no random_id)
# porque sus atributos son sensibles y no se imprimen en `terraform plan`.
resource "random_bytes" "hmac_salt" {
  length = 32
}

locals {
  secret_values = {
    "airflow-admin-password"  = random_password.airflow_admin.result
    "airflow-viewer-password" = random_password.airflow_viewer.result
    "airflow-fernet-key"      = replace(replace(random_bytes.airflow_fernet.base64, "+", "-"), "/", "_")
    "hmac-salt"               = random_bytes.hmac_salt.base64
  }
}

# --- Versión 1 de cada secreto -------------------------------------------------------------------
resource "google_secret_manager_secret_version" "initial" {
  for_each = local.secret_values

  secret      = google_secret_manager_secret.this[each.key].id
  secret_data = each.value
}
