# ------------------------------------------------------------------------------
# main/bigquery.tf
# Datasets de BigQuery del pipeline (todos en var.region, misma región que el
# bucket del lake para que las tablas externas Hive sobre Bronze funcionen sin
# egress entre regiones).
#
# Costo aprox.: almacenamiento activo 0.02 USD/GB/mes (los primeros 10 GB gratis
# cada mes) y consultas 6.25 USD/TB (el primer TB del mes es gratis). Para ~200 MB
# de datos y consultas de dbt/Tableau el costo esperado es 0 USD/mes.
#
# Permisos: se gestionan con google_bigquery_dataset_iam_member (iam.tf) y NO con
# el bloque `access` del dataset, porque ambos mecanismos no pueden mezclarse.
# Al crearse, BigQuery añade las entradas por defecto (projectOwners=OWNER,
# projectWriters=WRITER, projectReaders=READER); como nadie tiene roles
# primitivos Editor/Viewer en el proyecto, en la práctica solo el propietario
# accede por esa vía. Esto cumple la regla de ops_secrets: solo la SA de la VM
# (dataEditor, ver iam.tf) y el propietario del proyecto.
#
# default_table_expiration_ms se deja sin definir (nulo): las tablas no expiran.
# delete_contents_on_destroy = true porque es un proyecto académico.
# ------------------------------------------------------------------------------

resource "google_bigquery_dataset" "this" {
  for_each = local.datasets

  project       = var.project_id
  dataset_id    = each.key
  friendly_name = each.value.friendly_name
  description   = each.value.description
  location      = var.region

  delete_contents_on_destroy = true

  # Ventana de "time travel" mínima (2 días) para reducir el almacenamiento
  # facturable de versiones históricas; el pipeline es idempotente y regenerable.
  max_time_travel_hours = 48

  labels = merge(var.labels, { capa = replace(each.key, "_", "-") })
}
