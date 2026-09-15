# ------------------------------------------------------------------------------
# main/vm.tf
# Única VM del proyecto: corre Docker Compose con Airflow 3.3, Kafka 4 (KRaft),
# dbt y el proxy TLS. IP externa estática, OS Login, SA propia de mínimo privilegio.
#
# Costo aprox. (us-central1, precios de lista):
#   - e2-standard-2 (2 vCPU, 8 GB): ~0.067 USD/h → ~49 USD/mes encendida 24/7.
#     Apagada (`make vm-stop`) el cómputo cuesta 0; solo se paga disco e IP.
#     Con ~8 h/día de uso: ~16 USD/mes.
#   - Disco pd-balanced 30 GB: 0.10 USD/GB/mes → 3.00 USD/mes (se cobra aunque
#     la VM esté apagada).
#   - IP externa estática: 0.005 USD/h asignada a una VM → ~3.65 USD/mes.
#     (Si la VM está apagada la IP reservada cuesta 0.01 USD/h → ~7.30 USD/mes;
#     sigue siendo barato y evita cambiar el dominio sslip.io).
#   - Egress a internet (nivel STANDARD): ~0.085 USD/GB; uso esperado < 1 GB.
#   Total VM 24/7 ≈ 56 USD/mes; con la VM apagada fuera de horario ≈ 25 USD/mes.
# ------------------------------------------------------------------------------

# --- IP externa estática ----------------------------------------------------------------
# Estática para que el dominio airflow.<ip>.sslip.io y el certificado TLS no
# cambien cada vez que se apaga/enciende la VM.
resource "google_compute_address" "vm" {
  name         = "ip-${local.vm_name}"
  project      = var.project_id
  region       = var.region
  description  = "IP pública estática de la VM del pipeline (Airflow vía sslip.io)."
  address_type = "EXTERNAL"
  network_tier = "STANDARD" # más barato que PREMIUM; suficiente para un proyecto académico

  labels = var.labels
}

# --- VM -------------------------------------------------------------------------------------
resource "google_compute_instance" "pipeline" {
  name         = local.vm_name
  project      = var.project_id
  zone         = var.zone
  machine_type = var.machine_type
  description  = "VM del pipeline: Airflow + Kafka + dbt en Docker Compose."

  # Etiqueta de red usada por las reglas de firewall (443 público, 22 vía IAP).
  tags = ["airflow"]

  # Permite a Terraform detener la VM para cambiar machine_type, SA, etc.
  allow_stopping_for_update = true
  # Proyecto académico: se puede destruir sin pasos manuales.
  deletion_protection = false

  boot_disk {
    auto_delete = true
    initialize_params {
      image  = var.vm_image
      size   = var.disk_size_gb
      type   = "pd-balanced"
      labels = var.labels
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    access_config {
      nat_ip       = google_compute_address.vm.address
      network_tier = "STANDARD" # debe coincidir con el nivel de la IP reservada
    }
  }

  # SA propia con scope cloud-platform: los permisos reales los acotan los roles
  # IAM de iam.tf (no el scope). Sin llaves JSON: el metadata server emite tokens.
  service_account {
    email  = google_service_account.pipeline_vm.email
    scopes = ["cloud-platform"]
  }

  # Debian 12 soporta Shielded VM; secure boot no tiene costo adicional.
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
  }

  # Metadata de instancia (NO de proyecto). vm/startup.sh la lee con:
  #   curl -sH "Metadata-Flavor: Google" \
  #     http://metadata.google.internal/computeMetadata/v1/instance/attributes/<clave>
  metadata = {
    enable-oslogin         = "TRUE" # SSH gestionado por IAM (OS Login), sin llaves en metadata
    block-project-ssh-keys = "TRUE" # ignora llaves SSH a nivel de proyecto

    project-id   = var.project_id
    region       = var.region
    zone         = var.zone
    lake-bucket  = google_storage_bucket.lake.name
    airflow-host = local.airflow_host
    acme-email   = var.alert_email # cuenta ACME de Caddy (Let's Encrypt / ZeroSSL)

    # Nombres de los secretos (no sus valores) para que el script los lea de
    # Secret Manager con la SA adjunta.
    secret-airflow-admin-password  = google_secret_manager_secret.this["airflow-admin-password"].secret_id
    secret-airflow-viewer-password = google_secret_manager_secret.this["airflow-viewer-password"].secret_id
    secret-airflow-fernet-key      = google_secret_manager_secret.this["airflow-fernet-key"].secret_id
    secret-hmac-salt               = google_secret_manager_secret.this["hmac-salt"].secret_id
    secret-names                   = join(",", sort(keys(local.secrets)))
  }

  # Script de arranque: ../../vm/startup.sh. Cambiarlo recrea la VM (así se
  # vuelve a ejecutar). Si el archivo aún no existe se deja vacío para que
  # `terraform validate` funcione antes de escribir el script.
  metadata_startup_script = fileexists(local.startup_script_path) ? file(local.startup_script_path) : null

  labels = var.labels

  # Los permisos deben existir antes de que el script de arranque intente usar
  # el lake, BigQuery o los secretos.
  depends_on = [
    google_project_iam_member.vm_project_roles,
    google_storage_bucket_iam_member.vm_lake_object_admin,
    google_bigquery_dataset_iam_member.vm_data_editor,
    google_secret_manager_secret_iam_member.vm_secret_accessor,
    google_secret_manager_secret_version.initial,
    google_compute_firewall.allow_https,
    google_compute_firewall.allow_ssh_iap,
  ]
}
