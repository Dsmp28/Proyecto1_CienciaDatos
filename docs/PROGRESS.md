# Estado del proyecto

**Fase actual:** F5/F7 — demo de idempotencia del DAG completo corriendo en la VM (2 corridas); guía de defensa, README y checklist en redacción. F0–F4, features (2.3), insumos de Tableau (2.1), recomendación (2.2), seguridad (3.3), linaje y escaneo de secretos ya evidenciados.
**Último paso completado:** corregidos tres defectos detectados en la primera corrida del DAG en la nube (permisos de logs por `vm-sync`, `docs/` de solo lectura en el contenedor, 429 de BigQuery por escrituras fila a fila en `ops.*`); código sincronizado a la VM; demo relanzada (2026-09-21 05:34 UTC).
**Siguiente paso:** recoger `docs/evidence/idempotencia_<ts>.md`, completar Rendimiento e Idempotencia en `docs/METRICAS.md` desde `ops.run_metrics`, revisar GUIA_DEFENSA/README/checklist, reporte de costo y recursos encendidos, cierre.

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
