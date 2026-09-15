# ------------------------------------------------------------------------------
# main/variables.tf
# Variables de entrada. Los valores reales van en terraform.tfvars (ignorado por
# git); ver terraform.tfvars.example.
# ------------------------------------------------------------------------------

# --- Identidad del proyecto -------------------------------------------------------

variable "project_id" {
  description = "ID del proyecto de GCP (p. ej. cienciadatos-509301)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id debe ser un ID de proyecto válido de GCP (minúsculas, dígitos y guiones)."
  }
}

variable "region" {
  description = "Región de GCP para recursos regionales (subred, IP, buckets, datasets de BigQuery, réplicas de secretos)."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona de la VM. Debe pertenecer a var.region."
  type        = string
  default     = "us-central1-a"

  validation {
    condition     = startswith(var.zone, var.region)
    error_message = "zone debe pertenecer a region (p. ej. region=us-central1, zone=us-central1-a)."
  }
}

variable "billing_account_id" {
  description = "ID de la cuenta de facturación (formato XXXXXX-XXXXXX-XXXXXX), sin el prefijo billingAccounts/. Solo se usa para el presupuesto."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id debe tener el formato XXXXXX-XXXXXX-XXXXXX (hexadecimal en mayúsculas)."
  }
}

# --- VM -----------------------------------------------------------------------------

variable "machine_type" {
  description = "Tipo de máquina de la VM. e2-standard-2 (2 vCPU, 8 GB) cuesta ~49 USD/mes encendida 24/7 en us-central1."
  type        = string
  default     = "e2-standard-2"
}

variable "disk_size_gb" {
  description = "Tamaño del disco de arranque (pd-balanced) en GB. ~0.10 USD/GB/mes."
  type        = number
  default     = 30

  validation {
    condition     = var.disk_size_gb >= 10 && var.disk_size_gb <= 200
    error_message = "disk_size_gb debe estar entre 10 y 200."
  }
}

variable "vm_image" {
  description = "Imagen de la VM en formato <proyecto>/<familia>. Debian 12 o Ubuntu 24.04 LTS (ubuntu-os-cloud/ubuntu-2404-lts-amd64)."
  type        = string
  default     = "debian-cloud/debian-12"
}

# --- Presupuesto y alertas ------------------------------------------------------------

variable "budget_amount_usd" {
  description = "Monto mensual del presupuesto en USD. Objetivo del proyecto: < 60 USD/mes."
  type        = number
  default     = 60

  validation {
    condition     = var.budget_amount_usd > 0 && floor(var.budget_amount_usd) == var.budget_amount_usd
    error_message = "budget_amount_usd debe ser un entero positivo (la API de presupuestos usa unidades enteras)."
  }
}

variable "alert_email" {
  description = "Correo que recibe las alertas del presupuesto (canal de notificación de Cloud Monitoring)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email debe ser una dirección de correo válida."
  }
}

variable "create_budget" {
  description = "Crear el presupuesto de facturación. Requiere el rol roles/billing.costsManager (o Billing Account Administrator) en la cuenta de facturación; si no lo tienes, pon false."
  type        = bool
  default     = true
}

# --- Accesos opcionales --------------------------------------------------------------

variable "tableau_user_email" {
  description = "Correo del usuario que se conecta desde Tableau Desktop por OAuth. Recibe bigquery.dataViewer SOLO en gold y bigquery.jobUser en el proyecto. Vacío = no se crea el binding."
  type        = string
  default     = ""
}

variable "auditor_email" {
  description = "Correo del auditor de fraude. Recibe bigquery.dataViewer en silver (ve la llave nativa, no seudonimizada). Vacío = no se crea el binding."
  type        = string
  default     = ""
}

# --- Etiquetas ---------------------------------------------------------------------

variable "labels" {
  description = "Etiquetas aplicadas a todos los recursos que las admiten. Sirven para filtrar costos en Billing."
  type        = map(string)
  default = {
    proyecto = "red-metropolitana"
    curso    = "ciencia-datos"
  }
}

# --- Lake ----------------------------------------------------------------------------

variable "lake_bronze_nearline_days" {
  description = "Días tras los cuales los objetos bajo bronze/ pasan a clase NEARLINE (más barata de almacenar, más cara de leer). 0 = desactivado. Para ~200 MB la diferencia es de centavos; es opcional."
  type        = number
  default     = 0
}
