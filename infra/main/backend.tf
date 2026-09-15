# ------------------------------------------------------------------------------
# main/backend.tf
# Estado remoto en GCS, en el bucket creado por infra/bootstrap.
#
# IMPORTANTE: el bloque `backend` NO admite variables ni interpolación, por eso el
# nombre del bucket va escrito a mano. Debe coincidir exactamente con el output
# `state_bucket` del bootstrap, que se construye como "<project_id>-tfstate".
# Si cambia el project_id, cambia también esta línea.
#
# Autenticación del backend: ADC (gcloud auth application-default login).
# El estado contiene valores sensibles (contraseñas, Fernet key, sal HMAC), por
# eso el bucket es privado, con acceso uniforme y versionado.
# Costo: < 0.01 USD/mes (ver bootstrap/main.tf).
# ------------------------------------------------------------------------------
terraform {
  backend "gcs" {
    bucket = "cienciadatos-509301-tfstate"
    prefix = "main"
  }
}
