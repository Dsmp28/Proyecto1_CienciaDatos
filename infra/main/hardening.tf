# ------------------------------------------------------------------------------
# main/hardening.tf · Endurecimiento derivado de la revisión de seguridad (2026-09-23).
#
# 1. La cuenta de servicio por defecto de Compute recibe `roles/editor` al habilitar
#    la API. Nada del proyecto la usa (la VM tiene su propia SA) y ese rol le daría
#    acceso al estado de Terraform y a todos los datasets. Se desprivilegia.
# 2. El puerto 443 (Airflow) puede acotarse a rangos concretos fuera de la demo.
# Costo: 0 USD.
# ------------------------------------------------------------------------------

resource "google_project_default_service_accounts" "deprivilege" {
  project = var.project_id
  action  = "DEPRIVILEGE" # quita los roles heredados a la SA por defecto de Compute; no la borra
  # Al destruir la infraestructura se restaura el estado anterior (comportamiento por defecto del recurso).
}

variable "https_source_ranges" {
  description = "Rangos CIDR que pueden alcanzar Airflow por 443. Dejar 0.0.0.0/0 solo mientras el catedrático necesite el enlace; fuera de la demo, acotar a las IP del equipo (p. ej. [\"203.0.113.10/32\"])."
  type        = list(string)
  default     = ["0.0.0.0/0"]
  validation {
    condition     = length(var.https_source_ranges) > 0
    error_message = "https_source_ranges no puede estar vacío."
  }
}
