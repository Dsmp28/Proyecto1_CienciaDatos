# ------------------------------------------------------------------------------
# bootstrap/variables.tf
# Variables del módulo de arranque (bucket de estado + APIs).
# ------------------------------------------------------------------------------

variable "project_id" {
  description = "ID del proyecto de GCP (p. ej. cienciadatos-509301)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id debe ser un ID de proyecto válido de GCP (minúsculas, dígitos y guiones)."
  }
}

variable "region" {
  description = "Región donde se crea el bucket de estado."
  type        = string
  default     = "us-central1"
}

variable "labels" {
  description = "Etiquetas aplicadas a todos los recursos que las admiten."
  type        = map(string)
  default = {
    proyecto = "red-metropolitana"
    curso    = "ciencia-datos"
  }
}

variable "apis" {
  description = "APIs de Google Cloud que se habilitan en el proyecto. Habilitar una API no tiene costo; solo se paga por el uso de cada servicio."
  type        = set(string)
  default = [
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "secretmanager.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iap.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "oslogin.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}
