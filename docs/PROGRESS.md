# Estado del proyecto

**Fase actual:** F1 — Ingesta a Bronze (F0 cerrada el 2026-09-20)
**Último paso completado:** F0 cerrada: pila en la VM arriba, Airflow 3.3.2 por HTTPS (Let's Encrypt), usuarios admin/catedratico verificados; dataset `bronze` creado; `ingest/common.py` escrito. Subagentes escribiendo batch/tablas externas y productor/consumidor Kafka.
**Siguiente paso:** integrar y probar los scripts de ingesta en la VM (batch, streaming, CDC), crear tablas externas, tabla de conteos origen vs Bronze en METRICAS, commit y cierre de F1.

## Bloqueos
Ninguno. (Facturación vinculada el 2026-09-20; generador disponible en `docs/generar_red_metropolitana.py`; datos en `datos_red/`, ignorados por git.)

## Recursos de nube activos (proyecto cienciadatos-509301, us-central1)
- VM `vm-pipeline` (e2-standard-2, 30 GB) con IP estática <IP_VM>, Airflow en https://airflow.<IP_VM>.sslip.io. **Apagar con `make vm-stop` cuando no se use.**
- Credenciales de Airflow: `gcloud secrets versions access latest --secret=airflow-admin-password` (y `airflow-viewer-password` para `catedratico`).
- Bucket `cienciadatos-509301-lake` (Bronze) y `cienciadatos-509301-tfstate` (estado de Terraform).
- Datasets BigQuery: bronze (externas), staging, silver, quarantine, gold, features, ops, ops_secrets.
- Secret Manager: airflow-admin-password, airflow-viewer-password, airflow-fernet-key, hmac-salt.
- Presupuesto 60 USD/mes con alertas a <correo-del-propietario>.

## Costo acumulado en GCP
≈ 0 USD al 2026-09-20 (recursos recién creados). Cuenta de prueba gratuita: todo el consumo sale de los 300 USD de crédito.

## Datos (verificado en el generador)
Filas de origen: transmetro 363 221 · transurbano 832 791 · metroriel 299 100 · aerometro 203 554 · cdc 31 050 · catálogos 104 / 328 / 22 / 14.
`fecha_referencia = 2026-07-16`. Detalle en ADR-008, ADR-009 y ADR-010.
