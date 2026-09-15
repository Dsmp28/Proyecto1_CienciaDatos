# ------------------------------------------------------------------------------
# main/versions.tf
# Versiones fijadas. Terraform local: v1.15.8. Proveedor google ~> 8.3 (verificado
# el 2026-09-20 contra la documentación del registro). Proveedor random >= 3.6
# porque `random_bytes` (usado para la Fernet key y la sal HMAC) se añadió en 3.6.
# Costo: 0 USD.
# ------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.3"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
