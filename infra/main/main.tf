# ------------------------------------------------------------------------------
# main/main.tf
# Valores locales compartidos por el resto de archivos y datos del proyecto.
# No crea recursos facturables. Costo: 0 USD.
#
# Orden lógico de lectura: main.tf → network.tf → storage.tf → bigquery.tf →
# secrets.tf → iam.tf → vm.tf → budget.tf → outputs.tf
# ------------------------------------------------------------------------------

locals {
  vm_name = "vm-pipeline"

  # Ruta al script de arranque de la VM (se pasa como metadata_startup_script).
  startup_script_path = "${path.module}/../../vm/startup.sh"

  # Dominio público de Airflow vía sslip.io (resuelve al IP embebido en el nombre,
  # sin comprar dominio ni crear zona DNS). Formato con puntos: airflow.<ip>.sslip.io
  airflow_host = "airflow.${google_compute_address.vm.address}.sslip.io"

  # Datasets de BigQuery (capa medallón + operativos). Las llaves son el dataset_id.
  datasets = {
    staging = {
      friendly_name = "Staging"
      description   = "Capa de aterrizaje: copia cruda y tipada de cada archivo de Bronze. Se vacía en cada corrida (idempotencia)."
    }
    silver = {
      friendly_name = "Silver"
      description   = "Capa limpia y conformada: registros validados, deduplicados y con columnas de linaje (fuente, archivo, fecha_ingesta). Contiene la llave nativa de usuario; acceso restringido."
    }
    quarantine = {
      friendly_name = "Cuarentena"
      description   = "Registros rechazados por validación o duplicidad, con registro original, fuente, motivo y timestamp. Ningún registro se descarta: staging = silver + quarantine."
    }
    gold = {
      friendly_name = "Gold"
      description   = "Capa analítica para Tableau: hechos y dimensiones con la llave de usuario seudonimizada (HMAC-SHA256). Solo hace ref() a Silver u otro Gold."
    }
    features = {
      friendly_name = "Features"
      description   = "Características para modelos de ML derivadas exclusivamente de Silver (nunca de Gold)."
    }
    ops = {
      friendly_name = "Operaciones"
      description   = "Metadatos operativos del pipeline: bitácora de corridas, conteos por capa, conciliaciones y métricas de calidad."
    }
    ops_secrets = {
      friendly_name = "Operaciones (restringido)"
      description   = "Tablas operativas sensibles (p. ej. mapeo llave nativa ↔ llave seudonimizada). Acceso exclusivo de la cuenta de servicio de la VM y del propietario del proyecto."
    }
  }

  # Secretos de Secret Manager. Terraform crea el contenedor y (por ser valores
  # generados aleatoriamente) también la primera versión. Ver secrets.tf.
  secrets = {
    "airflow-admin-password"  = "Contraseña del usuario admin de Airflow (generada por Terraform)."
    "airflow-viewer-password" = "Contraseña del usuario de solo lectura de Airflow para el catedrático (generada por Terraform)."
    "airflow-fernet-key"      = "Fernet key de Airflow para cifrar conexiones y variables (32 bytes, base64 url-safe)."
    "hmac-salt"               = "Sal secreta para la seudonimización HMAC-SHA256 de la llave de usuario antes de Gold (32 bytes, base64)."
  }

  # Umbrales del presupuesto (fracción de 1.0) sobre el gasto real del mes.
  budget_thresholds = [0.25, 0.5, 0.75, 0.9, 1.0]
}
