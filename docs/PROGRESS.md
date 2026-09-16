# Estado del proyecto

**Fase actual:** F0 — Bootstrap (infraestructura aplicada; falta sincronizar código a la VM y verificar Airflow por HTTPS)
**Último paso completado:** `terraform apply` de `infra/bootstrap` (14 recursos) y `infra/main` (49 recursos) el 2026-09-20. Generador oficial leído y datos verificados (regeneración byte a byte idéntica).
**Siguiente paso:** `make vm-sync` + `make vm-up`, verificar https://airflow.<IP>.sslip.io con `admin` y `catedratico`; cerrar F0 y empezar F1 (ingesta a Bronze).

## Bloqueos
Ninguno. (Facturación vinculada el 2026-09-20; generador disponible en `docs/generar_red_metropolitana.py`; datos en `datos_red/`, ignorados por git.)

## Recursos de nube activos (proyecto cienciadatos-509301, us-central1)
- VM `vm-pipeline` (e2-standard-2, 30 GB) con IP estática. **Apagar con `make vm-stop` cuando no se use.**
- Bucket `cienciadatos-509301-lake` (Bronze) y `cienciadatos-509301-tfstate` (estado de Terraform).
- Datasets BigQuery: staging, silver, quarantine, gold, features, ops, ops_secrets.
- Secret Manager: airflow-admin-password, airflow-viewer-password, airflow-fernet-key, hmac-salt.
- Presupuesto 60 USD/mes con alertas a <correo-del-propietario>.

## Costo acumulado en GCP
≈ 0 USD al 2026-09-20 (recursos recién creados). Cuenta de prueba gratuita: todo el consumo sale de los 300 USD de crédito.

## Datos (verificado en el generador)
Filas de origen: transmetro 363 221 · transurbano 832 791 · metroriel 299 100 · aerometro 203 554 · cdc 31 050 · catálogos 104 / 328 / 22 / 14.
`fecha_referencia = 2026-07-16`. Detalle en ADR-008, ADR-009 y ADR-010.
