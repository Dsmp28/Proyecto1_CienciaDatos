# Estado del proyecto

**Fase actual:** F5/F6 — demo de idempotencia corriendo en la VM (DAG completo × 2); features listas; insumos de Tableau y recomendación en construcción (F4 cerrada el 2026-09-21)
**Último paso completado:** F1 cerrada: 9 archivos en Bronze por batch, streaming (Kafka→GCS, 114 objetos deterministas) y CDC; conciliación origen = Bronze (1 730 184 filas, diferencia 0); segunda corrida sin cambios. Tablas externas `bronze.*` creadas. HMAC verificado. Subagente construyendo `dbt/models/staging/` (F2).
**Siguiente paso:** revisar y commitear Staging + CDC aplicado (métricas 1.2), luego Silver + cuarentena (F3) con las reglas de `docs/governance/reglas_calidad.md`.

## Bloqueos
Ninguno. (Facturación vinculada el 2026-09-20; generador disponible en `docs/generar_red_metropolitana.py`; datos en `datos_red/`, ignorados por git.)

## Recursos de nube activos (proyecto cienciadatos-509301, us-central1)
- VM `vm-pipeline` (e2-standard-2, 30 GB) con IP estática <IP_VM>, Airflow en https://airflow.<IP_VM>.sslip.io. **Apagar con `make vm-stop` cuando no se use.**
- Credenciales de Airflow: `gcloud secrets versions access latest --secret=airflow-admin-password` (y `airflow-viewer-password` para `catedratico`).
- Bucket `cienciadatos-509301-lake` (Bronze: 121 objetos, ~346 MB) y `cienciadatos-509301-tfstate` (estado de Terraform).
- Datasets BigQuery: bronze (externas), staging, silver, quarantine, gold, features, ops, ops_secrets.
- Secret Manager: airflow-admin-password, airflow-viewer-password, airflow-fernet-key, hmac-salt.
- Presupuesto 60 USD/mes con alertas a <correo-del-propietario>.

## Costo acumulado en GCP
≈ 0 USD al 2026-09-20 (recursos recién creados). Cuenta de prueba gratuita: todo el consumo sale de los 300 USD de crédito.

## Datos (verificado en el generador)
Filas de origen: transmetro 363 221 · transurbano 832 791 · metroriel 299 100 · aerometro 203 554 · cdc 31 050 · catálogos 104 / 328 / 22 / 14.
`fecha_referencia = 2026-07-16`. Detalle en ADR-008, ADR-009 y ADR-010.
