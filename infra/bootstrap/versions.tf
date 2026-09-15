# ------------------------------------------------------------------------------
# bootstrap/versions.tf
# Versiones fijadas de Terraform y del proveedor de Google.
#
# Este módulo usa ESTADO LOCAL (terraform.tfstate en este directorio) porque
# su única misión es crear el bucket donde vivirá el estado remoto de `main/`.
# El archivo de estado está excluido del repositorio por .gitignore (*.tfstate).
# Costo: 0 USD (no hay recursos en este archivo).
# ------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.3"
    }
  }
}
