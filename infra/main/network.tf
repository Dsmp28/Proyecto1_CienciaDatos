# ------------------------------------------------------------------------------
# main/network.tf
# VPC propia (sin la red "default"), una subred regional y reglas de firewall.
#
# Costo: 0 USD. VPC, subredes y reglas de firewall no se cobran. Solo se cobra el
# tráfico de salida a internet (egress), estimado en centavos para este proyecto.
#
# Política de firewall (restricción dura del proyecto):
#   - 443/tcp abierto a internet (0.0.0.0/0)  → Airflow detrás de un proxy TLS.
#   - 22/tcp SOLO desde el rango de IAP 35.235.240.0/20 → SSH por túnel IAP.
#   - Kafka (9092) NO se expone: no existe regla que lo permita.
#   - Egress permitido (explícito, equivalente a la regla implícita de GCP).
#   - Todo lo demás en ingress queda denegado por la regla implícita de GCP; se
#     añade una regla explícita de denegación para que la intención sea visible.
# ------------------------------------------------------------------------------

resource "google_compute_network" "vpc" {
  name                    = "vpc-pipeline"
  project                 = var.project_id
  description             = "VPC del pipeline de transporte (una sola VM)."
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  mtu                     = 1460
}

resource "google_compute_subnetwork" "subnet" {
  name          = "subnet-pipeline-${var.region}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = "10.10.0.0/24"
  description   = "Subred única del pipeline."

  # Permite a la VM alcanzar APIs de Google (BigQuery, GCS, Secret Manager) por
  # IP privada aunque en el futuro se le quite la IP externa.
  private_ip_google_access = true
}

# --- Ingress 443 desde internet ----------------------------------------------------
resource "google_compute_firewall" "allow_https" {
  name        = "fw-allow-https-airflow"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "HTTPS público hacia la VM de Airflow (etiqueta de red: airflow)."
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = var.https_source_ranges # ver hardening.tf: acotar fuera de la demo
  target_tags   = ["airflow"]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
}

# --- Ingress 22 solo desde IAP -----------------------------------------------------
# 35.235.240.0/20 es el rango publicado por Google para el reenvío TCP de IAP.
resource "google_compute_firewall" "allow_ssh_iap" {
  name        = "fw-allow-ssh-iap"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "SSH únicamente a través de Identity-Aware Proxy (gcloud compute ssh --tunnel-through-iap)."
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["airflow"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# --- Deny explícito del resto del ingress ----------------------------------------------
# Redundante con la regla implícita de GCP (prioridad 65535) pero deja constancia
# de que Kafka (9092) y cualquier otro puerto no se exponen. Sin log_config para
# no generar costos de Cloud Logging.
resource "google_compute_firewall" "deny_all_ingress" {
  name        = "fw-deny-all-ingress"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Deniega todo el ingress no permitido explícitamente (Kafka nunca se expone)."
  direction   = "INGRESS"
  priority    = 65000

  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }
}

# --- Egress permitido -------------------------------------------------------------------
# La VM necesita salir a internet para apt, Docker Hub, Let's Encrypt y las APIs
# de Google. Equivale a la regla implícita "allow egress" de GCP.
resource "google_compute_firewall" "allow_egress" {
  name        = "fw-allow-egress"
  project     = var.project_id
  network     = google_compute_network.vpc.name
  description = "Permite todo el tráfico de salida."
  direction   = "EGRESS"
  priority    = 1000

  destination_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "all"
  }
}
