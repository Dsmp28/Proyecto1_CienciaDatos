# ------------------------------------------------------------------------------
# main/providers.tf
# Proveedor de Google autenticado con ADC (Application Default Credentials).
# NUNCA se usan llaves JSON de cuentas de servicio; en la VM la autenticación la
# da la cuenta de servicio adjunta (metadata server).
#
# `user_project_override` + `billing_project`: envían el proyecto como "proyecto
# de cuota" en cada llamada. Con credenciales de usuario (ADC) algunas APIs
# (Secret Manager, IAM Credentials, Budgets) exigen un proyecto de cuota
# explícito; sin esto aparecen errores 403 "quota project not set".
# Costo: 0 USD.
# ------------------------------------------------------------------------------
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  user_project_override = true
  billing_project       = var.project_id
}

provider "random" {}
